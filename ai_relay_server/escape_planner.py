"""
LiDAR 기반 추천 탈출 경로 + 카메라 오버레이 (T-015)
==================================================
- plan_escape(): 360° LaserScan에서 로봇 폭 회랑이 가장 길게 비는 방향 선택 (회전량 적을수록 우선).
- draw_obstacle_notice(): 정지 알림 배너 + 추천 경로(카메라 화각 안: 바닥 경로 / 밖: 가장자리 회전 화살표).
- 자동 주행 없음. 조작자에게 방향만 제시.
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import cv2
import numpy as np

from rosbridge_link import LIDAR_MIN_VALID_M

ROBOT_HALF_WIDTH_M = 0.12        # TurtleBot3 Burger 폭 178mm/2 + 여유 3cm
PATH_HORIZON_M = 1.5             # 이 이상 비면 충분히 열린 것으로 간주
MIN_CLEARANCE_M = 0.5            # 추천 최소 직진 여유
HEADING_STEP_DEG = 5
TURN_PENALTY_M_PER_RAD = 0.25    # 같은 여유면 적게 도는 방향 우선 (180° 회전 ≈ 0.79m 감점)

CAMERA_HFOV_DEG = 62.2           # Raspberry Pi Camera v2 (imx219) 수평 화각
PATH_HORIZON_Y_RATIO = 0.55      # 경로 끝점 화면 높이 (원근 근사)
EDGE_FOV_MARGIN_DEG = 3.0        # 화각 경계 근처는 가장자리 화살표로 표시

COLOR_ALERT = (0, 0, 255)        # BGR
COLOR_BANNER = (0, 0, 170)       # 짙은 적색: 흰 글자 대비 7:1 이상 (밝은 바닥 위에서도 WCAG AA)
BANNER_ALPHA = 0.9
COLOR_PATH = (0, 220, 0)
COLOR_TEXT = (255, 255, 255)
COLOR_OUTLINE = (0, 0, 0)
LABEL_STRIP_ALPHA = 0.7          # 하단 안내 문구 뒤 어두운 띠


@dataclass
class ScanData:
    ranges: Sequence[Optional[float]]
    angle_min: float
    angle_increment: float
    range_min: float
    range_max: float


@dataclass
class EscapeSuggestion:
    heading_rad: float               # 로봇 기준 (+좌, -우)
    clearance_m: float               # 추천 방향 직진 여유 (≤ PATH_HORIZON_M)

    @property
    def heading_deg(self) -> float:
        return math.degrees(self.heading_rad)


def _valid_points(scan: ScanData) -> np.ndarray:
    """유효 측정만 로봇 좌표 (x 전방, y 좌측) 배열 (N,2)로."""
    r = np.array([np.nan if v is None else v for v in scan.ranges], dtype=float)
    a = scan.angle_min + np.arange(r.size) * scan.angle_increment
    ok = np.isfinite(r) & (r >= max(scan.range_min, LIDAR_MIN_VALID_M)) & (r <= scan.range_max)
    return np.stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok])], axis=1)


def free_length(points: np.ndarray, heading_rad: float) -> float:
    """heading 방향 직선 회랑(반폭 ROBOT_HALF_WIDTH_M)의 첫 장애물까지 거리 (≤ PATH_HORIZON_M)."""
    if points.size == 0:
        return PATH_HORIZON_M
    c, s = math.cos(heading_rad), math.sin(heading_rad)
    fwd = points[:, 0] * c + points[:, 1] * s
    lat = -points[:, 0] * s + points[:, 1] * c
    blocking = (fwd > 0.0) & (np.abs(lat) < ROBOT_HALF_WIDTH_M)
    return float(min(PATH_HORIZON_M, fwd[blocking].min())) if blocking.any() else PATH_HORIZON_M


def plan_escape(scan: Optional[ScanData]) -> Optional[EscapeSuggestion]:
    """여유 MIN_CLEARANCE_M 이상 방향 중 (여유 - 회전 감점) 최대. 없으면 None."""
    if scan is None or not scan.ranges:
        return None
    points = _valid_points(scan)
    best: Optional[EscapeSuggestion] = None
    best_score = -math.inf
    for deg in range(-180, 180, HEADING_STEP_DEG):
        h = math.radians(deg)
        free = free_length(points, h)
        if free < MIN_CLEARANCE_M:
            continue
        score = free - TURN_PENALTY_M_PER_RAD * abs(h)
        if score > best_score:
            best_score, best = score, EscapeSuggestion(h, free)
    return best


def _heading_to_x(heading_rad: float, width: int) -> int:
    """핀홀 근사: 좌(+) 방향일수록 화면 왼쪽."""
    f = (width / 2) / math.tan(math.radians(CAMERA_HFOV_DEG / 2))
    return int(round(width / 2 - f * math.tan(heading_rad)))


def draw_obstacle_notice(frame: np.ndarray, reason: str, suggestion: Optional[EscapeSuggestion],
                         has_lidar: bool = True, draw_floor_path: bool = True, draw_arrows: bool = True) -> None:
    """정지 알림 배너 + 추천 탈출 경로를 frame에 직접 그림. 화면 문구는 방향만 (수치 미표시).
    draw_floor_path=False: 카메라 투영 경로(camera_projection)가 따로 그려질 때 화각 안 근사 바닥 경로 생략.
    draw_arrows=False: 선회 화살표(camera_projection.draw_pivot)가 따로 그려질 때 가장자리 화살표 생략.
    """
    h, w = frame.shape[:2]

    # 1) 상단 경고 배너 (반투명)
    banner_h = 58
    _blend_rect(frame, (0, 0), (w, banner_h), COLOR_BANNER, BANNER_ALPHA)
    cv2.putText(frame, f"STOPPED: {reason}", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COLOR_TEXT, 2)
    cv2.putText(frame, "OPERATOR ACTION REQUIRED - forward blocked, reverse/turn allowed",
                (12, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_TEXT, 1)

    if suggestion is None:
        msg = ("NO CLEAR PATH - remove obstacle or reverse manually" if has_lidar
               else "NO LIDAR DATA - escape path unavailable")
        _label(frame, msg, COLOR_ALERT)
        return

    deg = suggestion.heading_deg
    label = f"ESCAPE: TURN {'LEFT' if deg > 0 else 'RIGHT'}, THEN GO"
    if abs(deg) < HEADING_STEP_DEG / 2:
        label = "ESCAPE: STRAIGHT"

    half_fov = CAMERA_HFOV_DEG / 2 - EDGE_FOV_MARGIN_DEG
    if abs(deg) <= half_fov:
        if not draw_floor_path:
            _label(frame, label, COLOR_PATH)
            return
        # 2a) 화각 안: 하단 중앙 → 추천 방향 바닥 경로 (원근 사다리꼴 + 화살표)
        x_end = _heading_to_x(suggestion.heading_rad, w)
        y_end = int(h * PATH_HORIZON_Y_RATIO)
        base_half, tip_half = int(w * 0.12), int(w * 0.03)
        poly = np.array([[w // 2 - base_half, h - 1], [w // 2 + base_half, h - 1],
                         [x_end + tip_half, y_end], [x_end - tip_half, y_end]], np.int32)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly], COLOR_PATH)
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
        cv2.arrowedLine(frame, (w // 2, h - 10), (x_end, y_end), COLOR_OUTLINE, 8, tipLength=0.12)
        cv2.arrowedLine(frame, (w // 2, h - 10), (x_end, y_end), COLOR_PATH, 4, tipLength=0.12)
    elif draw_arrows:
        # 2b) 화각 밖: 회전 방향 가장자리 화살표 (180° 근처면 후방)
        left = deg > 0
        y = h // 2
        x_from, x_to = (w // 2 - 40, 30) if left else (w // 2 + 40, w - 30)
        cv2.arrowedLine(frame, (x_from, y), (x_to, y), COLOR_OUTLINE, 10, tipLength=0.18)  # 밝은 배경 대비 외곽선
        cv2.arrowedLine(frame, (x_from, y), (x_to, y), COLOR_PATH, 6, tipLength=0.18)
        if abs(deg) > 150:
            label = f"ESCAPE BEHIND: TURN {'LEFT' if left else 'RIGHT'}, THEN GO"
    _label(frame, label, COLOR_PATH)


def _blend_rect(frame: np.ndarray, p1, p2, color, alpha: float) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, p1, p2, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def _label(frame: np.ndarray, text: str, color) -> None:
    """하단 안내 문구: 어두운 띠 위에 표시 (영상 밝기와 무관하게 판독)."""
    h, w = frame.shape[:2]
    strip_h = 34
    _blend_rect(frame, (0, h - strip_h), (w, h), COLOR_OUTLINE, LABEL_STRIP_ALPHA)
    cv2.putText(frame, text, (12, h - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
