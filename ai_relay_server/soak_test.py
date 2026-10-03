"""
릴레이 장시간 부하(soak) 시험 — 하드웨어 불필요
================================================
가짜 rosbridge 2대 + in-process 릴레이 + Unity 역할 클라이언트로 아래 순환 시나리오를 반복하며 측정:
  A 수동 주행(지령→cmd_vel 지연 측정) → B 전방 0.3m 장애물 → C 2대 AUTO + 0.8m 만남 → D 콕핏 진입·후진 비켜주기
측정: 텔레메트리 주기·드롭, 영상 프레임 수, cmd_vel 송신율(로봇별), 지령→cmd_vel 지연, 프로세스 메모리 추이,
      안전 불변식 위반(장애물·만남 구간 전진 지령 > 0) 횟수.
실행: python ai_relay_server/soak_test.py [초, 기본 300]
"""

import asyncio
import ctypes
import gc
import json
import math
import statistics
import sys
import time
import tracemalloc

import websockets
from websockets.server import serve

from ros2_multi_turtlebot_relay import MultiTurtleBotRelay
from rosbridge_link import RosbridgeLink
from test_real_bridge import TICK_S, FakeRosbridge

TB1_PORT, TB2_PORT, RELAY_PORT = 19291, 19292, 19293     # test_real_bridge(1919x)와 동시 실행 가능
CYCLE_S = 12.0
SETTLE_S = 0.3              # 상태 전환 후 판정 유예 (게이트 반영 시간)
EXPECTED_HZ = 1.0 / TICK_S  # 20 Hz


