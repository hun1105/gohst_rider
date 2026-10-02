"""
Physical AI Multi-Agent ROS 2 Humble Relay & Safety Interlock Server
===================================================================
- 역할:
  1. TurtleBot3 Burger 2대(tb1: 주행 AGV, tb2: 순찰/장애물 AGV) ROS 2 Humble 통신 중계
  2. Unity 6 (Meta Quest VR) 텔레오퍼레이션 명령(/tb1/cmd_vel) 실시간 전달
  3. tb1 및 tb2 오도메트리(/tb1/odom, /tb2/odom) 실시간 좌표 변환 및 Unity 동기화
  4. YOLOv8 비전 AI 기반 협착/충돌 위험 감지 (작업자, tb2, 파렛트/화물)
  5. 하드웨어 미연결 시 즉시 시연 및 개발 가능한 고정밀 모의 시뮬레이션 모드 내장
"""

import argparse
import asyncio
import cv2
import json
import logging
import math
import numpy as np
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

import websockets
from websockets.server import serve

from camera_projection import (DEFAULT_CAMERA_FORWARD_M, DEFAULT_CAMERA_HEIGHT_M, DEFAULT_CAMERA_PITCH_DEG,
                               CameraModel, draw_calibration_grid, draw_paths, draw_pivot)
from escape_planner import (ROBOT_HALF_WIDTH_M, EscapeSuggestion, ScanData, _valid_points,
                            draw_obstacle_notice, plan_escape)
from path_planner import (MODE_FORWARD, MODE_NONE, MODE_PIVOT, RED, pivot_path, predict as predict_path,
                          recommend as recommend_path, to_world)
from rosbridge_link import NO_RANGE, RosbridgeLink

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiTurtleBotRelay")

# --- T-006: cmd_vel 워치독 ---
CMD_VEL_WATCHDOG_TIMEOUT_S = 0.5      # 텔레옵 무입력 허용 시간 (초)

# --- T-015: 장애물 정지·알림 (구 T-005 3-Step Escape 자동 후진·회전 삭제) ---
# 인터록 시 즉시 정지 + 조작자 알림 + LiDAR 추천 탈출 경로 표시. 회피 조작은 사람이 함.

# --- T-016: 자율 배회 AUTO (촬영 시연용, tb1 실기 전용) ---
AUTO_CRUISE_SPEED = 0.10              # 직진 배회 속도 (m/s)
AUTO_AVOID_SPEED = 0.05               # 회피 방향 정렬 후 전진 속도 (m/s)
AUTO_AVOID_TRIGGER_M = 0.6            # 전방 이 거리 이내 장애물 → AVOID
AUTO_ALIGNED_RAD = math.radians(20)   # 목표 방향 오차 이내면 전진하며 조향, 초과면 제자리 회전
AUTO_TURN_GAIN = 1.2                  # 조향 각속도 = 이득 × 방향 오차 (rad/s per rad)
AUTO_MAX_TURN = 0.8                   # 조향 각속도 상한 (rad/s)
AUTO_AVOID_TIMEOUT_S = 6.0            # AVOID 지속 한도 → STUCK (맴돌기 방지)
AUTO_GEOFENCE_RADIUS_M = 1.5          # 배회 구역 반경 (첫 AUTO 진입 위치 기준)
AUTO_GEOFENCE_REENTER_RATIO = 0.7     # 복귀 후 이 비율 안쪽이면 CRUISE (히스테리시스)
AUTO_MANUAL_OVERRIDE_EPS = 0.01       # 이 크기 초과 조작 입력 = 조작자 개입


class AutoState:
    OFF = "OFF"
    CRUISE = "CRUISE"
    AVOID = "AVOID"
    RETURN = "RETURN"
    STUCK = "STUCK"


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class AutoPilot:
    """T-025: 로봇별 AUTO 상태 (배회 중심은 그 로봇 odom 좌표)."""

    def __init__(self):
        self.state = AutoState.OFF
        self.stuck_reason = ""
        self.avoid_since = 0.0
        self.center: Optional[Tuple[float, float]] = None

    @property
    def active(self) -> bool:
        return self.state != AutoState.OFF


# --- 로봇 간 거리 인터록 ---
AGV_SAFETY_RADIUS_M = 1.0             # tb1↔tb2 최소 안전 거리 (m)

# --- T-007: 조종 권한 ---
ROBOT_IDS = ("tb1", "tb2")
DEFAULT_CONTROLLED_ROBOT = "tb1"

# --- T-012: 실기체 브리지 (rosbridge) ---
# 스폰 포즈 (Unity x, z, yaw도). 실기체는 전원 투입 위치 = odom 원점 → 이 포즈에 정렬.
SPAWN_POSES: Dict[str, Tuple[float, float, float]] = {
    "tb1": (0.0, 0.0, 0.0),
    "tb2": (1.8, 5.0, 180.0),
}
ODOM_STALE_S = 0.5                    # odom 무수신 → offline → 지령 0
SCAN_STALE_S = 1.0                    # scan 무수신 → LiDAR 가드 판단 불가
REAL_MAX_LINEAR_DEFAULT = 0.15        # 실기 선속도 상한 (m/s, 실내 시연)
REAL_MAX_ANGULAR = 1.5                # 실기 각속도 상한 (rad/s)
LIDAR_FRONT_GUARD_M = 0.35            # 전방 장애물 → 전진 차단 (+ tb1 인터록)
LIDAR_REAR_GUARD_M = 0.20             # 후방 장애물 → 후진 차단 (조작자 수동 후진 보호)
FRAME_WIDTH, FRAME_HEIGHT = 640, 480  # PROTOCOL 영상 규격, YOLO 회랑 기준
CAMERA_OPEN_TIMEOUT_MS = 8000         # 카메라 스트림 접속+FFmpeg 프로브 제한 (Wi-Fi MJPEG 3s 초과 실측)
CAMERA_READ_TIMEOUT_MS = 2000         # 프레임 무수신 판정
CAMERA_RETRY_S = 3.0                  # 실패 후 재접속 간격
SOURCE_SIM = "sim"
SOURCE_REAL = "real"

# --- T-019: 경로 추천·LiDAR 점 텔레메트리, 위치 원점 재설정 ---
SCAN_TELEMETRY_MAX_POINTS = 180       # Unity로 보내는 LiDAR 점 상한 (360점 → 2:1 솎음)
TELEMETRY_LOG_INTERVAL_TICKS = 20     # 운행 이력 JSONL 기록 간격 (20Hz 기준 1초)
NO_LEVEL = "NONE"


