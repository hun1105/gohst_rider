"""
Unity 시연 장면 자동 촬영 (사람 개입 없음, 실물 로봇 불필요).

구성 (모두 이 PC 안에서 실행):
  - 가상 rosbridge 로봇 2대 (tb1=ROS1, tb2=ROS2): cmd_vel을 적분해 odom을 내고, 다른 로봇·가상 장애물까지 LiDAR 거리를 계산해 scan 발행
  - 릴레이 (ai_relay_server/ros2_multi_turtlebot_relay.py) — 실제 판단 코드 그대로
  - Unity 에디터 (DemoCapture.Play 로 자동 Play) — 키 입력(R, Tab, WASD, Esc)은 이 스크립트가 보냄
  - 녹화 tools/record_screen.py

장면 (docs/VIDEO_SCRIPT_3MIN.md 2~5막):
  s2  R → 두 대 직진 → 서로 가까워지면 둘 다 정지
  s3  tb1만 AUTO → 앞에 장애물(작업자 역) 등장 → 정지·경로 표시
  s4  Tab 콕핏 → 후진·선회·전진 탈출 → Esc 복귀 → Shift+R 재개
  s5  주행 중 Play 중지 (전체 화면 녹화)

실행: python tools/demo_capture.py            (결과: video/unity_s*_sim.mp4)
"""

import asyncio
import ctypes
import json
import math
import os
import subprocess
import sys
import time
from ctypes import wintypes

import websockets
from websockets.server import serve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ai_relay_server"))
from ros2_multi_turtlebot_relay import SPAWN_POSES, odom_to_unity  # noqa: E402

UNITY_EXE = r"C:\Program Files\Unity\Hub\Editor\6000.0.84f1\Editor\Unity.exe"
PROJECT = os.path.join(ROOT, "PhysicalAI_AGV_VR")
VIDEO_DIR = os.path.join(ROOT, "video")
RELAY_LOG = os.path.join(VIDEO_DIR, "demo_relay.log")
UNITY_WINDOW = "Unity 6"

TB1_PORT, TB2_PORT, RELAY_PORT = 19391, 19392, 9090
TICK_S = 0.05                 # 가상 로봇 odom/scan 발행 주기 (20 Hz)
CMD_TIMEOUT_S = 0.5           # 마지막 cmd_vel 이후 이 시간 지나면 정지
ROBOT_RADIUS_M = 0.09         # Burger 외곽 근사 (LiDAR가 보는 상대 로봇 원)
WORKER_RADIUS_M = 0.15        # 가상 장애물(작업자 역) 반경
SCAN_MAX_M = 3.5
UNITY_CONNECT_TIMEOUT_S = 900


# ===================== 가상 세계 =====================
class SimRobot:
    def __init__(self, rid: str, ros_version: int):
        self.rid, self.ros_version = rid, ros_version
        self.odom = [0.0, 0.0, 0.0]     # ROS x, y, yaw(rad) — 각자 켠 자리 기준
        self.cmd = (0.0, 0.0, 0.0)      # linear, angular, 수신 시각

    def world(self):
        return odom_to_unity(self.odom[0], self.odom[1], self.odom[2], SPAWN_POSES[self.rid])

    def step(self, dt: float):
        v, w, t = self.cmd
        if time.monotonic() - t > CMD_TIMEOUT_S:
            v, w = 0.0, 0.0
        x, y, yaw = self.odom
        yaw += w * dt
        self.odom = [x + v * math.cos(yaw) * dt, y + v * math.sin(yaw) * dt, yaw]


class World:
    def __init__(self):
        self.robots = {"tb1": SimRobot("tb1", 1), "tb2": SimRobot("tb2", 2)}
        self.obstacles: list[tuple[float, float, float]] = []   # Unity x, z, 반경

    def reset(self, tb2_odom=(0.0, 0.0, 0.0)):
        self.robots["tb1"].odom = [0.0, 0.0, 0.0]
        self.robots["tb2"].odom = list(tb2_odom)
        for r in self.robots.values():
            r.cmd = (0.0, 0.0, 0.0)
        self.obstacles = []

    def scan(self, rid: str) -> list[float]:
        ux, uz, uyaw = self.robots[rid].world()
        circles = list(self.obstacles)
        for other, r in self.robots.items():
            if other != rid:
                ox, oz, _ = r.world()
                circles.append((ox, oz, ROBOT_RADIUS_M))
        ranges = []
        for a in range(360):          # index 0 = 전방, 반시계 증가 (ROS)
            yaw = math.radians(uyaw - a)
            dx, dz = math.sin(yaw), math.cos(yaw)
            best = SCAN_MAX_M
            for cx, cz, rad in circles:
                px, pz = cx - ux, cz - uz
                proj = px * dx + pz * dz
                if proj <= 0:
                    continue
                d2 = px * px + pz * pz - proj * proj
                if d2 > rad * rad:
                    continue
                hit = proj - math.sqrt(rad * rad - d2)
                if 0 < hit < best:
                    best = hit
            ranges.append(round(best, 3))
        return ranges

    def ahead(self, rid: str, dist: float):
        ux, uz, uyaw = self.robots[rid].world()
        return ux + dist * math.sin(math.radians(uyaw)), uz + dist * math.cos(math.radians(uyaw))