class TimedFake(FakeRosbridge):
    """cmd_vel 수신 시각까지 기록하는 가짜 rosbridge."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.cmd_times = []

    async def handler(self, ws):
        async def pump():
            while True:
                if self.publishing:
                    await ws.send(json.dumps({"op": "publish", "topic": "/odom", "msg": self._odom_msg()}))
                    await ws.send(json.dumps({"op": "publish", "topic": "/scan", "msg": self._scan_msg()}))
                await asyncio.sleep(TICK_S)
        task = asyncio.create_task(pump())
        try:
            async for raw in ws:
                data = json.loads(raw)
                if data.get("op") == "publish" and data.get("topic") == "/cmd_vel":
                    self.cmd_vel.append((data["msg"]["linear"]["x"], data["msg"]["angular"]["z"]))
                    self.cmd_times.append(time.perf_counter())
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            task.cancel()


def working_set_mb() -> float:
    """현재 프로세스 메모리 (Windows Working Set, MB). 실패 시 -1."""
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p          # 64비트 핸들 잘림 방지
        k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return -1.0
        return pmc.WorkingSetSize / 1e6
    except Exception:
        return -1.0


def pct(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


async def main(duration_s: float):
    tracemalloc.start()
    tb1 = TimedFake(1, (0.0, 0.0, 0.0), front=2.0, rear=2.0)
    tb2 = TimedFake(2, (0.0, 0.0, 0.0), front=2.0, rear=2.0)
    s1 = await serve(tb1.handler, "127.0.0.1", TB1_PORT)
    s2 = await serve(tb2.handler, "127.0.0.1", TB2_PORT)
    links = {"tb1": RosbridgeLink("tb1", f"ws://127.0.0.1:{TB1_PORT}", 1),
             "tb2": RosbridgeLink("tb2", f"ws://127.0.0.1:{TB2_PORT}", 2)}
    relay = MultiTurtleBotRelay(use_ai=False, links=links)
    relay_task = asyncio.create_task(relay.run(host="127.0.0.1", port=RELAY_PORT))
    await asyncio.sleep(1.0)

    tel_times, frames = [], 0
    probes = {}            # linear 값 → 송신 시각
    latencies = []
    violations = []        # (사유, 시각)
    guard = {"tb1_block_since": None, "meet_since": None}
    mem = []

    async with websockets.connect(f"ws://127.0.0.1:{RELAY_PORT}", max_size=None) as ws:
        async def reader():
            nonlocal frames
            async for msg in ws:
                if isinstance(msg, (bytes, bytearray)):
                    frames += 1
                elif '"telemetry"' in msg:
                    tel_times.append(time.perf_counter())

        async def send(obj):
            await ws.send(json.dumps(obj))

        reader_task = asyncio.create_task(reader())
        start = time.perf_counter()
        warm_mem_at = start + 10.0
        snap0 = None
        probe_k = 0
        cycles = 0
        last_cmd_idx = {"tb1": 0, "tb2": 0}

        def check_invariants(now):
            # 판정: 장애물·만남 구간(유예 후)에 실기로 나간 전진 지령이 있으면 위반
            for rid, fake in (("tb1", tb1), ("tb2", tb2)):
                new = fake.cmd_vel[last_cmd_idx[rid]:]
                new_t = fake.cmd_times[last_cmd_idx[rid]:]
                last_cmd_idx[rid] = len(fake.cmd_vel)
                for (lin, _), t in zip(new, new_t):
                    if lin <= 0:
                        continue
                    if rid == "tb1" and guard["tb1_block_since"] and t > guard["tb1_block_since"] + SETTLE_S:
                        violations.append(("tb1 forward while front 0.3m", round(t - start, 2)))
                    if guard["meet_since"] and t > guard["meet_since"] + SETTLE_S:
                        violations.append((f"{rid} forward while AGV meeting", round(t - start, 2)))

        while time.perf_counter() - start < duration_s:
            cycles += 1
            # ---- A: 수동 주행 + 지연 프로브 (0~3s)
            await send({"cmd": "SELECT_ROBOT", "robot": "tb1"})
            t_end = time.perf_counter() + 3.0
            while time.perf_counter() < t_end:
                probe_k = probe_k % 400 + 1
                lin = round(0.1 + probe_k * 0.0001, 4)      # 0.15 상한 아래 고유값
                probes[lin] = time.perf_counter()
                await send({"cmd": "TWIST", "robot": "tb1", "linear": lin, "angular": 0.0})
                await asyncio.sleep(TICK_S)
                check_invariants(time.perf_counter())
            # 지연: 프로브 값이 가짜 tb1에 처음 도착한 시각
            seen = {}
            for (l, _), t in zip(tb1.cmd_vel, tb1.cmd_times):
                if l in probes and l not in seen and t >= probes[l]:
                    seen[l] = t - probes[l]
            latencies += [v * 1000 for v in seen.values()]
            probes.clear()

            # ---- B: 전방 0.3m 장애물 + 전진 시도 (3~6s)
            tb1.front = 0.3
            guard["tb1_block_since"] = time.perf_counter()
            t_end = time.perf_counter() + 3.0
            while time.perf_counter() < t_end:
                await send({"cmd": "TWIST", "robot": "tb1", "linear": 0.1, "angular": 0.0})
                await asyncio.sleep(TICK_S)
                check_invariants(time.perf_counter())
            tb1.front = 2.0
            await asyncio.sleep(SETTLE_S + 0.2)
            check_invariants(time.perf_counter())
            guard["tb1_block_since"] = None

            # ---- C: 2대 AUTO + 0.8m 만남 (6~9s)
            await send({"cmd": "STOP", "robot": "tb1"})
            await send({"cmd": "RESET_POSE", "robot": "tb1", "x": 0.0, "z": 0.0, "yaw": 0.0})
            await send({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 3.0, "yaw": 180.0})
            await asyncio.sleep(0.3)
            for rid in ("tb1", "tb2"):
                await send({"cmd": "AUTO", "robot": rid, "enable": True})
            await asyncio.sleep(1.0)
            await send({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 0.8, "yaw": 180.0})
            guard["meet_since"] = time.perf_counter()
            t_end = time.perf_counter() + 1.5
            while time.perf_counter() < t_end:
                await asyncio.sleep(TICK_S)
                check_invariants(time.perf_counter())

            # ---- D: tb2 콕핏 진입 → 후진 비켜주기 → 정리 (9~12s)
            await send({"cmd": "SELECT_ROBOT", "robot": "tb2"})
            await send({"cmd": "TELEPORT", "mode": "FPV", "robot": "tb2"})
            t_end = time.perf_counter() + 1.0
            while time.perf_counter() < t_end:
                await send({"cmd": "TWIST", "robot": "tb2", "linear": -0.1, "angular": 0.0})
                await asyncio.sleep(TICK_S)
                check_invariants(time.perf_counter())
            await send({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 3.0, "yaw": 180.0})
            await asyncio.sleep(SETTLE_S + 0.2)
            check_invariants(time.perf_counter())
            guard["meet_since"] = None
            for rid in ("tb1", "tb2"):
                await send({"cmd": "STOP", "robot": rid})
            await send({"cmd": "TELEPORT", "mode": "GOD_VIEW", "robot": "tb2"})
            await asyncio.sleep(max(0.0, CYCLE_S - 3.0 - 3.5 - 2.8 - 2.0))

            now = time.perf_counter()
            if snap0 is None and now >= warm_mem_at:
                gc.collect()
                snap0 = tracemalloc.take_snapshot()
                mem.append((round(now - start), working_set_mb(), tracemalloc.get_traced_memory()[0] / 1e6))
            elif snap0 is not None:
                mem.append((round(now - start), working_set_mb(), tracemalloc.get_traced_memory()[0] / 1e6))

        elapsed = time.perf_counter() - start
        reader_task.cancel()

    gc.collect()
    snap1 = tracemalloc.take_snapshot()
    growth = snap1.compare_to(snap0, "lineno")[:5] if snap0 else []

    # cmd_vel 송신율: 1초 창별 개수
    def per_second(times):
        if not times:
            return []
        t0 = times[0]
        buckets = {}
        for t in times:
            buckets[int(t - t0)] = buckets.get(int(t - t0), 0) + 1
        full = [buckets.get(i, 0) for i in range(1, int(times[-1] - t0))]   # 처음·마지막 부분 창 제외
        return full

    tel_dt = [(b - a) * 1000 for a, b in zip(tel_times, tel_times[1:])]
    report = {
        "duration_s": round(elapsed, 1),
        "cycles": cycles,
        "telemetry": {
            "count": len(tel_times), "expected": int(elapsed * EXPECTED_HZ),
            "rate_hz": round(len(tel_times) / elapsed, 2),
            "interval_ms_p50": round(pct(tel_dt, 50), 1), "p95": round(pct(tel_dt, 95), 1),
            "p99": round(pct(tel_dt, 99), 1), "max": round(max(tel_dt), 1) if tel_dt else None,
            "gaps_over_150ms": sum(1 for d in tel_dt if d > 150),
        },
        "video_frames": {"count": frames, "rate_fps": round(frames / elapsed, 1)},
        "cmd_vel": {rid: {"count": len(f.cmd_times), "rate_hz": round(len(f.cmd_times) / elapsed, 2),
                          "min_per_s": min(per_second(f.cmd_times) or [0]),
                          "seconds_below_15": sum(1 for c in per_second(f.cmd_times) if c < 15)}
                    for rid, f in (("tb1", tb1), ("tb2", tb2))},
        "command_latency_ms": {"samples": len(latencies), "p50": round(pct(latencies, 50), 1),
                               "p95": round(pct(latencies, 95), 1), "max": round(max(latencies), 1) if latencies else None},
        "memory": {"samples(t_s, working_set_MB, traced_MB)": [(t, round(w, 1), round(tr, 2)) for t, w, tr in mem[::max(1, len(mem) // 8)]],
                   "working_set_delta_MB": round(mem[-1][1] - mem[0][1], 1) if len(mem) > 1 else None,
                   "traced_delta_MB": round(mem[-1][2] - mem[0][2], 2) if len(mem) > 1 else None,
                   "top_growth": [str(g) for g in growth]},
        "safety_violations": {"count": len(violations), "first": violations[:5]},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    relay_task.cancel()
    try:
        await relay_task
    except asyncio.CancelledError:
        pass
    s1.close()
    s2.close()
    ok = not violations and report["telemetry"]["gaps_over_150ms"] == 0
    print("SOAK TEST", "OK" if ok else "ATTENTION")


if __name__ == "__main__":
    asyncio.run(main(float(sys.argv[1]) if len(sys.argv) > 1 else 300.0))