def odom_to_unity(ox: float, oy: float, oyaw_rad: float,
                  spawn: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """ROS odom(x 전방, y 좌측, yaw 반시계 rad) → Unity(x 우측, z 전방, yaw 시계 도), 스폰 포즈 기준."""
    x0, z0, yaw0 = spawn
    y0 = math.radians(yaw0)
    right, fwd = -oy, ox
    x = x0 + right * math.cos(y0) + fwd * math.sin(y0)
    z = z0 - right * math.sin(y0) + fwd * math.cos(y0)
    return x, z, (yaw0 - math.degrees(oyaw_rad)) % 360.0


def clamp(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


def relative_pose(x: float, y: float, yaw: float, origin: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """odom 포즈를 기록 원점 기준 상대 포즈로 (T-019 RESET_POSE). 원점 좌표계로 회전·이동."""
    ox, oy, oyaw = origin
    c, s_ = math.cos(-oyaw), math.sin(-oyaw)
    dx, dy = x - ox, y - oy
    return c * dx - s_ * dy, s_ * dx + c * dy, yaw - oyaw


class EscapeState:
    IDLE = "IDLE"
    STOP = "STOP"   # 장애물 정지·조작자 개입 대기 (전진 차단, 후진·회전 수동 허용)

class TurtleBotState:
    def __init__(self, name: str, init_x: float = 0.0, init_z: float = 0.0, init_yaw: float = 0.0):
        self.name = name
        self.x = init_x
        self.y = 0.0
        self.z = init_z
        self.yaw = init_yaw  # 도(Degree)
        self.linear_vel = 0.0
        self.angular_vel = 0.0
        self.battery = 100.0
        # T-012: 실기체 연동 상태
        self.source = SOURCE_SIM
        self.online = True
        self.scan_ok = False
        self.front_min = NO_RANGE
        self.rear_min = NO_RANGE
        self.guard_reason = ""  # 직전 실기 가드 사유 (로그 중복 방지)

    def update_physics(self, dt: float):
        rad = math.radians(self.yaw)
        self.x += self.linear_vel * math.sin(rad) * dt
        self.z += self.linear_vel * math.cos(rad) * dt
        self.yaw = (self.yaw + math.degrees(self.angular_vel * dt)) % 360.0

    def to_dict(self):
        return {
            "name": self.name,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "yaw": round(self.yaw, 2),
            "linear_vel": round(self.linear_vel, 2),
            "angular_vel": round(self.angular_vel, 2),
            "battery": round(self.battery, 1),
            "source": self.source,
            "online": self.online,
            "front_min": round(self.front_min, 3),
            "rear_min": round(self.rear_min, 3),
        }

class MultiTurtleBotRelay:
    def __init__(self, use_ai: bool = True,
                 links: Optional[Dict[str, RosbridgeLink]] = None,
                 camera_url: Optional[str] = None,
                 real_max_linear: float = REAL_MAX_LINEAR_DEFAULT,
                 real_patrol: bool = False,
                 allow_no_scan: bool = False,
                 camera_open_timeout_ms: int = CAMERA_OPEN_TIMEOUT_MS,
                 camera_model: Optional[CameraModel] = None,
                 camera_grid: bool = False,
                 camera_robot: str = "tb1"):
        self.use_ai = use_ai
        self.camera_url = camera_url
        # T-025: 카메라가 달린 로봇 (영상 위 경로·정지 배너·YOLO 판단 대상)
        self.camera_robot = camera_robot if camera_robot in ROBOT_IDS else "tb1"
        self.vision_hazard = ""   # YOLO 회랑 검출 사유 (카메라 로봇 대상)
        self.camera_open_timeout_ms = camera_open_timeout_ms
        # T-020: 영상 위 경로 투영 (None이면 투영 안 함) + 보정 격자 모드
        self.camera_model = camera_model
        self.camera_grid = camera_grid
        self.camera_paths = None   # (추천, 대안 목록, 예상) — 로봇 좌표 궤적, 텔레메트리 루프가 갱신
        # 운행 이력: 텔레메트리 JSONL 파일 (main에서 지정, None이면 기록 안 함)
        self.telemetry_log = None
        self._telemetry_tick = 0

        # 2대의 TurtleBot3 상태 관리
        self.tb1 = TurtleBotState("tb1", *SPAWN_POSES["tb1"])
        self.tb2 = TurtleBotState("tb2", *SPAWN_POSES["tb2"])

        # T-012: 실기체 링크 (URL 지정된 로봇만 real, 나머지 sim)
        self.links: Dict[str, RosbridgeLink] = links or {}
        self.real_max_linear = real_max_linear
        self.real_patrol = real_patrol
        self.allow_no_scan = allow_no_scan
        for robot_id in self.links:
            robot = self._robot(robot_id)
            robot.source = SOURCE_REAL
            robot.online = False

        # tb2 자율 순찰 변수 (웨이포인트 순환)
        self.tb2_patrol_timer = 0.0
        
        # 안전 인터록 상태
        self.safety_interlock = False
        self.hazard_info = {"status": "NORMAL", "class": "", "distance": 999.0}

        # T-015: 장애물 정지·알림 상태 + 추천 탈출 경로
        self.escape_state = EscapeState.IDLE
        self.hazard_reason = ""
        self.escape_suggestion: Optional[EscapeSuggestion] = None

        # T-019: 위치 원점 재설정 (로봇별 odom 원점, 기준 Unity 포즈)
        self.pose_origin: Dict[str, Tuple[float, float, float]] = {}
        self.pose_reference: Dict[str, Tuple[float, float, float]] = {}

        # T-016 → T-025: 자율 배회 AUTO (로봇별)
        self.autos: Dict[str, AutoPilot] = {rid: AutoPilot() for rid in ROBOT_IDS}

        # T-006: cmd_vel 워치독 (시작 시 무입력 = 정지 상태)
        self.last_cmd_time = 0.0
        self.watchdog_tripped = True

        # T-007: 텔레옵 권한 보유 로봇 (tb2 선택 시 자율 순찰 정지)
        self.controlled_robot = DEFAULT_CONTROLLED_ROBOT

        # 클라이언트 → 텔레메트리 갱신 이벤트 (클라이언트별 송신 태스크가 대기)
        self.connected_vr_clients: Dict[object, asyncio.Event] = {}
        self.latest_frame_jpeg = None
        self.latest_telemetry_json = ""
        
        # YOLOv8 로드
        self.model = None
        if self.use_ai:
            try:
                from ultralytics import YOLO
                logger.info("YOLOv8 모델 로드 중 (경로 장애물/타AGV/작업자 전수 검출)...")
                self.model = YOLO("yolov8n.pt")
                logger.info("YOLOv8 안전 모델 로드 완료.")
            except Exception as e:
                logger.warning(f"YOLO 로드 실패 ({e}). 기본 릴레이 모드로 실행합니다.")

    def update_tb2_patrol(self, dt: float):
        """tb2 (보조 AGV)의 자율 순찰 속도 지령 (위치 적분은 telemetry_loop에서 sim 로봇만)"""
        if self.controlled_robot == "tb2" or self.autos["tb2"].active:
            return  # 수동 조종 중 또는 AUTO: 개루프 순찰 안 함
        if self.tb2.source == SOURCE_REAL and not self.real_patrol:
            # 실기 tb2: 개루프 순찰 기본 비활성 (현장 안전)
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 0.0
            return
        self.tb2_patrol_timer += dt
        # 직선 왕복 및 회전 시뮬레이션
        cycle = self.tb2_patrol_timer % 16.0
        if cycle < 6.0:
            self.tb2.linear_vel = 0.22  # 전진
            self.tb2.angular_vel = 0.0
        elif cycle < 8.0:
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 1.57 # 180도 회전
        elif cycle < 14.0:
            self.tb2.linear_vel = 0.22  # 복귀 전진
            self.tb2.angular_vel = 0.0
        else:
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 1.57 # 원위치 회전

    # ------------------------------------------------------------------
    # 안전 로직 (Claude 전용): T-015 장애물 정지·알림, T-006 cmd_vel 워치독,
    # T-007 조종 권한 이양
    # ------------------------------------------------------------------
    def _set_tb1_vel(self, lin: float, ang: float):
        self._set_vel("tb1", lin, ang)

    def _set_vel(self, robot_id: str, lin: float, ang: float):
        robot = self._robot(robot_id)
        robot.linear_vel = lin
        robot.angular_vel = ang

    def _robot(self, robot_id: str) -> TurtleBotState:
        return self.tb2 if robot_id == "tb2" else self.tb1

    def agv_distance(self) -> float:
        return math.hypot(self.tb2.x - self.tb1.x, self.tb2.z - self.tb1.z)

    def apply_teleop(self, robot_id: str, lin: float, ang: float):
        """조작자 TWIST/DRIVE 입력 적용. 권한·워치독 갱신 후 로봇별 안전 게이트 통과."""
        if robot_id != self.controlled_robot:
            return  # 권한 없는 로봇 명령 무시 (전환 직후 잔여 명령 차단)
        self.last_cmd_time = time.monotonic()
        self.watchdog_tripped = False

        if self.autos[robot_id].active:
            if abs(lin) <= AUTO_MANUAL_OVERRIDE_EPS and abs(ang) <= AUTO_MANUAL_OVERRIDE_EPS:
                return  # AUTO 중 0 입력(키 뗌 잔여)은 무시
            self.set_auto(False, "operator input", robot_id)

        if robot_id == "tb1":
            # 인터록(장애물 정지) 중: 전진만 차단, 후진·회전은 조작자 수동 회피 허용
            if self.safety_interlock and lin > 0:
                lin = 0.0
            self._set_tb1_vel(lin, ang)
        else:
            # tb2: 로봇 간 거리 인터록 + (카메라 로봇이면) 비전 검출
            if (self.agv_distance() < AGV_SAFETY_RADIUS_M or self.vision_blocks("tb2")) and lin > 0:
                lin = 0.0
            self.tb2.linear_vel = lin
            self.tb2.angular_vel = ang

    def stop_robot(self, robot_id: str, reason: str):
        """비상정지 경로: 지정 로봇 즉시 정지 (AUTO 해제)."""
        if robot_id in self.autos and self.autos[robot_id].active:
            self.set_auto(False, reason, robot_id)
        if robot_id == "tb2":
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 0.0
        else:
            self.stop_tb1(reason)

    def select_robot(self, robot_id: str):
        """T-007: 텔레옵 권한 이양. 이전 로봇 정지, 새 로봇 정지 상태에서 시작."""
        if robot_id not in ROBOT_IDS:
            logger.warning(f"[CONTROL] Unknown robot '{robot_id}' ignored")
            return
        if robot_id == self.controlled_robot:
            return
        prev = self.controlled_robot
        # T-025: AUTO 로봇은 권한이 바뀌어도 계속 배회 (MANUAL 전환은 콕핏 진입·조작 입력·STOP)
        if not self.autos[prev].active:
            self.stop_robot(prev, "control handover")
        self.controlled_robot = robot_id
        if not self.autos[robot_id].active:
            self._set_vel(robot_id, 0.0, 0.0)  # 순찰·잔여 속도 제거
        self.watchdog_tripped = True
        self.last_cmd_time = 0.0
        logger.warning(f"[CONTROL] Teleop handover {prev} -> {robot_id}")

    def release_control(self, reason: str):
        """클라이언트 이탈: 양쪽 정지, 권한 기본값 복귀 (tb2 순찰 재개), AUTO 해제·구역 중심 초기화."""
        for rid, ap in self.autos.items():
            self.set_auto(False, reason, rid)
            ap.center = None
        self.stop_robot("tb1", reason)
        self.stop_robot("tb2", reason)
        if self.controlled_robot != DEFAULT_CONTROLLED_ROBOT:
            logger.warning(f"[CONTROL] {reason}: control reverted to {DEFAULT_CONTROLLED_ROBOT}")
        self.controlled_robot = DEFAULT_CONTROLLED_ROBOT
        self.watchdog_tripped = True
        self.last_cmd_time = 0.0

    def stop_tb1(self, reason: str):
        """비상정지 경로: tb1 즉시 정지."""
        self._set_tb1_vel(0.0, 0.0)

    def update_obstacle_stop(self, now: float):
        """T-015: 인터록 상승 → 즉시 정지 + 알림(STOP). 해제 → IDLE. 자동 회피 동작 없음."""
        if self.escape_state == EscapeState.IDLE and self.safety_interlock:
            self._set_tb1_vel(0.0, 0.0)  # 회전 포함 즉시 정지. 이후 조작자 입력은 전진만 차단
            self.escape_state = EscapeState.STOP
            hint = self.escape_suggestion
            hint_txt = f", 추천 탈출 {hint.heading_deg:+.0f}° ({hint.clearance_m:.1f}m)" if hint else ""
            logger.warning(f"[OBSTACLE] tb1 정지 — 조작자 개입 필요: {self.hazard_reason}{hint_txt}")
        elif self.escape_state == EscapeState.STOP and not self.safety_interlock:
            self.escape_state = EscapeState.IDLE
            logger.info("[OBSTACLE] tb1 인터록 해제 → 주행 가능")

    # ------------------------------------------------------------------
    # T-016: 자율 배회 AUTO (안전 로직 — Claude 전용)
    # ------------------------------------------------------------------
    # tb1 기준 호환 속성 (기존 텔레메트리 최상위 mode·auto_state, 시험 코드)
    @property
    def auto_active(self) -> bool:
        return self.autos["tb1"].active

    @property
    def auto_state(self) -> str:
        return self.autos["tb1"].state

    @property
    def auto_stuck_reason(self) -> str:
        return self.autos["tb1"].stuck_reason

    def auto_eligible(self, robot_id: str = "tb1") -> str:
        """AUTO 진입 불가 사유. 가능하면 빈 문자열."""
        robot = self._robot(robot_id)
        if robot.source != SOURCE_REAL or robot_id not in self.links:
            return f"{robot_id} is not a real robot"
        if not robot.online:
            return f"{robot_id} offline"
        if not robot.scan_ok:
            return "no LiDAR scan"
        return ""

    def set_auto(self, enable: bool, reason: str, robot_id: str = "tb1"):
        ap = self.autos[robot_id]
        if not enable:
            if ap.active:
                logger.warning(f"[AUTO] {robot_id} OFF → MANUAL ({reason})")
                self._set_vel(robot_id, 0.0, 0.0)
            ap.state = AutoState.OFF
            ap.stuck_reason = ""
            return
        why_not = self.auto_eligible(robot_id)
        if why_not:
            logger.warning(f"[AUTO] {robot_id} 요청 거부: {why_not}")
            return
        fb = self.links[robot_id].feedback
        if ap.center is None:
            ap.center = (fb.x, fb.y)
            logger.info(f"[AUTO] {robot_id} 배회 구역 중심 고정 ({fb.x:.2f}, {fb.y:.2f}), 반경 {AUTO_GEOFENCE_RADIUS_M}m")
        ap.state = AutoState.CRUISE
        ap.stuck_reason = ""
        logger.warning(f"[AUTO] {robot_id} 시작/재개 ({reason})")

    def _auto_stuck(self, reason: str, robot_id: str = "tb1"):
        ap = self.autos[robot_id]
        self._set_vel(robot_id, 0.0, 0.0)
        if ap.state != AutoState.STUCK:
            logger.warning(f"[AUTO] {robot_id} STUCK — 조작자 개입 필요: {reason}")
        ap.state = AutoState.STUCK
        ap.stuck_reason = f"AUTO STUCK: {reason}"

    def _steer_toward(self, err: float, forward_speed: float, robot_id: str = "tb1"):
        """방향 오차(rad, +좌) 기준: 정렬되면 전진하며 조향, 아니면 제자리 회전."""
        ang = max(-AUTO_MAX_TURN, min(AUTO_MAX_TURN, AUTO_TURN_GAIN * err))
        lin = forward_speed if abs(err) <= AUTO_ALIGNED_RAD else 0.0
        self._set_vel(robot_id, lin, ang)

    def vision_blocks(self, robot_id: str) -> bool:
        """YOLO 회랑 검출은 카메라가 달린 로봇에만 적용."""
        return bool(self.vision_hazard) and robot_id == self.camera_robot

    def robot_hazard(self, robot_id: str) -> str:
        """로봇별 정지 원인 (없으면 빈 문자열). tb1은 영상 루프가 계산한 인터록과 같은 기준."""
        if robot_id == "tb1":
            return self.hazard_reason if self.safety_interlock else ""
        robot = self._robot(robot_id)
        if robot.source == SOURCE_REAL and self.lidar_front_blocked(robot):
            return f"LIDAR OBSTACLE ({robot.front_min:.2f}m)"
        d = self.agv_distance()
        if d < AGV_SAFETY_RADIUS_M:
            return f"COLLISION RISK: TB1 AGV ({d:.2f}m)"
        if self.vision_blocks(robot_id):
            return self.vision_hazard
        return ""

    def robot_stop_reason(self, robot_id: str) -> str:
        """화면 알림용: 인터록 원인 → 없으면 AUTO STUCK 원인."""
        hazard = self.robot_hazard(robot_id)
        if hazard:
            return hazard
        ap = self.autos[robot_id]
        return ap.stuck_reason if ap.state == AutoState.STUCK else ""

    def update_auto(self, now: float):
        """AUTO 상태머신 (20Hz, 로봇별). 정지 원인은 STUCK로 고정, 재개는 조작자 AUTO 요청만."""
        for robot_id in ROBOT_IDS:
            self._update_auto_robot(now, robot_id)

    def _update_auto_robot(self, now: float, robot_id: str):
        ap = self.autos[robot_id]
        if not ap.active:
            return
        robot = self._robot(robot_id)
        if not robot.online:
            self.set_auto(False, f"{robot_id} offline", robot_id)
            return
        if ap.state == AutoState.STUCK:
            self._set_vel(robot_id, 0.0, 0.0)
            return
        # 로봇 간 만남(1.0m)은 tb1·tb2 모두 STUCK → 관제사가 한 대를 골라 비켜줌
        hazard = self.robot_hazard(robot_id)
        if hazard:
            self._auto_stuck(hazard if robot_id != "tb1" else (self.hazard_reason or "interlock"), robot_id)
            return
        if not robot.scan_ok:
            self._auto_stuck("LiDAR scan lost", robot_id)
            return

        fb = self.links[robot_id].feedback
        cx, cy = ap.center
        dist_from_center = math.hypot(fb.x - cx, fb.y - cy)

        # 1) 전방 장애물 → LiDAR 추천 방향 회피 조향
        if 0.0 <= robot.front_min < AUTO_AVOID_TRIGGER_M:
            if ap.state != AutoState.AVOID:
                ap.state = AutoState.AVOID
                ap.avoid_since = now
            elif now - ap.avoid_since > AUTO_AVOID_TIMEOUT_S:
                self._auto_stuck(f"avoid timeout {AUTO_AVOID_TIMEOUT_S:.0f}s", robot_id)
                return
            suggestion = plan_escape(ScanData(*fb.scan)) if fb.scan else None
            if suggestion is None:
                self._auto_stuck("dead end - no clear path", robot_id)
                return
            self._steer_toward(suggestion.heading_rad, AUTO_AVOID_SPEED, robot_id)
            return

        # 2) 배회 구역 이탈 → 중심 방향 복귀
        if ap.state == AutoState.RETURN or dist_from_center > AUTO_GEOFENCE_RADIUS_M:
            if dist_from_center <= AUTO_GEOFENCE_RADIUS_M * AUTO_GEOFENCE_REENTER_RATIO:
                ap.state = AutoState.CRUISE
            else:
                ap.state = AutoState.RETURN
                err = wrap_angle(math.atan2(cy - fb.y, cx - fb.x) - fb.yaw)
                self._steer_toward(err, AUTO_CRUISE_SPEED, robot_id)
                return

        # 3) 직진 배회
        ap.state = AutoState.CRUISE
        self._set_vel(robot_id, AUTO_CRUISE_SPEED, 0.0)

    def check_cmd_watchdog(self, now: float):
        """T-006: 텔레옵 입력이 타임아웃 이상 끊기면 조종 대상 로봇 정지."""
        # T-025: 권한 없는 실기 로봇은 AUTO가 아니면 정지 유지 (조작 입력이 올 수 없음)
        for rid in ROBOT_IDS:
            other = self._robot(rid)
            if rid != self.controlled_robot and other.source == SOURCE_REAL and not self.autos[rid].active:
                other.linear_vel = 0.0
                other.angular_vel = 0.0
        robot_id = self.controlled_robot
        if self.autos[robot_id].active:
            return  # AUTO는 조작자 무입력이 정상. 연결 해제 시 release_control이 정지
        if now - self.last_cmd_time < CMD_VEL_WATCHDOG_TIMEOUT_S:
            return
        if not self.watchdog_tripped:
            logger.warning(f"[WATCHDOG] No cmd_vel for {CMD_VEL_WATCHDOG_TIMEOUT_S}s -> {robot_id} stopped")
            self.watchdog_tripped = True
        robot = self._robot(robot_id)
        robot.linear_vel = 0.0
        robot.angular_vel = 0.0

    def enforce_tb2_proximity(self):
        """T-007 → T-025: 로봇 간 1.0m 안이면 두 로봇 모두 전진 차단 (후진·회전으로 비켜주기만 허용)."""
        near = self.agv_distance() < AGV_SAFETY_RADIUS_M
        for robot in (self.tb1, self.tb2):
            blocked = near or (robot is self.tb2 and self.vision_blocks("tb2"))
            if blocked and robot.linear_vel > 0:
                robot.linear_vel = 0.0
                logger.warning(f"[PHYSICAL AI INTERLOCK] {robot.name} forward motion cut off (AGV proximity)")

    # ------------------------------------------------------------------
    # T-012: 실기체 브리지 (안전 로직 포함 — Claude 전용)
    # ------------------------------------------------------------------
    def sync_real_feedback(self, now: float):
        """rosbridge 최신 odom/scan → 로봇 상태 (포즈, online, LiDAR 섹터 거리)."""
        for robot_id, link in self.links.items():
            robot = self._robot(robot_id)
            fb = link.feedback
            robot.online = link.connected and now - fb.odom_stamp < ODOM_STALE_S
            if fb.odom_stamp > 0.0:
                ox, oy, oyaw = fb.x, fb.y, fb.yaw
                if robot_id in self.pose_origin:
                    ox, oy, oyaw = relative_pose(ox, oy, oyaw, self.pose_origin[robot_id])
                spawn = self.pose_reference.get(robot_id, SPAWN_POSES[robot_id])
                robot.x, robot.z, robot.yaw = odom_to_unity(ox, oy, oyaw, spawn)
            robot.scan_ok = link.connected and now - fb.scan_stamp < SCAN_STALE_S
            robot.front_min = fb.front_min if robot.scan_ok else NO_RANGE
            robot.rear_min = fb.rear_min if robot.scan_ok else NO_RANGE

    def lidar_front_blocked(self, robot: TurtleBotState) -> bool:
        return 0.0 <= robot.front_min < LIDAR_FRONT_GUARD_M

    def apply_real_guards(self):
        """실기 출력 게이트: offline 정지 → 속도 상한 → LiDAR 전·후방 가드. 지령 상태 자체를 수정."""
        for robot in (self.tb1, self.tb2):
            if robot.source != SOURCE_REAL:
                continue
            reason = ""
            if not robot.online:
                robot.linear_vel = 0.0
                robot.angular_vel = 0.0
                reason = "offline (odom stale)"
            else:
                robot.linear_vel = clamp(robot.linear_vel, self.real_max_linear)
                robot.angular_vel = clamp(robot.angular_vel, REAL_MAX_ANGULAR)
                scan_unknown = not robot.scan_ok and not self.allow_no_scan
                if robot.linear_vel > 0 and (scan_unknown or self.lidar_front_blocked(robot)):
                    robot.linear_vel = 0.0
                    reason = "scan stale" if scan_unknown else f"front {robot.front_min:.2f}m"
                elif robot.linear_vel < 0 and (scan_unknown
                                               or 0.0 <= robot.rear_min < LIDAR_REAR_GUARD_M):
                    robot.linear_vel = 0.0
                    reason = "scan stale" if scan_unknown else f"rear {robot.rear_min:.2f}m"
            if reason != robot.guard_reason:
                if reason:
                    logger.warning(f"[REAL GUARD] {robot.name} motion blocked: {reason}")
                else:
                    logger.info(f"[REAL GUARD] {robot.name} clear")
                robot.guard_reason = reason

    def reset_pose(self, robot_id: str, x: Optional[float], z: Optional[float], yaw: Optional[float]):
        """T-019: 현재 odom을 원점으로 기록 → Unity 포즈 = 기준 포즈 (현장 원점 마커 정렬)."""
        link = self.links.get(robot_id)
        if link is None or link.feedback.odom_stamp <= 0.0:
            logger.warning(f"[POSE] {robot_id} 원점 재설정 거부: 실기 odom 없음")
            return
        fb = link.feedback
        self.pose_origin[robot_id] = (fb.x, fb.y, fb.yaw)
        if x is not None and z is not None:
            self.pose_reference[robot_id] = (float(x), float(z), float(yaw or 0.0) % 360.0)
        else:
            self.pose_reference.pop(robot_id, None)
        ref = self.pose_reference.get(robot_id, SPAWN_POSES[robot_id])
        logger.warning(f"[POSE] {robot_id} 원점 재설정 → Unity ({ref[0]:.2f}, {ref[1]:.2f}, {ref[2]:.0f}°)")

    def build_path_telemetry(self) -> Tuple[dict, list]:
        """T-019: 실기 LiDAR 기준 추천·예상·대안 궤적 + LiDAR 점 (Unity 월드 평탄 배열).
        T-025: 대상 = 조종 중인 로봇 (실기·스캔 있을 때), 아니면 카메라 로봇."""
        rid = self.path_robot()
        empty = {"robot": rid, "recommended": [], "recommended_level": NO_LEVEL, "predicted": [], "predicted_level": NO_LEVEL,
                 "alternatives": [], "alt_points": 0,
                 "recommended_mode": MODE_NONE, "pivot_deg": 0.0, "pivot_points": [], "pivot_level": NO_LEVEL}
        link = self.links.get(rid)
        r = self._robot(rid)
        if link is None or r.source != SOURCE_REAL or not r.scan_ok or not link.feedback.scan:
            self.camera_paths = None
            return empty, []
        pts = _valid_points(ScanData(*link.feedback.scan))
        best, alts = recommend_path(pts)
        pred = predict_path(pts, r.linear_vel, r.angular_vel)
        # T-024: 전진 후보 전부 충돌 → LiDAR 탈출 방향으로 제자리 선회 후 직진 (회전 공간 있을 때만)
        mode, pivot, pivot_deg = (MODE_FORWARD if best else MODE_NONE), None, 0.0
        if best is None:
            esc = plan_escape(ScanData(*link.feedback.scan))
            pivot = pivot_path(pts, esc.heading_rad) if esc else None
            if pivot is not None and pivot.level != RED:
                mode, pivot_deg = MODE_PIVOT, round(esc.heading_deg, 1)
            else:
                pivot = None
        # 영상 위 경로는 카메라 로봇의 궤적일 때만 (다른 로봇 궤적을 이 카메라에 그리면 틀림)
        self.camera_paths = (best, alts, pred, pivot, pivot_deg) if rid == self.camera_robot else None
        w = lambda t: to_world(t.points, r.x, r.z, r.yaw) if t else []
        alt_points = min((len(a.points) for a in alts), default=0)
        path = {
            "robot": rid,
            "recommended": w(best), "recommended_level": best.level if best else NO_LEVEL,
            "predicted": w(pred), "predicted_level": pred.level if pred else NO_LEVEL,
            "alternatives": [v for a in alts for v in to_world(a.points[:alt_points], r.x, r.z, r.yaw)],
            "alt_points": alt_points,
            "recommended_mode": mode, "pivot_deg": pivot_deg,
            "pivot_points": w(pivot), "pivot_level": pivot.level if pivot else NO_LEVEL,
        }
        step = max(1, -(-len(pts) // SCAN_TELEMETRY_MAX_POINTS))   # 올림 나눗셈
        return path, to_world(pts[::step], r.x, r.z, r.yaw)

    def path_robot(self) -> str:
        """경로 추천 대상: 조종 중인 실기 로봇(스캔 있음) → 아니면 카메라 로봇."""
        c = self._robot(self.controlled_robot)
        if c.source == SOURCE_REAL and c.scan_ok and self.controlled_robot in self.links:
            return self.controlled_robot
        return self.camera_robot

    def publish_real_commands(self):
        """게이트 통과한 지령을 실기 cmd_vel로 (20Hz, 0 포함 상시 송신)."""
        for robot_id, link in self.links.items():
            robot = self._robot(robot_id)
            link.request_twist(robot.linear_vel, robot.angular_vel)

    def _open_camera(self) -> Optional["cv2.VideoCapture"]:
        """카메라 스트림 열기 (블로킹 → to_thread로 호출). 실패 시 None."""
        cap = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.camera_open_timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAMERA_READ_TIMEOUT_MS,
        ])
        if cap.isOpened():
            logger.info(f"카메라 스트림 연결: {self.camera_url}")
            return cap
        cap.release()
        logger.warning(f"카메라 스트림 열기 실패: {self.camera_url} → 가상 프레임, {CAMERA_RETRY_S}s 후 재시도")
        return None

    async def video_and_ai_loop(self):
        """tb1 전방 카메라 스트림 생성, YOLOv8 추론 및 충돌 인터록 판정"""
        cap = None
        next_camera_retry = 0.0

        while True:
            frame = None
            # 실물 파이캠 스트림 (HTTP MJPEG/RTSP). 블로킹 호출은 스레드로, 끊기면 주기적 재접속.
            if self.camera_url and cap is None and time.monotonic() >= next_camera_retry:
                cap = await asyncio.to_thread(self._open_camera)
                if cap is None:
                    next_camera_retry = time.monotonic() + CAMERA_RETRY_S
            if cap is not None:
                ret, frame = await asyncio.to_thread(cap.read)
                if not ret or frame is None:
                    logger.warning(f"카메라 프레임 수신 끊김 → 가상 프레임, {CAMERA_RETRY_S}s 후 재접속")
                    cap.release()
                    cap = None
                    frame = None
                    next_camera_retry = time.monotonic() + CAMERA_RETRY_S
                elif frame.shape[:2] != (FRAME_HEIGHT, FRAME_WIDTH):
                    # YOLO 회랑 픽셀 기준(640x480) 유지
                    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

            if frame is None:
                # 고해상도 가상 물류창고 FPV 프레임 렌더링
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                # 바닥 그라디언트
                frame[240:, :] = (45, 45, 45)
                # 차선 라인
                cv2.line(frame, (80, 480), (280, 240), (0, 200, 255), 3)
                cv2.line(frame, (560, 480), (360, 240), (0, 200, 255), 3)
                
                # 거리 계산: tb1과 tb2의 상대적 거리
                dx = self.tb2.x - self.tb1.x
                dz = self.tb2.z - self.tb1.z
                dist_tb1_tb2 = math.sqrt(dx*dx + dz*dz)
                
                # 가상 tb2 (보조 로봇) 렌더링
                if dz > 0.5 and dz < 8.0 and abs(dx) < 2.5:
                    # 원근법 투영
                    scale = max(0.2, 1.0 - (dz / 8.0))
                    box_w = int(140 * scale)
                    box_h = int(180 * scale)
                    center_x = int(320 + (dx / dz) * 300)
                    center_y = int(240 + 120 * scale)
                    
                    x1 = max(0, center_x - box_w // 2)
                    y1 = max(0, center_y - box_h // 2)
                    x2 = min(640, center_x + box_w // 2)
                    y2 = min(480, center_y + box_h // 2)
                    
                    # tb2 바디 렌더링
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 140, 0), -1)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
                    cv2.putText(frame, "AGV_TB2 [Patrol]", (x1 + 5, y1 + 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, (255, 255, 255), 1)

            # YOLOv8 실시간 추론 (작업자, 차량/AGV, 파렛트 등) — 카메라 로봇 대상
            detected_hazard = False
            hazard_name = "NORMAL"
            vision_hazard = ""
            min_dist = 999.0

            # tb1과 tb2의 물리적 거리 계산
            dist_to_tb2 = math.sqrt((self.tb2.x - self.tb1.x)**2 + (self.tb2.z - self.tb1.z)**2)
            
            if self.model is not None and frame is not None:
                # 0: 사람, 2,3,5,7: 차량/이동체, 24,26,28: 가방/화물, 56: 의자/장애물
                target_classes = [0, 1, 2, 3, 5, 7, 24, 26, 28, 56, 57]
                results = await asyncio.to_thread(self.model, frame, classes=target_classes, verbose=False)
                for r in results:
                    for box in r.boxes:
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names.get(cls_id, "Obstacle")
                        
                        center_x = (bx1 + bx2) // 2
                        box_height = by2 - by1
                        
                        # 전방 충돌 회랑 (Corridor: 중앙 50%, 근접 거리)
                        in_corridor = (180 <= center_x <= 460) and (by2 > 220)
                        
                        if in_corridor and box_height > 80 and conf > 0.40:
                            vision_hazard = f"HAZARD: {cls_name}"
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)
                            cv2.putText(frame, f"INTERLOCK: {cls_name} ({conf:.2f})", 
                                        (bx1, max(by1 - 10, 25)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        else:
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{cls_name} {conf:.2f}", 
                                        (bx1, max(by1 - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            self.vision_hazard = vision_hazard
            if vision_hazard and self.camera_robot == "tb1":
                detected_hazard = True
                hazard_name = vision_hazard

            # 타 AGV(tb2)와의 물리적 거리 기반 이중 안전 인터록
            if dist_to_tb2 < AGV_SAFETY_RADIUS_M:
                detected_hazard = True
                hazard_name = f"COLLISION RISK: TB2 AGV ({dist_to_tb2:.2f}m)"

            # T-012: 실기 tb1 LiDAR 전방 장애물 → 인터록 (정지·알림 원인)
            if self.tb1.source == SOURCE_REAL and self.lidar_front_blocked(self.tb1):
                detected_hazard = True
                hazard_name = f"LIDAR OBSTACLE ({self.tb1.front_min:.2f}m)"

            self.safety_interlock = detected_hazard
            if self.safety_interlock and self.tb1.linear_vel > 0:
                # 전진 주행 즉시 차단
                self.tb1.linear_vel = 0.0
                logger.warning(f"[PHYSICAL AI INTERLOCK] Forward motion cut off! Reason: {hazard_name}")

            # T-015: 정지 알림 배너 + LiDAR 추천 탈출 경로 (실기 tb1 스캔 있을 때만 경로 계산)
            # T-020: LiDAR 경로를 카메라 영상 위에 원근 투영 (상시). 보정 모드면 바닥 격자 추가
            if self.camera_model is not None:
                if self.camera_grid:
                    draw_calibration_grid(frame, self.camera_model)
                if self.camera_paths is not None:
                    best, alts, pred, pivot, pivot_deg = self.camera_paths
                    draw_paths(frame, self.camera_model, ROBOT_HALF_WIDTH_M,
                               best.points if best else None, best.level if best else "NONE",
                               pred.points if pred else None, [a.points for a in alts])
                    if pivot is not None:
                        draw_pivot(frame, self.camera_model, ROBOT_HALF_WIDTH_M, pivot.points, pivot.level, pivot_deg)

            # T-016: AUTO STUCK(막다른 길·회피 시간 초과)도 인터록과 같은 알림 경로 (safety 블록 = tb1 기준)
            if self.safety_interlock:
                notice = hazard_name
            elif self.auto_state == AutoState.STUCK:
                notice = self.auto_stuck_reason
            else:
                notice = ""
            self.hazard_reason = notice
            self.escape_suggestion = None
            has_lidar = self.tb1.source == SOURCE_REAL and self.tb1.scan_ok and "tb1" in self.links
            if notice and has_lidar:
                raw = self.links["tb1"].feedback.scan
                self.escape_suggestion = plan_escape(ScanData(*raw)) if raw else None

            # T-025: 영상 배너는 카메라 로봇 기준
            cam_id = self.camera_robot
            cam_robot = self._robot(cam_id)
            cam_notice = notice if cam_id == "tb1" else self.robot_stop_reason(cam_id)
            cam_lidar = cam_robot.source == SOURCE_REAL and cam_robot.scan_ok and cam_id in self.links
            if cam_id == "tb1":
                cam_escape = self.escape_suggestion
            else:
                raw = self.links[cam_id].feedback.scan if cam_lidar else None
                cam_escape = plan_escape(ScanData(*raw)) if (cam_notice and raw) else None
            cam_auto = self.autos[cam_id]
            if cam_notice:
                pivot_drawn = self.camera_model is not None and self.camera_paths is not None and self.camera_paths[3] is not None
                draw_obstacle_notice(frame, cam_notice, cam_escape, cam_lidar,
                                     draw_floor_path=self.camera_model is None, draw_arrows=not pivot_drawn)
            elif cam_auto.active:
                cv2.putText(frame, f"AUTO: {cam_auto.state}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
            else:
                cv2.putText(frame, "SYSTEM: SAFE (NORMAL)", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if not cam_notice:  # 경고 중엔 보조 정보 숨김 (배너·탈출 경로에 시선 집중)
                cv2.putText(frame, f"TB1 Pos: ({self.tb1.x:.1f}, {self.tb1.z:.1f}) | TB2: ({self.tb2.x:.1f}, {self.tb2.z:.1f}) | Dist: {dist_to_tb2:.2f}m",
                            (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, "ROS 2 Humble Multi-Agent Teleop", (20, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

            # JPEG 인코딩 및 버퍼 갱신
            _, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self.latest_frame_jpeg = jpeg_buf.tobytes()

            await asyncio.sleep(0.033) # 30 FPS

    async def telemetry_loop(self):
        """Unity 6로 tb1 및 tb2 오도메트리/상태 JSON 실시간 전송 (20Hz)"""
        dt = 0.05
        while True:
            # 안전 게이트 (장애물 정지 → 워치독 → tb2 거리 인터록) 후 물리 갱신
            now = time.monotonic()
            self.sync_real_feedback(now)
            self.update_obstacle_stop(now)
            self.update_auto(now)
            self.check_cmd_watchdog(now)
            self.enforce_tb2_proximity()
            self.update_tb2_patrol(dt)
            # T-012: 실기 출력 게이트 → cmd_vel 송신. sim 로봇만 위치 적분 (real은 odom이 위치 원천)
            self.apply_real_guards()
            self.publish_real_commands()
            for robot in (self.tb1, self.tb2):
                if robot.source == SOURCE_SIM:
                    robot.update_physics(dt)

            path_data, scan_points = self.build_path_telemetry()
            robots = {}
            for rid in ROBOT_IDS:
                d = self._robot(rid).to_dict()
                ap = self.autos[rid]
                reason = self.robot_stop_reason(rid)
                d.update({"mode": "AUTO" if ap.active else "MANUAL", "auto_state": ap.state,
                          "alert": bool(reason), "stop_reason": reason})
                robots[rid] = d
            telemetry_data = {
                "type": "telemetry",
                "tb1": robots["tb1"],
                "tb2": robots["tb2"],
                "safety": {
                    "interlock": self.safety_interlock,
                    "status": "EMERGENCY_STOP" if self.safety_interlock else "NORMAL",
                    "target": "tb1",
                    "escape": self.escape_state,
                    "reason": self.hazard_reason,
                    "escape_heading": round(self.escape_suggestion.heading_deg, 1) if self.escape_suggestion else 0.0,
                    "escape_clearance": round(self.escape_suggestion.clearance_m, 2) if self.escape_suggestion else NO_RANGE,
                    "watchdog": self.watchdog_tripped
                },
                "controlled_robot": self.controlled_robot,
                "camera_robot": self.camera_robot,
                "mode": "AUTO" if self.auto_active else "MANUAL",
                "auto_state": self.auto_state,
                "path": path_data,
                "scan": scan_points,
            }
            msg = json.dumps(telemetry_data)

            # 운행 이력 (Memory): 1 Hz 텔레메트리 스냅샷 JSONL. LiDAR 점·궤적 좌표는 제외, 신뢰도만
            self._telemetry_tick += 1
            if self.telemetry_log is not None and self._telemetry_tick % TELEMETRY_LOG_INTERVAL_TICKS == 0:
                snapshot = {k: v for k, v in telemetry_data.items() if k not in ("scan", "path")}
                snapshot["t"] = round(time.time(), 2)
                snapshot["path_level"] = path_data["recommended_level"]
                snapshot["predicted_level"] = path_data["predicted_level"]
                self.telemetry_log.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                self.telemetry_log.flush()

            # 연결된 모든 VR 클라이언트에 전송
            # 클라이언트 송신은 클라이언트별 태스크가 담당 (최신 값만).
            # 여기서 send를 await하면 느린 클라이언트가 제어 루프·실기 cmd_vel을 멈춤 (T-012).
            self.latest_telemetry_json = msg
            for telemetry_ready in self.connected_vr_clients.values():
                telemetry_ready.set()

            await asyncio.sleep(dt)

    async def vr_ws_handler(self, websocket):
        """Meta Quest 2 VR 클라이언트 웹소켓 통신 핸들러"""
        telemetry_ready = asyncio.Event()
        self.connected_vr_clients[websocket] = telemetry_ready
        logger.info(f"VR Client connected: {websocket.remote_address}")

        async def send_video_task():
            while True:
                if self.latest_frame_jpeg:
                    try:
                        await websocket.send(self.latest_frame_jpeg)
                    except Exception:
                        break
                await asyncio.sleep(0.033)

        async def send_telemetry_task():
            while True:
                await telemetry_ready.wait()
                telemetry_ready.clear()
                try:
                    await websocket.send(self.latest_telemetry_json)
                except Exception:
                    break

        video_sender = asyncio.create_task(send_video_task())
        telemetry_sender = asyncio.create_task(send_telemetry_task())

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    cmd = data.get("cmd")

                    if cmd == "TWIST":
                        # ROS 2 표준 Twist 포맷
                        target_robot = data.get("robot", "tb1")
                        lin = float(data.get("linear", 0.0))
                        ang = float(data.get("angular", 0.0))
                        self.apply_teleop(target_robot, lin, ang)

                    elif cmd == "DRIVE":
                        # 하위 호환 PWM / Left-Right 포맷 -> Twist 변환
                        left = int(data.get("left", 0))
                        right = int(data.get("right", 0))
                        # -220~+220 -> -0.22 m/s ~ +0.22 m/s 변환
                        forward_ratio = (left + right) / 440.0
                        turn_ratio = (left - right) / 440.0
                        
                        lin = forward_ratio * 0.22
                        ang = turn_ratio * 2.84

                        self.apply_teleop("tb1", lin, ang)

                    elif cmd == "STOP":
                        self.stop_robot(data.get("robot", "tb1"), "operator STOP")

                    elif cmd == "SELECT_ROBOT":
                        self.select_robot(str(data.get("robot", "")))

                    elif cmd == "RESET_POSE":
                        self.reset_pose(str(data.get("robot", "tb1")), data.get("x"), data.get("z"), data.get("yaw"))

                    elif cmd == "AUTO":
                        rid = str(data.get("robot", "tb1"))
                        if rid in ROBOT_IDS:
                            self.set_auto(bool(data.get("enable", True)), "operator AUTO command", rid)

                    elif cmd == "TELEPORT":
                        rid = str(data.get("robot", ""))
                        logger.info(f"[Perspective Mode]: {data.get('mode')} robot={rid}")
                        # T-025: 1인칭(콕핏) 진입 = 사람이 직접 조종 → 그 로봇 MANUAL
                        if data.get("mode") == "FPV" and rid in ROBOT_IDS and self.autos[rid].active:
                            self.set_auto(False, "operator entered cockpit", rid)

                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("VR Client disconnected.")
        finally:
            video_sender.cancel()
            telemetry_sender.cancel()
            self.connected_vr_clients.pop(websocket, None)
            self.release_control("client disconnected")

    async def run(self, host: str = "0.0.0.0", port: int = 9090):
        logger.info(f"ROS 2 Humble Multi-TurtleBot Relay running on ws://{host}:{port}...")
        for robot_id, link in self.links.items():
            logger.info(f"[T-012] {robot_id} = REAL via rosbridge {link.url}")
        server = await serve(self.vr_ws_handler, host, port)
        try:
            await asyncio.gather(
                self.video_and_ai_loop(),
                self.telemetry_loop(),
                *(link.run() for link in self.links.values()),
                server.wait_closed()
            )
        finally:
            # 종료 경로: 실기 정지 지령 (rosbridge 끊긴 뒤 마지막 속도 유지 방지)
            await asyncio.gather(*(link.send_stop() for link in self.links.values()))


def build_links(args: argparse.Namespace) -> Dict[str, RosbridgeLink]:
    links: Dict[str, RosbridgeLink] = {}
    for robot_id in ROBOT_IDS:
        url = getattr(args, f"{robot_id}_url")
        if url:
            links[robot_id] = RosbridgeLink(robot_id, url, getattr(args, f"{robot_id}_ros"),
                                            getattr(args, f"{robot_id}_ns"))
    return links


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ROS 2 Humble Multi-TurtleBot Relay Server")
    parser.add_argument("--mock", action="store_true",
                        help="(하위 호환, 무시됨) URL 미지정 로봇은 항상 sim")
    parser.add_argument("--no-ai", action="store_true", help="Disable YOLOv8 AI inference")
    parser.add_argument("--port", type=int, default=9090, help="Relay server WebSocket port")
    parser.add_argument("--host", default="0.0.0.0", help="Relay server bind address")
    # T-012: 실기체 rosbridge 연결 (지정한 로봇만 real)
    parser.add_argument("--tb1-url", help="tb1 rosbridge URL, 예) ws://172.30.1.23:9090")
    parser.add_argument("--tb1-ros", type=int, choices=(1, 2), default=1, help="tb1 ROS 버전 (Noetic=1)")
    parser.add_argument("--tb1-ns", default="", help="tb1 토픽 네임스페이스 (없으면 /cmd_vel)")
    parser.add_argument("--tb2-url", help="tb2 rosbridge URL, 예) ws://172.30.1.28:9090")
    parser.add_argument("--tb2-ros", type=int, choices=(1, 2), default=2, help="tb2 ROS 버전 (Humble=2)")
    parser.add_argument("--tb2-ns", default="", help="tb2 토픽 네임스페이스, 예) tb2")
    parser.add_argument("--camera-url", help="전방 카메라 MJPEG/RTSP URL (없으면 가상 프레임)")
    parser.add_argument("--camera-robot", choices=ROBOT_IDS, default="tb1",
                        help="카메라가 달린 로봇 (영상 위 경로·정지 배너·YOLO 대상)")
    parser.add_argument("--camera-open-timeout-ms", type=int, default=CAMERA_OPEN_TIMEOUT_MS,
                        help="카메라 스트림 열기 제한 ms (진단: tools/check_camera_stream.py)")
    # T-020: 카메라 장착값 (영상 위 경로 투영). Burger 138×178×192mm, Pi Camera v2 62.2°×48.8°
    parser.add_argument("--camera-height-m", type=float, default=DEFAULT_CAMERA_HEIGHT_M, help="렌즈 바닥 높이 m")
    parser.add_argument("--camera-pitch-deg", type=float, default=DEFAULT_CAMERA_PITCH_DEG, help="아래로 숙인 각 deg (권장 15)")
    parser.add_argument("--camera-forward-m", type=float, default=DEFAULT_CAMERA_FORWARD_M, help="로봇 중심→렌즈 전방 거리 m")
    parser.add_argument("--no-path-overlay", action="store_true", help="영상 위 경로 투영 끔")
    parser.add_argument("--camera-grid", action="store_true", help="보정 격자 표시 (바닥 0.5/1.0/1.5/2.0m 선)")
    parser.add_argument("--real-max-linear", type=float, default=REAL_MAX_LINEAR_DEFAULT,
                        help="실기 선속도 상한 m/s")
    parser.add_argument("--real-patrol", action="store_true", help="실기 tb2 자율 순찰 허용")
    parser.add_argument("--allow-no-scan", action="store_true",
                        help="scan 미수신이어도 전·후진 허용 (LiDAR 가드 해제, 비권장)")
    parser.add_argument("--log-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
                        help="운행 이력 저장 폴더 (이벤트 로그 + 1Hz 텔레메트리 JSONL)")
    parser.add_argument("--no-log", action="store_true", help="운행 이력 파일 기록 끔")
    args = parser.parse_args()

    telemetry_log = None
    if not args.no_log:
        os.makedirs(args.log_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        event_path = os.path.join(args.log_dir, f"relay_events_{stamp}.log")
        handler = logging.FileHandler(event_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)
        telemetry_log = open(os.path.join(args.log_dir, f"relay_telemetry_{stamp}.jsonl"), "a", encoding="utf-8")
        logger.info(f"[LOG] 운행 이력 기록: {event_path} (+ telemetry jsonl)")

    relay = MultiTurtleBotRelay(
        use_ai=not args.no_ai, links=build_links(args), camera_url=args.camera_url,
        real_max_linear=args.real_max_linear, real_patrol=args.real_patrol,
        allow_no_scan=args.allow_no_scan, camera_open_timeout_ms=args.camera_open_timeout_ms,
        camera_model=None if args.no_path_overlay else CameraModel(
            mount_height_m=args.camera_height_m, pitch_deg=args.camera_pitch_deg, forward_m=args.camera_forward_m),
        camera_grid=args.camera_grid, camera_robot=args.camera_robot,
    )
    relay.telemetry_log = telemetry_log
    try:
        asyncio.run(relay.run(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped.")
    finally:
        if telemetry_log is not None:
            telemetry_log.close()