WORLD = World()


async def rosbridge_handler(ws, rid: str):
    robot = WORLD.robots[rid]

    async def pump():
        while True:
            x, y, yaw = robot.odom
            q = {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}
            await ws.send(json.dumps({"op": "publish", "topic": "/odom",
                                      "msg": {"pose": {"pose": {"position": {"x": x, "y": y, "z": 0.0}, "orientation": q}}}}))
            await ws.send(json.dumps({"op": "publish", "topic": "/scan",
                                      "msg": {"ranges": WORLD.scan(rid), "angle_min": 0.0, "angle_increment": math.radians(1),
                                              "range_min": 0.12, "range_max": SCAN_MAX_M}}))
            await asyncio.sleep(TICK_S)

    task = asyncio.create_task(pump())
    try:
        async for raw in ws:
            data = json.loads(raw)
            if data.get("op") == "publish" and data.get("topic", "").endswith("/cmd_vel"):
                m = data["msg"]
                robot.cmd = (float(m["linear"]["x"]), float(m["angular"]["z"]), time.monotonic())
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        task.cancel()


async def physics():
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK_S)
        now = time.monotonic()
        for r in WORLD.robots.values():
            r.step(now - last)
        last = now


# ===================== 릴레이 =====================
class Relay:
    def __init__(self):
        self.proc = None

    def start(self):
        log = open(RELAY_LOG, "a", encoding="utf-8")
        log.write(f"\n===== relay start {time.ctime()} =====\n")
        log.flush()
        self.proc = subprocess.Popen(
            [sys.executable, "ros2_multi_turtlebot_relay.py", "--port", str(RELAY_PORT), "--no-ai", "--no-log", "--real-patrol",
             "--tb1-url", f"ws://127.0.0.1:{TB1_PORT}", "--tb1-ros", "1",
             "--tb2-url", f"ws://127.0.0.1:{TB2_PORT}", "--tb2-ros", "2"],
            cwd=os.path.join(ROOT, "ai_relay_server"), stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


def log_size() -> int:
    return os.path.getsize(RELAY_LOG) if os.path.exists(RELAY_LOG) else 0


async def wait_unity_connected(since: int, timeout: float):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        with open(RELAY_LOG, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(since)
            if "VR Client connected" in f.read():
                return True
        await asyncio.sleep(1.0)
    return False


# ===================== 키·마우스 입력 (Windows SendInput) =====================
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
SC = {"R": 0x13, "TAB": 0x0F, "W": 0x11, "A": 0x1E, "S": 0x1F, "D": 0x20, "ESC": 0x01, "LSHIFT": 0x2A, "LCTRL": 0x1D, "P": 0x19, "SPACE": 0x39, "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "Q": 0x10, "E": 0x12}
KEYEVENTF_SCANCODE, KEYEVENTF_KEYUP = 0x0008, 0x0002
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x0002, 0x0004, 0x8000


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(inp: INPUT):
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def key(name: str, up: bool = False):
    inp = INPUT(type=1)
    inp.u.ki = KEYBDINPUT(0, SC[name], KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0), 0, None)
    _send(inp)


async def tap(name: str, mod: str | None = None):
    if mod:
        key(mod)
        await asyncio.sleep(0.05)
    key(name)
    await asyncio.sleep(0.08)
    key(name, up=True)
    if mod:
        await asyncio.sleep(0.05)
        key(mod, up=True)


async def hold(name: str, seconds: float):
    key(name)
    await asyncio.sleep(seconds)
    key(name, up=True)


def click(x: int, y: int):
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    inp = INPUT(type=0)
    inp.u.mi = MOUSEINPUT(int(x * 65535 / sw), int(y * 65535 / sh), 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
    _send(inp)
    for flag in (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP):
        inp.u.mi = MOUSEINPUT(int(x * 65535 / sw), int(y * 65535 / sh), 0, flag | MOUSEEVENTF_ABSOLUTE, 0, None)
        _send(inp)


def find_window(part: str):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if part in buf.value:
                    found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def focus_unity():
    hwnd = find_window(UNITY_WINDOW)
    if not hwnd:
        raise RuntimeError("Unity 창을 찾지 못함")
    user32.ShowWindow(hwnd, 3)                     # 최대화
    key("LCTRL"); key("LCTRL", up=True)             # 전경 전환 잠금 해제용 키 입력
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    # Game 창(최대화) 왼쪽 아래 빈 바닥을 눌러 키 입력 포커스를 준다 (로봇·사이드바와 겹치지 않는 자리)
    click(rect.left + int((rect.right - rect.left) * 0.08), rect.top + int((rect.bottom - rect.top) * 0.85))
    time.sleep(0.3)


# ===================== 녹화 =====================
class Recorder:
    def __init__(self, name: str, window: bool = True):
        self.out = os.path.join(VIDEO_DIR, name)
        self.stop_file = os.path.splitext(self.out)[0] + ".stop"
        cmd = [sys.executable, os.path.join(ROOT, "tools", "record_screen.py"), "--out", self.out, "--max", "300"]
        if window:
            cmd += ["--window", UNITY_WINDOW]
        self.proc = subprocess.Popen(cmd, env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    async def stop(self):
        open(self.stop_file, "w").close()
        while self.proc.poll() is None:
            await asyncio.sleep(0.5)
        print("  saved", self.out, flush=True)


# ===================== 장면 =====================
async def restart_relay(relay: Relay, tb2_odom=(0.0, 0.0, 0.0)):
    relay.stop()
    WORLD.reset(tb2_odom)
    mark = log_size()
    relay.start()
    ok = await wait_unity_connected(mark, 120)
    print("  relay", "connected" if ok else "NOT connected", flush=True)
    await asyncio.sleep(3.0)
    focus_unity()


async def scene_s2(relay):
    print("[s2] AUTO 두 대 → 만남 정지", flush=True)
    await restart_relay(relay)
    rec = Recorder("unity_s2_auto_sim.mp4")
    await asyncio.sleep(3.0)
    await tap("R")
    await asyncio.sleep(14.0)
    await rec.stop()


async def scene_s3_s4(relay):
    print("[s3] tb1 AUTO → 장애물 → 정지", flush=True)
    await restart_relay(relay, tb2_odom=(0.0, 0.8, 0.0))   # tb2는 옆으로 비켜 세움 (Unity x=+0.8)
    rec = Recorder("unity_s3_stop_sim.mp4")
    await asyncio.sleep(3.0)
    await tap("R", mod="LSHIFT")                            # tb1만 AUTO
    await asyncio.sleep(1.5)
    wx, wz = WORLD.ahead("tb1", 0.8)
    WORLD.obstacles.append((wx, wz, WORKER_RADIUS_M))       # 작업자 역 등장
    await asyncio.sleep(9.0)
    await rec.stop()

    print("[s4] 콕핏 → 수동 탈출 → 재개", flush=True)
    focus_unity()
    rec = Recorder("unity_s4_vr_sim.mp4")
    await asyncio.sleep(2.0)
    await tap("TAB")                                        # 콕핏 진입 (그 로봇만 MANUAL)
    await asyncio.sleep(4.0)
    await hold("S", 1.8)                                    # 후진
    await asyncio.sleep(0.6)
    await hold("D", 1.2)                                    # 추천 방향(우)으로 선회
    await asyncio.sleep(0.6)
    await hold("W", 3.0)                                    # 비켜서 전진
    await asyncio.sleep(1.5)
    await tap("ESC")                                        # 관제 맵 복귀
    await asyncio.sleep(1.5)
    await tap("R", mod="LSHIFT")                            # tb1 AUTO 재개
    await asyncio.sleep(6.0)
    await rec.stop()


async def scene_s5(relay):
    print("[s5] 주행 중 Play 중지 → 정지", flush=True)
    await restart_relay(relay)
    rec = Recorder("unity_s5_disconnect_sim.mp4", window=False)
    await asyncio.sleep(2.0)
    await tap("R")
    await asyncio.sleep(2.5)
    await tap("P", mod="LCTRL")                             # 에디터 Play 중지 = 클라이언트 연결 해제
    await asyncio.sleep(5.0)
    await rec.stop()


def robot_colors_visible():
    """Unity 창 캡처에서 하늘색(tb1)·주황(tb2) 로봇이 보이는지 (픽셀 비율 %)."""
    import cv2
    import numpy as np
    from PIL import ImageGrab
    hwnd = find_window(UNITY_WINDOW)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    img = cv2.cvtColor(np.array(ImageGrab.grab(bbox=(rect.left, rect.top + 140, rect.right, rect.bottom - 40))), cv2.COLOR_RGB2HSV)
    cyan = cv2.inRange(img, (85, 120, 150), (100, 255, 255)).mean() / 255 * 100
    orange = cv2.inRange(img, (10, 120, 150), (25, 255, 255)).mean() / 255 * 100
    return cyan > 0.05, orange > 0.05


async def restart_play():
    """에디터 Play 끄기 → (스크립트 다시 컴파일) → 다시 켜기."""
    focus_unity()
    await tap("P", mod="LCTRL")
    await asyncio.sleep(25.0)
    focus_unity()
    await tap("P", mod="LCTRL")


async def scene_tb1_obstacle(relay):
    """tb1 혼자 직진 → 앞 장애물 → 0.35m 정지 (현재 화면 스타일: tb2 숨김, LiDAR 점 없음)."""
    print("[tb1stop] tb1 직진 → 장애물 → 정지", flush=True)
    WORLD.reset(tb2_odom=(0.0, 3.4, 0.0))                   # tb2는 화면 밖 오른쪽 멀리
    await asyncio.sleep(2.0)
    focus_unity()
    tb1_vis, tb2_vis = robot_colors_visible()
    if not tb1_vis:
        await tap("F2")
    if tb2_vis:
        await tap("F3")
    await asyncio.sleep(1.0)
    rec = Recorder("unity_tb1_obstacle_sim.mp4")
    await asyncio.sleep(3.0)
    await tap("R", mod="LSHIFT")                            # 조종 대상(기본 tb1)만 AUTO
    await asyncio.sleep(1.5)
    wx, wz = WORLD.ahead("tb1", 0.8)
    WORLD.obstacles.append((wx, wz, WORKER_RADIUS_M))
    await asyncio.sleep(9.0)
    await rec.stop()
    if not tb1_vis:
        await tap("F2")
    if tb2_vis:
        await tap("F3")


async def main_tb1_obstacle():
    """이미 열린 Unity를 그대로 쓰고 장면 하나만 찍는다 (실물 릴레이는 미리 꺼 둘 것)."""
    os.makedirs(VIDEO_DIR, exist_ok=True)
    servers = [await serve(lambda ws: rosbridge_handler(ws, "tb1"), "127.0.0.1", TB1_PORT),
               await serve(lambda ws: rosbridge_handler(ws, "tb2"), "127.0.0.1", TB2_PORT)]
    asyncio.create_task(physics())
    relay = Relay()
    try:
        WORLD.reset(tb2_odom=(0.0, 3.4, 0.0))
        mark = log_size()
        relay.start()
        if find_window(UNITY_WINDOW):
            await restart_play()
        else:
            print("Unity 실행 중...", flush=True)
            subprocess.Popen([UNITY_EXE, "-projectPath", PROJECT, "-executeMethod", "PhysicalAI.EditorTools.DemoCapture.Play"])
        if not await wait_unity_connected(mark, UNITY_CONNECT_TIMEOUT_S):
            print("Unity가 릴레이에 접속하지 않음 — 중단", flush=True)
            return 1
        print("Unity 접속 확인", flush=True)
        await asyncio.sleep(5.0)
        await scene_tb1_obstacle(relay)
    finally:
        for k in SC:
            key(k, up=True)
        relay.stop()
        for s in servers:
            s.close()
    print("완료", flush=True)
    return 0


async def main():
    if "--tb1-obstacle" in sys.argv:
        return await main_tb1_obstacle()
    os.makedirs(VIDEO_DIR, exist_ok=True)
    servers = [await serve(lambda ws: rosbridge_handler(ws, "tb1"), "127.0.0.1", TB1_PORT),
               await serve(lambda ws: rosbridge_handler(ws, "tb2"), "127.0.0.1", TB2_PORT)]
    asyncio.create_task(physics())
    relay = Relay()
    mark = log_size()
    relay.start()
    print("Unity 실행 중 (첫 실행은 수 분 걸림)...", flush=True)
    unity = subprocess.Popen([UNITY_EXE, "-projectPath", PROJECT, "-executeMethod", "PhysicalAI.EditorTools.DemoCapture.Play"])
    if not await wait_unity_connected(mark, UNITY_CONNECT_TIMEOUT_S):
        print("Unity가 릴레이에 접속하지 않음 — 중단", flush=True)
        relay.stop()
        return 1
    print("Unity 접속 확인", flush=True)
    await asyncio.sleep(5.0)
    try:
        await scene_s2(relay)
        await scene_s3_s4(relay)
        await scene_s5(relay)
    finally:
        for k in SC:
            key(k, up=True)
        relay.stop()
        for s in servers:
            s.close()
    print("완료. Unity 창은 열어 둠 (pid", unity.pid, ")", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
