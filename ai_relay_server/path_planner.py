"""
곡률 샘플링 궤적 추천 + 예상 궤적 (T-019)
==========================================
- 창고 환경: 차선 없음 → LiDAR 빈 공간 기하로 판단 (학습 모델 불필요).
- DWA(Fox·Burgard·Thrun, 1997) 계열의 궤적 롤아웃을 '곡률(κ = ω/v)'로 표현:
  속도와 무관하게 길이 1.2m 원호를 그려 화면에 일정한 길이의 경로 띠로 표시.
- 추천: 곡률 후보 25개 중 (자유 길이 + 여유 − 곡률 감점) 최대.
- 예상: 현재 지령 (v, ω)를 유지할 때의 원호 (수동 운전 가이드선).
- 신뢰도: 로봇 반경 기준 충돌 위치·여유 거리로 GREEN / YELLOW / RED.
- 선회 추천(T-024): 전진 후보가 전부 RED면 탈출 방향으로 제자리 선회 후 직진 궤적.
- 로봇을 움직이지 않음. 표시·판단 보조용.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

ROBOT_RADIUS_M = 0.13            # Burger 외접 반경 약 0.105m + 여유
PATH_LENGTH_M = 1.2              # 표시 궤적 길이
PATH_STEP_M = 0.05               # 궤적 점 간격
CURVATURE_MAX = 3.0              # 1/m (반경 0.33m 선회까지)
CURVATURE_SAMPLES = 25
MAX_ARC_TURN_RAD = math.radians(120)   # 원호 최대 회전각 (급선회 띠는 짧게)
RED_FREE_M = 0.5                 # 이 거리 안 충돌 → RED
YELLOW_CLEARANCE_M = 0.08        # 여유가 이보다 작으면 YELLOW
CLEARANCE_SCORE_CAP_M = 0.3
W_CLEARANCE = 0.5
W_CURVATURE = 0.08               # 같은 조건이면 곧은 경로 우선
ALT_MIN_CURVATURE_GAP = 1.0      # 대안 궤적 간 최소 곡률 차
MAX_ALTERNATIVES = 2
MIN_LINEAR_FOR_PREDICTION = 0.02  # 이보다 느리면 예상 궤적 없음 (제자리 회전 포함)
PIVOT_SWEEP_MARGIN_M = 0.03      # 제자리 선회 공간: 로봇 반경 + 이 여유 안에 LiDAR 점 없어야 함

GREEN, YELLOW, RED, NONE = "GREEN", "YELLOW", "RED", "NONE"
MODE_FORWARD, MODE_PIVOT, MODE_NONE = "FORWARD", "PIVOT", "NONE"


@dataclass
class Trajectory:
    curvature: float
    points: np.ndarray           # (N, 2) 로봇 좌표 (x 전방, y 좌측)
    free_length: float           # 첫 충돌까지 길이 (충돌 없음 = PATH_LENGTH_M)
    clearance: float             # 충돌 전 구간의 최소 여유 (반경 제외)
    level: str
    score: float


def arc_length(curvature: float) -> float:
    """원호 길이: 기본 PATH_LENGTH_M, 급선회는 회전각 MAX_ARC_TURN_RAD에서 자름 (띠가 말려 보이지 않게)."""
    return PATH_LENGTH_M if abs(curvature) < 1e-6 else min(PATH_LENGTH_M, MAX_ARC_TURN_RAD / abs(curvature))


def arc_points(curvature: float) -> np.ndarray:
    """전진 원호 점 (로봇 좌표). 양의 곡률 = 좌회전."""
    s = np.arange(PATH_STEP_M, arc_length(curvature) + 1e-9, PATH_STEP_M)
    if abs(curvature) < 1e-6:
        x, y = s, np.zeros_like(s)
    else:
        x = np.sin(curvature * s) / curvature
        y = (1.0 - np.cos(curvature * s)) / curvature
    return np.stack([x, y], axis=1)


def evaluate(points_xy: np.ndarray, traj: np.ndarray, curvature: float) -> Trajectory:
    """궤적 각 점에서 LiDAR 점까지 최소 거리로 충돌·여유·신뢰도 계산."""
    if points_xy.size == 0:
        d = np.full(len(traj), np.inf)
    else:
        diff = traj[:, None, :] - points_xy[None, :, :]
        d = np.sqrt((diff ** 2).sum(axis=2)).min(axis=1)
    total = len(traj) * PATH_STEP_M
    hit = np.nonzero(d < ROBOT_RADIUS_M)[0]
    if hit.size:
        k = int(hit[0])
        free = k * PATH_STEP_M
        clearance = float(d[:k].min() - ROBOT_RADIUS_M) if k > 0 else 0.0
    else:
        free = total
        clearance = float(min(d.min() - ROBOT_RADIUS_M, CLEARANCE_SCORE_CAP_M))
    if free < min(RED_FREE_M, total):
        level = RED
    elif free < total - 1e-9 or clearance < YELLOW_CLEARANCE_M:
        level = YELLOW
    else:
        level = GREEN
    score = free + W_CLEARANCE * min(clearance, CLEARANCE_SCORE_CAP_M) - W_CURVATURE * abs(curvature)
    return Trajectory(curvature, traj, free, clearance, level, score)


def recommend(points_xy: np.ndarray) -> Tuple[Optional[Trajectory], List[Trajectory]]:
    """곡률 후보 롤아웃 → (추천, 대안 목록). 전부 RED면 (None, [])."""
    cands = [evaluate(points_xy, arc_points(k), k)
             for k in np.linspace(-CURVATURE_MAX, CURVATURE_MAX, CURVATURE_SAMPLES)]
    viable = sorted((c for c in cands if c.level != RED), key=lambda c: c.score, reverse=True)
    if not viable:
        return None, []
    best = viable[0]
    alts: List[Trajectory] = []
    for c in viable[1:]:
        if all(abs(c.curvature - o.curvature) >= ALT_MIN_CURVATURE_GAP for o in [best] + alts):
            alts.append(c)
        if len(alts) >= MAX_ALTERNATIVES:
            break
    return best, alts


def predict(points_xy: np.ndarray, linear: float, angular: float) -> Optional[Trajectory]:
    """현재 지령 유지 시 예상 궤적. 후진이면 뒤쪽 원호."""
    if abs(linear) < MIN_LINEAR_FOR_PREDICTION:
        return None
    # 이동 거리 s 기준 헤딩 변화율 κ = ω/|v|. 후진은 x·y 모두 반전:
    # x = −sin(κs)/κ, y = −(1−cos κs)/κ  (ω>0 후진 → 뒤쪽 오른편으로 휨)
    k = max(-CURVATURE_MAX, min(CURVATURE_MAX, angular / abs(linear)))
    traj = arc_points(k)
    if linear < 0:
        traj = -traj
    return evaluate(points_xy, traj, k)


def can_pivot(points_xy: np.ndarray) -> bool:
    """제자리 선회 시 차체가 쓸고 지나가는 원(반경 + 여유) 안에 장애물이 없으면 True."""
    if points_xy.size == 0:
        return True
    return bool(np.sqrt((points_xy ** 2).sum(axis=1)).min() >= ROBOT_RADIUS_M + PIVOT_SWEEP_MARGIN_M)


def pivot_path(points_xy: np.ndarray, heading_rad: float) -> Optional[Trajectory]:
    """제자리에서 heading만큼 선회한 뒤 직진하는 궤적 (선회 공간 없으면 None)."""
    if not can_pivot(points_xy):
        return None
    straight = arc_points(0.0)
    c, s = math.cos(heading_rad), math.sin(heading_rad)
    rotated = np.stack([straight[:, 0] * c - straight[:, 1] * s, straight[:, 0] * s + straight[:, 1] * c], axis=1)
    return evaluate(points_xy, rotated, 0.0)


def to_world(points_xy: np.ndarray, x: float, z: float, yaw_deg: float, decimals: int = 2) -> List[float]:
    """로봇 좌표 (x 전방, y 좌측) → Unity 월드 평탄 배열 [x0, z0, …]. Unity yaw는 시계 방향 도."""
    if points_xy.size == 0:
        return []
    a = math.radians(yaw_deg)
    fwd = np.array([math.sin(a), math.cos(a)])        # Unity (x, z)
    right = np.array([math.cos(a), -math.sin(a)])
    w = np.array([x, z]) + points_xy[:, :1] * fwd - points_xy[:, 1:2] * right
    return [round(float(v), decimals) for v in w.reshape(-1)]
