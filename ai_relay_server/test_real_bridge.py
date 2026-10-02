"""
T-012 실기체 브리지 E2E 검증 (하드웨어 불필요)
- 가짜 rosbridge 서버 2대(tb1=ROS1, tb2=ROS2)가 odom/scan 발행, cmd_vel 기록.
- 릴레이를 in-process로 띄우고 Unity 역할 클라이언트로 TWIST/SELECT_ROBOT 송신.
실행: python ai_relay_server/test_real_bridge.py
"""

import asyncio
import json
import math
import sys

import websockets
from websockets.server import serve

from ros2_multi_turtlebot_relay import (
    AUTO_AVOID_SPEED, AUTO_AVOID_TIMEOUT_S, AUTO_CRUISE_SPEED, AUTO_MAX_TURN,
    LIDAR_REAR_GUARD_M, REAL_MAX_LINEAR_DEFAULT, SPAWN_POSES, MultiTurtleBotRelay, odom_to_unity,
)
from escape_planner import ScanData, _valid_points, plan_escape
from path_planner import can_pivot, pivot_path, recommend
from rosbridge_link import RosbridgeLink, sector_min_range

TB1_PORT, TB2_PORT, RELAY_PORT = 19191, 19192, 19193
TICK_S = 0.05
TB2_ODOM = (0.5, 0.2, math.pi / 2)   # ROS x, y, yaw


class FakeRosbridge:
    def __init__(self, ros_version: int, odom, front: float, rear: float):
        self.ros_version = ros_version
        self.odom = odom
        self.front, self.rear = front, rear
        self.scan_override = None   # 360개 range 직접 지정 (막다른 길 등)
        self.publishing = True
        self.ops = []
        self.cmd_vel = []

    def _odom_msg(self):
        x, y, yaw = self.odom
        q = {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}
        return {"pose": {"pose": {"position": {"x": x, "y": y, "z": 0.0}, "orientation": q}}}

    def _scan_msg(self):
        # LDS-01 형식: 0~359도, 1도 간격, index 0 = 전방. 무효값 0.0·None 섞음.
        if self.scan_override is not None:
            return {"ranges": list(self.scan_override), "angle_min": 0.0, "angle_increment": math.radians(1),
                    "range_min": 0.12, "range_max": 3.5}
        ranges = [2.0] * 360
        for i in list(range(0, 10)) + list(range(350, 360)):
            ranges[i] = self.front
        for i in range(170, 190):
            ranges[i] = self.rear
        ranges[45], ranges[300] = 0.0, None
        return {"ranges": ranges, "angle_min": 0.0, "angle_increment": math.radians(1),
                "range_min": 0.12, "range_max": 3.5}

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
                self.ops.append((data["op"], data.get("topic"), data.get("type")))
                if data["op"] == "publish" and data["topic"] == "/cmd_vel":
                    self.cmd_vel.append((data["msg"]["linear"]["x"], data["msg"]["angular"]["z"]))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            task.cancel()


def check(cond: bool, label: str):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        sys.exit(1)


async def telemetry(ws, window_s: float = 0.4):
    """수신 버퍼의 지난 메시지를 버리고 window_s 동안 받은 마지막 텔레메트리 반환."""
    latest = None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + window_s
    while latest is None or loop.time() < deadline:
        msg = await ws.recv()
        if isinstance(msg, str):
            data = json.loads(msg)
            if data.get("type") == "telemetry":
                latest = data
    return latest


async def drive(ws, robot: str, lin: float, ang: float, seconds: float):
    for _ in range(int(seconds / TICK_S)):
        await ws.send(json.dumps({"cmd": "TWIST", "robot": robot, "linear": lin, "angular": ang}))
        await asyncio.sleep(TICK_S)


