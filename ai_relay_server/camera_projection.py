"""
카메라 영상 위 경로 투영 (T-020)
================================
- 경로 계산은 LiDAR(path_planner), 그리는 곳은 전방 카메라 영상 (NVIDIA PathNet식 표시).
- 핀홀 카메라 모델: 바닥 점 (로봇 좌표 x 전방, y 좌측, z=0) → 영상 픽셀.
- 카메라: Raspberry Pi Camera v2 (imx219) 수평 62.2° / 수직 48.8°, 640×480.
- 장착 기본값: TurtleBot3 Burger 크기 138×178×192mm (ROBOTIS 공식 제원) 기준
  앞단 부근(+0.06m), 높이 0.17m, 수평(피치 0°). 실측 후 CLI로 덮어씀.
- 보정 격자 모드: 바닥 0.5/1.0/1.5/2.0m 거리선과 ±0.25m 측면선 → 바닥 테이프와 겹치게 피치 조정.
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

PI_CAM_V2_HFOV_DEG = 62.2
PI_CAM_V2_VFOV_DEG = 48.8
DEFAULT_CAMERA_HEIGHT_M = 0.16       # 실측: 렌즈 높이 = Galaxy S20 FE 높이 159.8mm (Burger 전고 0.192m 이하)
DEFAULT_CAMERA_PITCH_DEG = 0.0       # 아래로 숙인 각 (+)
DEFAULT_CAMERA_FORWARD_M = 0.06      # 로봇 중심 → 렌즈 (Burger 전장 0.138m의 앞쪽)
MIN_DEPTH_M = 0.05                   # 이보다 카메라에 가까운/뒤쪽 점은 그리지 않음

RIBBON_FILL_ALPHA = 0.38
RIBBON_EDGE_PX = 2
PREDICTED_LINE_PX = 3
ALT_LINE_PX = 2
GRID_DISTANCES_M = (0.5, 1.0, 1.5, 2.0)
GRID_LATERAL_M = 0.25
GRID_FAR_M = 3.0

# T-024 선회 화살표 (하단 중앙 타원 호, 하단 안내 띠 34px 위)
PIVOT_ARROW_BOTTOM_PX = 95
PIVOT_ARROW_RX_PX = 90
PIVOT_ARROW_RY_PX = 34
PIVOT_ARROW_MIN_SWEEP_DEG = 40       # 작은 선회도 방향이 보이게
PIVOT_ARROW_MAX_SWEEP_DEG = 200
PIVOT_ARROW_SEGMENTS = 24
PIVOT_ARROW_PX = 6
PIVOT_ARROW_TIP = 1.4                # 마지막 4점 구간 기준 화살촉 비율

# BGR (Unity 경로 띠와 같은 의미 색)
LEVEL_COLORS = {"GREEN": (102, 204, 31), "YELLOW": (38, 194, 250), "RED": (51, 31, 230), "NONE": (102, 204, 31)}
PREDICTED_COLOR = (255, 242, 235)
ALT_COLOR = (60, 120, 25)
GRID_COLOR = (0, 255, 255)
OUTLINE_COLOR = (0, 0, 0)


@dataclass
class CameraModel:
    width: int = 640
    height: int = 480
    hfov_deg: float = PI_CAM_V2_HFOV_DEG
    vfov_deg: float = PI_CAM_V2_VFOV_DEG
    mount_height_m: float = DEFAULT_CAMERA_HEIGHT_M
    pitch_deg: float = DEFAULT_CAMERA_PITCH_DEG
    forward_m: float = DEFAULT_CAMERA_FORWARD_M

    @property
    def fx(self) -> float:
        return (self.width / 2) / math.tan(math.radians(self.hfov_deg / 2))

    @property
    def fy(self) -> float:
        return (self.height / 2) / math.tan(math.radians(self.vfov_deg / 2))

    def project(self, floor_xy: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """바닥 점 (N,2) → 픽셀 (N,2) float, 유효 마스크 (카메라 앞쪽)."""
        if floor_xy.size == 0:
            return np.empty((0, 2)), np.zeros(0, bool)
        th = math.radians(self.pitch_deg)
        vx = floor_xy[:, 0] - self.forward_m          # 카메라 → 점 (전방)
        vy = floor_xy[:, 1]                            # 좌측
        vz = -self.mount_height_m                      # 바닥은 카메라 아래
        depth = vx * math.cos(th) - vz * math.sin(th)  # 광축 방향 거리 (아래로 숙임 반영)
        up = vx * math.sin(th) + vz * math.cos(th)     # 영상 위쪽 성분
        valid = depth > MIN_DEPTH_M
        d = np.where(valid, depth, np.nan)
        u = self.width / 2 - self.fx * vy / d
        v = self.height / 2 - self.fy * up / d
        return np.stack([u, v], axis=1), valid

    def nearest_visible_floor_m(self) -> float:
        """영상 아래 끝에 보이는 바닥까지 거리 (렌즈 기준, m). 바닥이 안 보이면 inf."""
        a = math.radians(self.pitch_deg + self.vfov_deg / 2)
        return self.mount_height_m / math.tan(a) if a > 0 else math.inf


def ribbon_polygon(center_xy: np.ndarray, half_width: float) -> np.ndarray:
    """중심선 (N,2) → 좌·우 테두리 다각형 (2N,2), 로봇 좌표."""
    d = np.gradient(center_xy, axis=0)
    n = np.stack([-d[:, 1], d[:, 0]], axis=1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    left, right = center_xy + n * half_width, center_xy - n * half_width
    return np.vstack([left, right[::-1]])


def _visible_prefix(cam: CameraModel, center_xy: np.ndarray, margin_m: float = 0.0) -> np.ndarray:
    """렌즈보다 margin_m 이상 앞에 있는 중심선 점만 (띠 테두리가 카메라 뒤로 넘어가지 않게)."""
    keep = np.flatnonzero(center_xy[:, 0] - cam.forward_m > MIN_DEPTH_M + margin_m)
    return center_xy[keep] if keep.size else center_xy[:0]


def draw_ribbon(frame: np.ndarray, cam: CameraModel, center_xy: np.ndarray, half_width: float, color) -> None:
    """로봇 폭 반투명 띠 + 검은 외곽선·색 테두리 (원근 반영)."""
    pts = _visible_prefix(cam, center_xy, margin_m=half_width)
    if len(pts) < 2:
        return
    px, valid = cam.project(ribbon_polygon(pts, half_width))
    if not valid.all():
        return
    poly = np.round(px).astype(np.int32)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [poly], color)
    cv2.addWeighted(overlay, RIBBON_FILL_ALPHA, frame, 1 - RIBBON_FILL_ALPHA, 0, frame)
    cv2.polylines(frame, [poly], True, OUTLINE_COLOR, RIBBON_EDGE_PX + 2, cv2.LINE_AA)
    cv2.polylines(frame, [poly], True, color, RIBBON_EDGE_PX, cv2.LINE_AA)


def draw_centerline(frame: np.ndarray, cam: CameraModel, center_xy: np.ndarray, color, thickness: int) -> None:
    pts = _visible_prefix(cam, center_xy)
    if len(pts) < 2:
        return
    px, _ = cam.project(pts)
    line = np.round(px).astype(np.int32)
    cv2.polylines(frame, [line], False, OUTLINE_COLOR, thickness + 2, cv2.LINE_AA)
    cv2.polylines(frame, [line], False, color, thickness, cv2.LINE_AA)


def draw_paths(frame: np.ndarray, cam: CameraModel, half_width: float,
               recommended: Optional[np.ndarray], recommended_level: str,
               predicted: Optional[np.ndarray], alternatives: Sequence[np.ndarray]) -> None:
    """대안(얇은 선) → 추천(신뢰도 색 띠) → 예상(흰 중심선) 순서로 그림."""
    for alt in alternatives:
        draw_centerline(frame, cam, alt, ALT_COLOR, ALT_LINE_PX)
    if recommended is not None and len(recommended):
        draw_ribbon(frame, cam, recommended, half_width, LEVEL_COLORS.get(recommended_level, LEVEL_COLORS["GREEN"]))
    if predicted is not None and len(predicted):
        draw_centerline(frame, cam, predicted, PREDICTED_COLOR, PREDICTED_LINE_PX)


def draw_pivot(frame: np.ndarray, cam: CameraModel, half_width: float,
               pivot_xy: np.ndarray, level: str, pivot_deg: float) -> None:
    """T-024 제자리 선회 추천: 선회 방향 곡선 화살표 (휘는 정도 = 선회량, 수치 미표시) + 화각 안 직진 띠."""
    color = LEVEL_COLORS.get(level, LEVEL_COLORS["GREEN"])
    draw_ribbon(frame, cam, pivot_xy, half_width, color)
    left = pivot_deg > 0
    sweep = math.radians(min(PIVOT_ARROW_MAX_SWEEP_DEG, max(PIVOT_ARROW_MIN_SWEEP_DEG, abs(pivot_deg))))
    cx, cy = cam.width / 2, cam.height - PIVOT_ARROW_BOTTOM_PX
    a, b = PIVOT_ARROW_RX_PX, PIVOT_ARROW_RY_PX
    # 화면 위쪽 꼭짓점(−90°)에서 시작해 좌(반시계)/우(시계)로 sweep만큼 휘는 타원 호
    t = np.linspace(0.0, sweep, PIVOT_ARROW_SEGMENTS)
    theta = -math.pi / 2 - t if left else -math.pi / 2 + t
    arc = np.round(np.stack([cx + a * np.cos(theta), cy + b * np.sin(theta)], axis=1)).astype(np.int32)
    for col, px in ((OUTLINE_COLOR, PIVOT_ARROW_PX + 4), (color, PIVOT_ARROW_PX)):
        cv2.polylines(frame, [arc[:-3]], False, col, px, cv2.LINE_AA)
        cv2.arrowedLine(frame, tuple(arc[-4]), tuple(arc[-1]), col, px, cv2.LINE_AA, tipLength=PIVOT_ARROW_TIP)


def draw_calibration_grid(frame: np.ndarray, cam: CameraModel) -> None:
    """바닥 거리선·측면선. 바닥에 같은 위치로 테이프를 붙이고 선과 겹치도록 피치·높이 조정."""
    for dist in GRID_DISTANCES_M:
        seg = np.array([[dist + cam.forward_m, -1.0], [dist + cam.forward_m, 1.0]])
        px, valid = cam.project(seg)
        if valid.all():
            p = np.round(px).astype(np.int32)
            cv2.line(frame, tuple(p[0]), tuple(p[1]), GRID_COLOR, 1, cv2.LINE_AA)
            y = int(p[0][1]) - 4
            if 12 < y < cam.height:
                cv2.putText(frame, f"{dist:.1f} m", (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, OUTLINE_COLOR, 3)
                cv2.putText(frame, f"{dist:.1f} m", (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GRID_COLOR, 1)
    for lat in (-GRID_LATERAL_M, GRID_LATERAL_M):
        seg = np.array([[cam.forward_m + max(0.2, cam.nearest_visible_floor_m()), lat], [cam.forward_m + GRID_FAR_M, lat]])
        px, valid = cam.project(seg)
        if valid.all():
            p = np.round(px).astype(np.int32)
            cv2.line(frame, tuple(p[0]), tuple(p[1]), GRID_COLOR, 1, cv2.LINE_AA)
    info = f"CALIB h={cam.mount_height_m:.2f}m pitch={cam.pitch_deg:.0f}deg fwd={cam.forward_m:.2f}m  near floor {cam.nearest_visible_floor_m():.2f}m"
    cv2.putText(frame, info, (10, cam.height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, OUTLINE_COLOR, 3)
    cv2.putText(frame, info, (10, cam.height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRID_COLOR, 1)
