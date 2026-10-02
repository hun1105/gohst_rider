"""
rosbridge v2 WebSocket 클라이언트 (T-012)
=========================================
- 실기체 TurtleBot3 1대와 릴레이 서버를 잇는 asyncio 링크.
- ROS 1 Noetic(tb1)·ROS 2 Humble(tb2) 공용: 로봇에서 rosbridge_server만 띄우면 됨.
  - Noetic: roslaunch rosbridge_server rosbridge_websocket.launch
  - Humble: ros2 launch rosbridge_server rosbridge_websocket_launch.xml
- 릴레이 쪽 rclpy·ros1_bridge 불필요 → Windows Python에서도 실행 가능.
- 구독: odom(20Hz 스로틀), scan(10Hz 스로틀) / 발행: cmd_vel
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import websockets

logger = logging.getLogger("RosbridgeLink")

RECONNECT_DELAY_S = 2.0          # 연결 실패·끊김 후 재시도 간격
CONNECT_TIMEOUT_S = 3.0          # WebSocket 핸드셰이크 제한
PING_INTERVAL_S = 2.0            # 끊김 조기 감지 (Wi-Fi 드롭)
PING_TIMEOUT_S = 2.0
ODOM_THROTTLE_MS = 50            # rosbridge 측 odom 전송 간격 (20Hz)
SCAN_THROTTLE_MS = 100           # rosbridge 측 scan 전송 간격 (10Hz)
SECTOR_HALF_ANGLE_RAD = math.radians(30)   # 전방/후방 감시 섹터 반각
FRONT_ANGLE_RAD = 0.0
REAR_ANGLE_RAD = math.pi
NO_RANGE = -1.0                  # 섹터 내 유효 측정 없음
# LiDAR 유효 최소 거리 하한. ROS 1 LD08(LDS-02) 드라이버는 range_min=0.0을 보내고 무효 측정을 0.0으로 채움
# → 그대로 쓰면 0m 장애물로 판단해 전진 영구 차단. LDS-01/02 측정 하한(0.12m) 미만은 무효로 처리.
LIDAR_MIN_VALID_M = 0.12

MSG_TYPES = {
    1: {"twist": "geometry_msgs/Twist", "odom": "nav_msgs/Odometry", "scan": "sensor_msgs/LaserScan"},
    2: {"twist": "geometry_msgs/msg/Twist", "odom": "nav_msgs/msg/Odometry", "scan": "sensor_msgs/msg/LaserScan"},
}


def quaternion_to_yaw(q: dict) -> float:
    """ROS 쿼터니언 → yaw (rad, 반시계 +)."""
    x, y, z, w = (float(q.get(k, 0.0)) for k in ("x", "y", "z", "w"))
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def sector_min_range(
    ranges: list, angle_min: float, angle_increment: float,
    range_min: float, range_max: float, center: float, half_angle: float,
) -> float:
    """LaserScan에서 center±half_angle 섹터의 최소 유효 거리. 없으면 NO_RANGE."""
    best = math.inf
    for i, r in enumerate(ranges):
        # rosbridge는 inf/NaN을 null로 보냄. NaN은 비교가 False라 자동 제외.
        if r is None or not (max(range_min, LIDAR_MIN_VALID_M) <= r <= range_max):
            continue
        a = angle_min + i * angle_increment
        diff = math.atan2(math.sin(a - center), math.cos(a - center))
        if abs(diff) <= half_angle and r < best:
            best = r
    return best if best != math.inf else NO_RANGE


@dataclass
class RobotFeedback:
    """로봇에서 받은 최신 상태 (ROS 좌표계). stamp는 time.monotonic() 수신 시각."""
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    odom_stamp: float = 0.0
    front_min: float = NO_RANGE
    rear_min: float = NO_RANGE
    scan_stamp: float = 0.0
    # 최신 원본 스캔 (ranges, angle_min, angle_increment, range_min, range_max) — 탈출 경로 계산용 (T-015)
    scan: Optional[Tuple[list, float, float, float, float]] = None


class RosbridgeLink:
    def __init__(self, robot_id: str, url: str, ros_version: int, namespace: str = ""):
        if ros_version not in MSG_TYPES:
            raise ValueError(f"ros_version must be 1 or 2, got {ros_version}")
        self.robot_id = robot_id
        self.url = url
        self.types = MSG_TYPES[ros_version]
        ns = namespace.strip("/")
        self.topics = {k: f"/{ns}/{k}" if ns else f"/{k}" for k in ("cmd_vel", "odom", "scan")}
        self.feedback = RobotFeedback()
        self.connected = False
        self._ws: Optional[Any] = None
        self._pending = (0.0, 0.0)
        self._pending_event = asyncio.Event()

    async def run(self) -> None:
        """연결 유지 루프. 끊기면 RECONNECT_DELAY_S 후 재접속."""
        while True:
            try:
                async with websockets.connect(
                    self.url, open_timeout=CONNECT_TIMEOUT_S,
                    ping_interval=PING_INTERVAL_S, ping_timeout=PING_TIMEOUT_S, max_size=None,
                ) as ws:
                    self._ws = ws
                    await self._setup(ws)
                    self.connected = True
                    logger.info(f"[{self.robot_id}] rosbridge connected {self.url} topics={self.topics}")
                    self.request_twist(0.0, 0.0)  # 재접속 직후 정지 지령
                    sender = asyncio.create_task(self._sender(ws))
                    try:
                        async for raw in ws:
                            self._dispatch(raw)
                    finally:
                        sender.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[{self.robot_id}] rosbridge link down ({type(e).__name__}: {e})")
            finally:
                self._ws = None
                self.connected = False
            await asyncio.sleep(RECONNECT_DELAY_S)

    async def _setup(self, ws) -> None:
        await ws.send(json.dumps({"op": "advertise", "topic": self.topics["cmd_vel"], "type": self.types["twist"]}))
        await ws.send(json.dumps({
            "op": "subscribe", "topic": self.topics["odom"], "type": self.types["odom"],
            "throttle_rate": ODOM_THROTTLE_MS, "queue_length": 1,
        }))
        await ws.send(json.dumps({
            "op": "subscribe", "topic": self.topics["scan"], "type": self.types["scan"],
            "throttle_rate": SCAN_THROTTLE_MS, "queue_length": 1,
        }))

    def _dispatch(self, raw) -> None:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return
        if data.get("op") != "publish":
            if data.get("op") == "status" and data.get("level") in ("error", "warning"):
                logger.warning(f"[{self.robot_id}] rosbridge status: {data.get('msg')}")
            return
        topic, msg = data.get("topic"), data.get("msg") or {}
        try:
            if topic == self.topics["odom"]:
                self._on_odom(msg)
            elif topic == self.topics["scan"]:
                self._on_scan(msg)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"[{self.robot_id}] malformed {topic}: {e}")

    def _on_odom(self, msg: dict) -> None:
        pose = msg["pose"]["pose"]
        fb = self.feedback
        fb.x = float(pose["position"]["x"])
        fb.y = float(pose["position"]["y"])
        fb.yaw = quaternion_to_yaw(pose["orientation"])
        fb.odom_stamp = time.monotonic()

    def _on_scan(self, msg: dict) -> None:
        args = (msg["ranges"], float(msg["angle_min"]), float(msg["angle_increment"]),
                float(msg["range_min"]), float(msg["range_max"]))
        fb = self.feedback
        fb.front_min = sector_min_range(*args, FRONT_ANGLE_RAD, SECTOR_HALF_ANGLE_RAD)
        fb.rear_min = sector_min_range(*args, REAR_ANGLE_RAD, SECTOR_HALF_ANGLE_RAD)
        fb.scan = args
        fb.scan_stamp = time.monotonic()

    def request_twist(self, linear: float, angular: float) -> None:
        """cmd_vel 지령 예약 (논블로킹). 송신 태스크가 최신 값만 전송 — 정체 시 옛 지령 누적 없음."""
        self._pending = (linear, angular)
        self._pending_event.set()

    async def _sender(self, ws) -> None:
        while True:
            await self._pending_event.wait()
            self._pending_event.clear()
            try:
                await ws.send(self._twist_json(*self._pending))
            except websockets.exceptions.ConnectionClosed:
                return  # 수신 루프가 끊김 처리·재접속 담당

    def _twist_json(self, linear: float, angular: float) -> str:
        return json.dumps({
            "op": "publish", "topic": self.topics["cmd_vel"],
            "msg": {"linear": {"x": linear, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": angular}},
        })

    async def send_stop(self) -> None:
        """종료 경로: 정지 지령 직접 송신 (실패 무시)."""
        ws = self._ws
        if ws is None:
            return
        try:
            await ws.send(self._twist_json(0.0, 0.0))
        except Exception:
            pass