async def main():
    print("[0] 좌표 변환 단위 검증")
    x, z, yaw = odom_to_unity(1.0, 0.0, 0.0, SPAWN_POSES["tb2"])
    check(abs(x - 1.8) < 1e-6 and abs(z - 4.0) < 1e-6 and abs(yaw - 180.0) < 1e-6,
          "tb2 스폰(180°)에서 odom 전방 1m → Unity z 감소")
    x, z, yaw = odom_to_unity(0.0, 1.0, math.pi / 2, (0.0, 0.0, 0.0))
    check(abs(x + 1.0) < 1e-6 and abs(z) < 1e-6 and abs(yaw - 270.0) < 1e-6,
          "odom 좌측 1m·좌회전 90° → Unity x=-1, yaw=270")

    print("[0b] 탈출 경로 플래너 단위 검증")
    def scan_with(blocked_deg, near=0.3, far=2.0):
        r = [near if (d in blocked_deg) else far for d in range(360)]
        return ScanData(r, 0.0, math.radians(1), 0.12, 3.5)
    sug = plan_escape(scan_with(set(range(0, 360))))
    check(sug is None, "사방 막힘 → 추천 없음")
    sug = plan_escape(scan_with(set()))
    check(sug is not None and abs(sug.heading_deg) < 1e-6, "사방 열림 → 직진 추천")
    left_open = set(range(0, 360)) - set(range(45, 136))      # 좌측 45~135° 열림 (0.3m 거리 20° 틈은 10cm라 로봇 통과 불가)
    sug = plan_escape(scan_with(left_open))
    check(sug is not None and 55 <= sug.heading_deg <= 135, f"좌측만 열림 → 좌 {sug.heading_deg if sug else None}° (틈 안에서 최소 회전)")

    print("[0d] LiDAR 무효값 0.0 처리 (ROS 1 LD08: range_min=0.0)")
    ld08 = [0.0 if d % 7 == 0 else 1.0 for d in range(360)]
    fm = sector_min_range(ld08, 0.0, math.radians(1), 0.0, 100.0, 0.0, math.radians(30))
    check(abs(fm - 1.0) < 1e-6, f"0.0 측정 무시 → 전방 {fm}m (0m 오판 없음)")
    pts0 = _valid_points(ScanData(ld08, 0.0, math.radians(1), 0.0, 100.0))
    check(len(pts0) and (pts0 ** 2).sum(axis=1).min() > 0.5, "경로 계산용 점에서도 0.0 제외")

    print("[0c] 제자리 선회 후 직진 추천 단위 검증 (T-024)")
    pts = _valid_points(scan_with(left_open))
    best, _ = recommend(pts)
    piv = pivot_path(pts, sug.heading_rad) if sug else None
    check(best is None and piv is not None and piv.level != "RED",
          f"전방 0.3m 막힘·좌측 열림 → 전진 후보 없음, 선회 후 직진 {piv.level if piv else None}")
    end = piv.points[-1] if piv is not None else (0.0, 0.0)
    check(end[1] > 0.8, f"선회 후 직진 끝점이 좌측 (y={end[1]:.2f}m)")
    tight = _valid_points(ScanData([0.14] * 360, 0.0, math.radians(1), 0.12, 3.5))
    check(not can_pivot(tight) and pivot_path(tight, 0.0) is None, "둘레 0.14m 포위 → 선회 공간 없음")

    tb1 = FakeRosbridge(1, (0.0, 0.0, 0.0), front=2.0, rear=2.0)
    tb2 = FakeRosbridge(2, TB2_ODOM, front=2.0, rear=2.0)
    s1 = await serve(tb1.handler, "127.0.0.1", TB1_PORT)
    s2 = await serve(tb2.handler, "127.0.0.1", TB2_PORT)
    links = {
        "tb1": RosbridgeLink("tb1", f"ws://127.0.0.1:{TB1_PORT}", 1),
        "tb2": RosbridgeLink("tb2", f"ws://127.0.0.1:{TB2_PORT}", 2),
    }
    relay = MultiTurtleBotRelay(use_ai=False, links=links)
    relay_task = asyncio.create_task(relay.run(host="127.0.0.1", port=RELAY_PORT))
    await asyncio.sleep(1.0)

    print("[1] rosbridge 핸드셰이크")
    check(("advertise", "/cmd_vel", "geometry_msgs/Twist") in tb1.ops, "tb1 ROS1 타입으로 cmd_vel advertise")
    check(("subscribe", "/odom", "nav_msgs/msg/Odometry") in tb2.ops, "tb2 ROS2 타입으로 odom subscribe")

    async with websockets.connect(f"ws://127.0.0.1:{RELAY_PORT}", max_size=None) as ws:
        print("[2] 텔레메트리 실기 반영")
        t = await telemetry(ws)
        ex, ez, eyaw = odom_to_unity(*TB2_ODOM, SPAWN_POSES["tb2"])
        r2 = t["tb2"]
        check(r2["source"] == "real" and r2["online"], "tb2 source=real, online=true")
        check(abs(r2["x"] - ex) < 0.01 and abs(r2["z"] - ez) < 0.01 and abs(r2["yaw"] - eyaw) < 0.1,
              f"tb2 포즈 = odom 변환값 ({r2['x']}, {r2['z']}, {r2['yaw']})")
        check(abs(r2["front_min"] - 2.0) < 1e-3 and abs(r2["rear_min"] - 2.0) < 1e-3,
              "front_min/rear_min 섹터 계산 (무효값 0.0·None 제외)")

        print("[3] TB2 텔레옵 → cmd_vel (속도 상한)")
        await ws.send(json.dumps({"cmd": "SELECT_ROBOT", "robot": "tb2"}))
        await asyncio.sleep(0.2)
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", 0.22, 0.5, 0.5)
        check(any(abs(l - REAL_MAX_LINEAR_DEFAULT) < 1e-6 and abs(a - 0.5) < 1e-6 for l, a in tb2.cmd_vel),
              f"0.22 지령 → {REAL_MAX_LINEAR_DEFAULT} m/s로 제한되어 송신")

        print("[4] 워치독 0.5s → 정지 지령")
        await asyncio.sleep(0.8)
        check(tb2.cmd_vel[-1] == (0.0, 0.0), "입력 중단 후 마지막 cmd_vel = 0")

        print("[5] LiDAR 전방 가드")
        tb2.front = 0.25
        await asyncio.sleep(0.3)
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", 0.1, 0.0, 0.4)
        check(all(l == 0.0 for l, _ in tb2.cmd_vel), "전방 0.25m → 전진 지령 0")
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", -0.1, 0.0, 0.4)
        check(any(l < 0 for l, _ in tb2.cmd_vel), "후진은 허용")
        tb2.front = 2.0

        print("[6] odom 끊김 → offline·정지")
        tb2.publishing = False
        await asyncio.sleep(0.8)
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", 0.1, 0.0, 0.3)
        t = await telemetry(ws)
        check(not t["tb2"]["online"], "tb2 online=false")
        check(all(c == (0.0, 0.0) for c in tb2.cmd_vel), "offline 동안 지령 0")
        tb2.publishing = True

        print("[7] TB1 LiDAR 인터록 → 정지·알림 (자동 후진·회전 없음) + 추천 탈출 경로 (T-015)")
        await ws.send(json.dumps({"cmd": "SELECT_ROBOT", "robot": "tb1"}))
        await asyncio.sleep(0.2)
        tb1.front = 0.3
        await asyncio.sleep(0.4)
        tb1.cmd_vel.clear()
        await asyncio.sleep(2.5)   # 구 Escape라면 이 사이 BACKUP·ROTATE 발생
        t = await telemetry(ws)
        sf = t["safety"]
        check(sf["interlock"] and sf["escape"] == "STOP", f"escape={sf['escape']}")
        check(sf["reason"].startswith("LIDAR OBSTACLE"), f"reason='{sf['reason']}'")
        check(all(c == (0.0, 0.0) for c in tb1.cmd_vel), "자동 후진·회전 지령 없음 (2.5s 동안 전부 0)")
        check(sf["escape_clearance"] >= 0.5 and 25 <= abs(sf["escape_heading"]) <= 60,
              f"추천 탈출 {sf['escape_heading']}° / {sf['escape_clearance']}m (전방만 막힘 → 비스듬히)")
        tb1.cmd_vel.clear()
        await drive(ws, "tb1", 0.1, 0.0, 0.4)
        check(all(l == 0.0 for l, _ in tb1.cmd_vel), "STOP 중 전진 입력 차단")
        tb1.cmd_vel.clear()
        await drive(ws, "tb1", -0.1, 0.6, 0.4)
        check(any(l < 0 and a > 0 for l, a in tb1.cmd_vel), "STOP 중 수동 후진·회전 허용")
        tb1.rear = LIDAR_REAR_GUARD_M - 0.05   # range_min(0.12) 초과 유효값
        await asyncio.sleep(0.4)
        tb1.cmd_vel.clear()
        await drive(ws, "tb1", -0.1, 0.0, 0.4)
        check(all(l == 0.0 for l, _ in tb1.cmd_vel), "후방 장애물 → 수동 후진도 차단")
        tb1.rear = 2.0
        tb1.front = 2.0
        await asyncio.sleep(0.5)
        t = await telemetry(ws)
        check(t["safety"]["escape"] == "IDLE" and t["safety"]["reason"] == "", "장애물 제거 → IDLE, reason 비움")


        print("[9] 자율 배회 AUTO (T-016)")
        async def auto_cmd(enable=True):
            await ws.send(json.dumps({"cmd": "AUTO", "robot": "tb1", "enable": enable}))
            await asyncio.sleep(0.3)

        async def last_cmds(seconds=0.4):
            tb1.cmd_vel.clear()
            await asyncio.sleep(seconds)
            return list(tb1.cmd_vel)

        tb1.odom = (0.0, 0.0, 0.0)
        await asyncio.sleep(0.3)
        await auto_cmd(True)
        t = await telemetry(ws)
        check(t["mode"] == "AUTO" and t["auto_state"] == "CRUISE", f"AUTO 진입 → {t['mode']}/{t['auto_state']}")
        cmds = await last_cmds(1.0)   # 조작자 무입력 1s: 워치독이 멈추면 안 됨
        check(cmds and all(abs(l - AUTO_CRUISE_SPEED) < 1e-6 and a == 0.0 for l, a in cmds),
              f"CRUISE {AUTO_CRUISE_SPEED} m/s 직진 유지 (무입력 1s, 워치독 미적용)")

        tb1.front = 0.5   # 0.35~0.6m: 회피 조향
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        cmds = await last_cmds()
        check(t["auto_state"] == "AVOID", f"전방 0.5m → {t['auto_state']}")
        check(cmds and all(a != 0.0 and l in (0.0, AUTO_AVOID_SPEED) for l, a in cmds), "AVOID: 추천 방향 조향")

        tb1.front = 0.3   # 인터록 → STUCK
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        cmds = await last_cmds()
        check(t["auto_state"] == "STUCK" and t["mode"] == "AUTO", f"전방 0.3m → {t['mode']}/{t['auto_state']}")
        check(all(c == (0.0, 0.0) for c in cmds), "STUCK: 정지")
        tb1.front = 2.0
        await asyncio.sleep(0.5)
        t = await telemetry(ws)
        cmds = await last_cmds()
        check(t["auto_state"] == "STUCK" and t["safety"]["reason"].startswith("AUTO STUCK"),
              f"장애물 제거돼도 자동 재개 없음, 알림 유지: '{t['safety']['reason']}'")
        check(all(c == (0.0, 0.0) for c in cmds), "STUCK 유지 중 정지")

        await auto_cmd(True)   # R / 퀘스트 Y
        t = await telemetry(ws)
        check(t["auto_state"] == "CRUISE", "AUTO 재개 → CRUISE")

        await drive(ws, "tb1", 0.05, 0.0, 0.2)   # 조작자 개입
        t = await telemetry(ws)
        check(t["mode"] == "MANUAL" and t["auto_state"] == "OFF", "WASD/썸스틱 입력 → 즉시 MANUAL")

        print("[9b] 배회 구역 1.5m 복귀")
        await auto_cmd(True)
        tb1.odom = (2.0, 0.0, 0.0)   # 중심(0,0)에서 2.0m, 중심은 등 뒤
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        cmds = await last_cmds()
        check(t["auto_state"] == "RETURN", f"구역 이탈 → {t['auto_state']}")
        check(cmds and all(l == 0.0 and abs(abs(a) - AUTO_MAX_TURN) < 1e-6 for l, a in cmds),
              "중심이 뒤쪽 → 제자리 최대 회전")
        tb1.odom = (1.0, 0.0, math.pi)   # 중심 방향, 반경 70% 안
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        check(t["auto_state"] == "CRUISE", "구역 안 복귀 → CRUISE")
        tb1.odom = (0.0, 0.0, 0.0)

        print("[9c] 막다른 길 → STUCK")
        tb1.scan_override = [0.45] * 360   # 사방 0.45m: 인터록(0.35) 미만 아님, 통과 여유(0.5) 없음
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        check(t["auto_state"] == "STUCK" and "dead end" in t["safety"]["reason"], f"막다른 길: '{t['safety']['reason']}'")
        check(not t["safety"]["interlock"], "인터록 없이도 STUCK 알림")
        tb1.scan_override = None
        await asyncio.sleep(0.4)   # 정상 스캔이 릴레이에 도달한 뒤 재개

        print("[9d] AVOID 장기화 → STUCK (맴돌기 방지)")
        await auto_cmd(True)
        tb1.front = 0.5
        await asyncio.sleep(AUTO_AVOID_TIMEOUT_S + 0.6)
        t = await telemetry(ws)
        check(t["auto_state"] == "STUCK" and "avoid timeout" in t["safety"]["reason"], f"'{t['safety']['reason']}'")
        tb1.front = 2.0

        print("[9e] STOP → MANUAL")
        await auto_cmd(True)
        await ws.send(json.dumps({"cmd": "STOP", "robot": "tb1"}))
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        check(t["mode"] == "MANUAL", "STOP 명령 → MANUAL")
        await auto_cmd(True)   # 연결 해제 시 해제되는지 [8]에서 확인


        print("[10] 경로 추천·LiDAR 점 텔레메트리 + 위치 원점 재설정 (T-019)")
        await ws.send(json.dumps({"cmd": "STOP", "robot": "tb1"}))   # MANUAL·정지 상태에서 시작
        tb1.odom = (0.0, 0.0, 0.0)
        tb1.front, tb1.rear, tb1.scan_override = 2.0, 2.0, None
        await asyncio.sleep(0.5)
        t = await telemetry(ws)
        path = t["path"]
        check(path["recommended_level"] == "GREEN" and len(path["recommended"]) >= 4, f"사방 2m 열림 → 추천 {path['recommended_level']}")
        x0, z0 = path["recommended"][0], path["recommended"][1]
        check(abs(x0) < 0.02 and 0.0 < z0 < 0.1, f"추천 궤적 시작점이 로봇 앞 (+z): ({x0}, {z0})")
        check(0 < len(t["scan"]) <= 360 and len(t["scan"]) % 2 == 0, f"LiDAR 점 {len(t['scan']) // 2}개 (≤180)")
        check(path["predicted"] == [] and path["predicted_level"] == "NONE", "정지 중 예상 궤적 없음")
        await ws.send(json.dumps({"cmd": "TWIST", "robot": "tb1", "linear": 0.1, "angular": 0.5}))
        t = await telemetry(ws, 0.15)
        pred = t["path"]["predicted"]
        check(len(pred) >= 4 and pred[-2] < 0, f"좌회전 지령 → 예상 궤적 끝 x<0 (Unity 좌측): {pred[-2:]}")
        await asyncio.sleep(0.7)   # 워치독으로 정지

        tb1.odom = (1.0, 0.5, 0.3)
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        check(abs(t["tb1"]["x"]) > 0.3 or abs(t["tb1"]["z"]) > 0.3, "재설정 전: odom 이동만큼 스폰에서 벗어남")
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb1"}))
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        r1 = t["tb1"]
        check(abs(r1["x"]) < 0.01 and abs(r1["z"]) < 0.01 and min(r1["yaw"], 360 - r1["yaw"]) < 0.5,
              f"RESET_POSE → 스폰 포즈 ({r1['x']}, {r1['z']}, {r1['yaw']})")
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb1", "x": 2.0, "z": 3.0, "yaw": 90.0}))
        await asyncio.sleep(0.3)
        tb1.odom = (1.0 + 0.5 * math.cos(0.3), 0.5 + 0.5 * math.sin(0.3), 0.3)   # odom 헤딩으로 0.5m 전진
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        r1 = t["tb1"]
        check(abs(r1["x"] - 2.5) < 0.02 and abs(r1["z"] - 3.0) < 0.02 and abs(r1["yaw"] - 90.0) < 0.5,
              f"기준 (2,3,90°) 재설정 후 0.5m 전진 → ({r1['x']}, {r1['z']}, {r1['yaw']}) ≈ (2.5, 3.0, 90)")
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2"}))   # tb2는 sim이 아닌 real 링크 → 허용
        await asyncio.sleep(0.2)

        print("[10b] 전진 막힘 → 제자리 선회 후 직진 추천 텔레메트리 (T-024)")
        tb1.scan_override = [2.0 if 45 <= d <= 135 else 0.3 for d in range(360)]   # 좌측만 열림
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        path = t["path"]
        check(path["recommended_mode"] == "PIVOT" and path["pivot_deg"] > 0 and len(path["pivot_points"]) >= 4,
              f"mode={path['recommended_mode']} 선회 {'좌' if path['pivot_deg'] > 0 else '우'}, 직진 점 {len(path['pivot_points']) // 2}개")
        check(path["recommended"] == [] and path["pivot_level"] in ("GREEN", "YELLOW"), f"전진 추천 없음, 선회 경로 {path['pivot_level']}")
        tb1.scan_override = None
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        check(t["path"]["recommended_mode"] == "FORWARD" and t["path"]["pivot_points"] == [], "장애물 제거 → FORWARD, 선회 경로 비움")
        await auto_cmd(True)   # [8]에서 연결 해제 시 AUTO 해제 확인용


        print("[11] TC-02 tb1↔tb2 안전거리 1.0m 인터록")
        await ws.send(json.dumps({"cmd": "STOP", "robot": "tb1"}))
        tb1.front, tb1.rear, tb1.scan_override = 2.0, 2.0, None   # LiDAR 원인 배제 → 거리 인터록만 검사
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        tx, tz = t["tb1"]["x"], t["tb1"]["z"]
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2", "x": tx, "z": tz + 0.8, "yaw": 180.0}))
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        d = math.hypot(t["tb2"]["x"] - t["tb1"]["x"], t["tb2"]["z"] - t["tb1"]["z"])
        check(t["safety"]["interlock"] and "TB2" in t["safety"]["reason"], f"거리 {d:.2f}m → 인터록 '{t['safety']['reason']}'")
        tb1.cmd_vel.clear()
        await drive(ws, "tb1", 0.1, 0.0, 0.4)
        check(all(l == 0.0 for l, _ in tb1.cmd_vel), "1.0m 이내 → tb1 전진 차단")
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2", "x": tx, "z": tz + 3.0, "yaw": 180.0}))
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        check(not t["safety"]["interlock"], "3.0m로 벌어짐 → 인터록 해제")

        print("[12] 2대 AUTO → 만남 1.0m → 둘 다 정지 → 한 대 콕핏 진입·비켜주기 → 재개 (T-025)")
        async def auto_for(robot, enable=True):
            await ws.send(json.dumps({"cmd": "AUTO", "robot": robot, "enable": enable}))
            await asyncio.sleep(0.3)
        for rid in ("tb1", "tb2"):
            await ws.send(json.dumps({"cmd": "STOP", "robot": rid}))
        tb1.front = tb1.rear = tb2.front = tb2.rear = 2.0
        tb1.scan_override = tb2.scan_override = None
        await ws.send(json.dumps({"cmd": "SELECT_ROBOT", "robot": "tb1"}))
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb1", "x": 0.0, "z": 0.0, "yaw": 0.0}))
        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 3.0, "yaw": 180.0}))
        await asyncio.sleep(0.3)
        await auto_for("tb1")
        await auto_for("tb2")
        t = await telemetry(ws)
        check(t["tb1"]["mode"] == "AUTO" and t["tb2"]["mode"] == "AUTO" and t["tb2"]["auto_state"] == "CRUISE",
              f"두 대 동시 AUTO: tb1 {t['tb1']['auto_state']} / tb2 {t['tb2']['auto_state']}")
        tb2.cmd_vel.clear()
        await asyncio.sleep(0.6)   # tb2는 조종 권한 없음 → AUTO만으로 주행 (워치독 미적용)
        check(tb2.cmd_vel and all(abs(l - AUTO_CRUISE_SPEED) < 1e-6 for l, _ in tb2.cmd_vel), "권한 없는 tb2도 AUTO 직진 송신")

        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 0.8, "yaw": 180.0}))   # 마주 보고 0.8m
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        check(t["tb1"]["auto_state"] == "STUCK" and t["tb2"]["auto_state"] == "STUCK",
              f"만남 0.8m → 둘 다 STUCK ({t['tb1']['auto_state']}/{t['tb2']['auto_state']})")
        check(t["tb1"]["alert"] and t["tb2"]["alert"] and "TB1" in t["tb2"]["stop_reason"],
              f"양쪽 알림: tb2 '{t['tb2']['stop_reason']}'")
        tb1.cmd_vel.clear(); tb2.cmd_vel.clear()
        await asyncio.sleep(0.3)
        check(all(c == (0.0, 0.0) for c in tb1.cmd_vel + tb2.cmd_vel), "둘 다 정지 지령")

        await ws.send(json.dumps({"cmd": "SELECT_ROBOT", "robot": "tb2"}))
        await ws.send(json.dumps({"cmd": "TELEPORT", "mode": "FPV", "robot": "tb2"}))
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        check(t["tb2"]["mode"] == "MANUAL" and t["tb1"]["mode"] == "AUTO" and t["tb1"]["auto_state"] == "STUCK",
              "tb2 콕핏 진입 → tb2만 MANUAL, tb1은 STUCK 유지")
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", 0.1, 0.0, 0.4)
        check(all(l == 0.0 for l, _ in tb2.cmd_vel), "1.0m 안: tb2 전진 차단")
        tb2.cmd_vel.clear()
        await drive(ws, "tb2", -0.1, 0.0, 0.4)
        check(any(l < 0 for l, _ in tb2.cmd_vel), "후진으로 비켜주기 허용")
        await asyncio.sleep(0.7)

        await ws.send(json.dumps({"cmd": "RESET_POSE", "robot": "tb2", "x": 0.0, "z": 3.0, "yaw": 180.0}))   # 비켜준 뒤
        await asyncio.sleep(0.4)
        t = await telemetry(ws)
        check(not t["tb2"]["alert"] and t["tb1"]["auto_state"] == "STUCK", "거리 확보 → 알림 해제, tb1 자동 재개 없음")
        await auto_for("tb1")
        await auto_for("tb2")
        t = await telemetry(ws)
        moving = ("CRUISE", "RETURN", "AVOID")   # tb1은 이전 시험의 배회 중심 밖이면 RETURN
        check(t["tb1"]["auto_state"] in moving and t["tb2"]["auto_state"] in moving,
              f"Y/R로 각각 AUTO 재개 ({t['tb1']['auto_state']}/{t['tb2']['auto_state']})")
        await ws.send(json.dumps({"cmd": "TELEPORT", "mode": "FPV", "robot": "tb1"}))
        await asyncio.sleep(0.3)
        t = await telemetry(ws)
        check(t["tb1"]["mode"] == "MANUAL" and t["tb2"]["mode"] == "AUTO", "tb1 콕핏 진입 → tb1만 MANUAL")
        await auto_for("tb2", False)
        await ws.send(json.dumps({"cmd": "SELECT_ROBOT", "robot": "tb1"}))
        await asyncio.sleep(0.2)
        await auto_cmd(True)   # [8]에서 연결 해제 시 AUTO 해제 확인용

    print("[8] 클라이언트 이탈·릴레이 종료 → 정지 지령")
    await asyncio.sleep(0.3)
    check(relay.auto_state == "OFF", "클라이언트 이탈 → AUTO 해제")
    check(tb1.cmd_vel[-1] == (0.0, 0.0) and tb2.cmd_vel[-1] == (0.0, 0.0), "양쪽 마지막 지령 0")
    relay_task.cancel()
    try:
        await relay_task
    except asyncio.CancelledError:
        pass
    s1.close()
    s2.close()
    print("T-012 REAL BRIDGE TEST OK")


if __name__ == "__main__":
    asyncio.run(main())
