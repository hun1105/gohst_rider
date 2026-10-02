"""
make_figures.py — 제출 문서용 도식 생성 (docs/assets/)
사용: python tools/make_figures.py
- fig_architecture.png   : 시스템 아키텍처
- fig_escape_planner.png : 탈출 경로 알고리즘 (실제 escape_planner.plan_escape 계산 결과)
- placeholder_cap_*.png  : 촬영 캡처 자리 (docs/assets/cap_*.jpg 넣으면 문서 빌드 시 자동 교체)
"""

import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ai_relay_server"))
from escape_planner import (  # noqa: E402
    MIN_CLEARANCE_M, PATH_HORIZON_M, ROBOT_HALF_WIDTH_M, TURN_PENALTY_M_PER_RAD, HEADING_STEP_DEG,
    ScanData, _valid_points, free_length, plan_escape,
)

ASSETS = os.path.join(ROOT, "docs", "assets")
INK, SLATE, MUTED, PANEL, LINE = "#1F242B", "#4A5562", "#7A8490", "#EEF1F4", "#C9D0D8"
RED, GREEN, WHITE, DARK = "#C8102E", "#1E8C45", "#FFFFFF", "#1F242B"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

CAPTURE_SLOTS = {
    "cap_cockpit_stop": ("콕핏 화면 캡처", "Scene 3 — 적색 정지 배너 + 녹색 탈출 경로", 4 / 3),
    "cap_map_stuck": ("PC 관제 맵 캡처", "Scene 3 — 적색 로봇·위험 원판·사이드바 정지 원인", 16 / 9),
    "cap_field_robot": ("현장 사진", "실물 TurtleBot3 + 장애물 배치 (AUTO 배회 구역)", 16 / 9),
    "cap_vr_takeover": ("Quest 미러 캡처", "Scene 4 — 착용자 콕핏 시점 수동 탈출", 16 / 9),
}


def box(ax, x, y, w, h, title, lines=(), fill=PANEL, title_color=INK, text_color=SLATE, fs=11, title_fs=13):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill, ec=LINE if fill != DARK else DARK, lw=1.2))
    ax.text(x + 0.15, y + h - 0.18, title, ha="left", va="top", fontsize=title_fs, weight="bold", color=title_color)
    for k, t in enumerate(lines):
        ax.text(x + 0.18, y + h - 0.62 - k * 0.36, t, ha="left", va="top", fontsize=fs, color=text_color)


def arrow(ax, x1, y1, x2, y2, both=False, color=SLATE, lw=2.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="<|-|>" if both else "-|>",
                                 mutation_scale=16, color=color, lw=lw))


def fig_architecture():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    ax.set_xlim(0, 16); ax.set_ylim(0, 9); ax.axis("off")
    ax.text(0.4, 8.6, "시스템 아키텍처", fontsize=22, weight="bold", color=INK, va="top")
    ax.text(0.4, 8.05, "Unity 디지털 트윈 ↔ AI 릴레이 에이전트 ↔ TurtleBot3 실기", fontsize=12, color=MUTED, va="top")

    # 좌: Unity
    box(ax, 0.4, 1.0, 3.7, 6.4, "Unity 6 디지털 트윈", [
        "PC 모니터 — 탑다운 관제 맵", "   · 사이드바 HUD (정지 원인·탈출 방향)", "   · 마우스 피킹 → 조종 권한 이양",
        "Quest 2 HMD — 선택 로봇 콕핏 1인칭", "   · 카메라 영상 + 경고 오버레이", "DualDisplayController",
        "   · XR 활성 시 PC/HMD 화면 분리", "입력: WASD · 썸스틱 · R/Y · A/X",
        "WebSocketManager (자동 재접속)",
    ], fs=10.5)

    # 중: 릴레이
    ax.add_patch(FancyBboxPatch((5.35, 1.0), 5.3, 6.4, boxstyle="round,pad=0.02,rounding_size=0.08", fc=DARK, ec=DARK))
    ax.text(5.5, 7.22, "AI 릴레이 에이전트 (Python asyncio)", fontsize=13, weight="bold", color=WHITE, va="top")
    gates = [("조종 권한 (SELECT_ROBOT)", SLATE), ("장애물 정지·알림 (STOP)", RED), ("AUTO 상태머신", SLATE),
             ("워치독 0.5s", SLATE), ("로봇 간 거리 1.0m", SLATE), ("속도 상한 0.15 m/s", SLATE),
             ("LiDAR 가드 전방 0.35 / 후방 0.20m", RED), ("통신 두절 정지 (odom 0.5s)", SLATE)]
    gx, gy0, gw, gh = 5.55, 6.3, 2.75, 0.5
    ax.text(gx, gy0 + 0.12, "안전 게이트 (20 Hz, 위→아래)", fontsize=9.5, color="#C9D0D8", va="bottom")
    for k, (g, c) in enumerate(gates):
        y = gy0 - k * 0.62
        ax.add_patch(FancyBboxPatch((gx, y - gh), gw, gh, boxstyle="round,pad=0.01,rounding_size=0.06", fc=c, ec=c))
        ax.text(gx + gw / 2, y - gh / 2, g, ha="center", va="center", fontsize=9.2, color=WHITE, weight="bold")
        if k < len(gates) - 1:
            ax.annotate("", xy=(gx + gw / 2, y - gh - 0.1), xytext=(gx + gw / 2, y - gh), arrowprops=dict(arrowstyle="-|>", color="#C9D0D8", lw=1))
    ax.text(gx + gw / 2, 1.12, "→ /cmd_vel 20 Hz", ha="center", fontsize=10, color=WHITE, weight="bold")
    side = [("LiDAR 360°\n탈출 경로 플래너", GREEN), ("영상 오버레이\n(배너·경로)", SLATE),
            ("YOLOv8 회랑 검출\n(선택)", SLATE), ("rosbridge 링크\n(재접속)", SLATE)]
    for k, (t, c) in enumerate(side):
        y = 6.05 - k * 1.05
        ax.add_patch(FancyBboxPatch((8.5, y - 0.8), 1.95, 0.8, boxstyle="round,pad=0.01,rounding_size=0.06", fc=c, ec=c))
        ax.text(9.475, y - 0.4, t, ha="center", va="center", fontsize=9, color=WHITE, weight="bold", linespacing=1.3)

    # 우: 로봇
    box(ax, 11.9, 1.0, 3.7, 6.4, "TurtleBot3 Burger", [
        "Raspberry Pi 4 · Ubuntu 22.04", "ROS 2 Humble", "turtlebot3_bringup", "   · /odom  /cmd_vel  (OpenCR)",
        "LDS-02 LiDAR → /scan (360°)", "rosbridge_server :9090", "Pi Camera v2 (imx219)",
        "   · ustreamer :8080 (YUYV→JPEG)", "   · 640×480 · 15.7 fps",
    ], fs=10.5)

    # 연결
    arrow(ax, 4.2, 4.6, 5.25, 4.6, both=True)
    ax.text(4.725, 4.85, "WebSocket\n:9090", ha="center", va="bottom", fontsize=9, color=SLATE, weight="bold", linespacing=1.2)
    ax.text(4.725, 4.35, "JSON 20Hz\nJPEG 영상", ha="center", fontsize=8.5, color=MUTED, va="top", linespacing=1.2)
    arrow(ax, 10.75, 4.6, 11.8, 4.6, both=True)
    ax.text(11.275, 4.85, "rosbridge\n:9090", ha="center", va="bottom", fontsize=9, color=SLATE, weight="bold", linespacing=1.2)
    ax.text(11.275, 4.35, "/odom /scan ▲\n/cmd_vel ▼", ha="center", fontsize=8.5, color=MUTED, va="top", linespacing=1.2)
    arrow(ax, 11.8, 2.0, 10.75, 2.0)
    ax.text(11.275, 2.2, "HTTP MJPEG\n:8080", ha="center", va="bottom", fontsize=8.5, color=MUTED, linespacing=1.2)
    ax.text(8.0, 0.45, "Unity → 릴레이: TWIST · STOP · SELECT_ROBOT · AUTO · TELEPORT     릴레이 → Unity: 텔레메트리(포즈·LiDAR·안전·모드) + 영상",
            ha="center", fontsize=10, color=SLATE)
    path = os.path.join(ASSETS, "fig_architecture.png")
    fig.savefig(path, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    # 발표자료용: 그림 내 제목·부제 제외 (슬라이드 제목과 중복 방지). 박스 상단(y=7.4) 위쪽을 픽셀 기준으로 잘라냄
    from PIL import Image
    im = Image.open(path)
    top = int(im.height * (1 - (7.55 - 0.0) / 9.0))   # 데이터 y 7.55 ≈ 박스 상단 바로 위
    im.crop((0, max(0, top), im.width, im.height)).save(os.path.join(ASSETS, "fig_architecture_body.png"))
    return path


def fig_agent_loop():
    """AI Agent 6요소 루프: Goal → 인지 → 추론 → 계획 → 실행(Tool) → 피드백, 중앙 Memory, 사람 개입."""
    fig, ax = plt.subplots(figsize=(16, 8.2), dpi=120)
    ax.set_xlim(0, 16); ax.set_ylim(0, 8.2); ax.axis("off")
    # Goal 띠
    ax.add_patch(FancyBboxPatch((0.4, 7.05), 15.2, 0.95, boxstyle="round,pad=0.02,rounding_size=0.1", fc=DARK, ec=DARK))
    ax.text(0.7, 7.52, "GOAL", fontsize=12, weight="bold", color="#9FD3B1", va="center")
    ax.text(1.8, 7.52, "AGV 2대 운용 중 작업자 협착·충돌 0건, 장애물 봉착 시 사람과 함께 무사고 탈출",
            fontsize=14, weight="bold", color=WHITE, va="center")
    steps = [
        ("1  인지 (Tool)", ["LiDAR /scan 360°", "/odom 20 Hz", "카메라 640×480 (ustreamer)"], SLATE),
        ("2  추론", ["섹터 최소거리 ±30°", "로봇 폭 회랑 여유", "tb1↔tb2 거리 · YOLOv8"], SLATE),
        ("3  계획", ["AUTO 상태기계", "곡률 샘플링 추천 궤적", "탈출 방향 argmax"], GREEN),
        ("4  실행 (Tool)", ["안전 게이트 8단", "/cmd_vel 20 Hz (rosbridge)", "정지·전진 차단"], RED),
        ("5  피드백", ["영상 위 경로 띠·적색 배너", "지도 적색 차체·위험 원판", "사이드바 · 컨트롤러 진동"], SLATE),
    ]
    w, h, y = 2.75, 2.35, 3.95
    xs = [0.4 + k * (w + 0.36) for k in range(5)]
    for x, (title, lines, c) in zip(xs, steps):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc=PANEL, ec=c, lw=2.2))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.6), w, 0.6, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c, ec=c))
        ax.text(x + 0.15, y + h - 0.3, title, fontsize=12.5, weight="bold", color=WHITE, va="center")
        for k, t in enumerate(lines):
            ax.text(x + 0.18, y + h - 0.95 - k * 0.42, t, fontsize=10.5, color=INK, va="center")
    for k in range(4):
        x0 = xs[k] + w + 0.02
        ax.add_patch(FancyArrowPatch((x0, y + h / 2), (x0 + 0.32, y + h / 2), arrowstyle="-|>", mutation_scale=16, color=SLATE, lw=2))
    # Memory (하단 중앙)
    ax.add_patch(FancyBboxPatch((3.6, 1.15), 8.8, 1.9, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#FFF7E6", ec="#E0A526", lw=2))
    ax.text(3.85, 2.75, "MEMORY / STATE", fontsize=12, weight="bold", color="#9A6A00", va="center")
    mem = ["주행 모드 MANUAL/AUTO · AUTO 상태 CRUISE/AVOID/RETURN/STUCK", "정지 원인(reason) · 배회 구역 중심 · 위치 원점(RESET_POSE)",
           "로봇별 최신 포즈·스캔·통신 생존 시각 · 운행 이력 로그(이벤트 + 1 Hz JSONL)"]
    for k, t in enumerate(mem):
        ax.text(3.85, 2.35 - k * 0.42, t, fontsize=10.5, color=INK, va="center")
    for x in (xs[1] + w / 2, xs[2] + w / 2, xs[3] + w / 2):
        ax.add_patch(FancyArrowPatch((x, y - 0.05), (x if x < 12.4 else 12.3, 3.1), arrowstyle="<|-|>", mutation_scale=12, color="#E0A526", lw=1.5))
    # 사람 개입 루프
    ax.add_patch(FancyArrowPatch((xs[4] + w / 2, y - 0.05), (xs[4] + w / 2, 0.55), arrowstyle="-", color=GREEN, lw=2))
    ax.add_patch(FancyArrowPatch((xs[4] + w / 2, 0.55), (xs[0] + w / 2, 0.55), arrowstyle="-", color=GREEN, lw=2))
    ax.add_patch(FancyArrowPatch((xs[0] + w / 2, 0.55), (xs[0] + w / 2, y - 0.05), arrowstyle="-|>", mutation_scale=16, color=GREEN, lw=2))
    ax.text(8.0, 0.25, "사람 개입: 관제 맵 클릭 → Quest 콕핏 빙의 → 그립 데드맨 + 트리거로 수동 탈출 → Y로 AUTO 재개",
            ha="center", fontsize=11, color=GREEN, weight="bold")
    path = os.path.join(ASSETS, "fig_agent_loop.png")
    fig.savefig(path, bbox_inches="tight", facecolor=WHITE); plt.close(fig)
    return path


def sample_scan():
    """전방 정면 상자 + 우측 벽 + 좌후방 기둥 (LDS 형식: 0° 전방, 1° 간격, 반시계 +)."""
    r = np.full(360, 3.0)
    for d in range(360):
        a = math.radians(d)
        if -20 <= ((d + 180) % 360) - 180 <= 20:            # 전방 상자 (0.42m)
            r[d] = min(r[d], 0.42 / max(math.cos(a), 0.3))
        y_wall = -0.55                                       # 우측 벽 y = -0.55m
        if math.sin(a) < -0.05:
            r[d] = min(r[d], y_wall / math.sin(a))
        dx, dy = -0.6, 0.7                                   # 좌후방 기둥
        b = math.atan2(dy, dx); dist = math.hypot(dx, dy)
        if abs(math.atan2(math.sin(a - b), math.cos(a - b))) < math.radians(9):
            r[d] = min(r[d], dist)
    return ScanData(list(r), 0.0, math.radians(1), 0.12, 3.5)


def fig_escape_planner():
    scan = sample_scan()
    pts = _valid_points(scan)
    best = plan_escape(scan)
    heads = np.radians(np.arange(-180, 180, HEADING_STEP_DEG))
    free = np.array([free_length(pts, h) for h in heads])
    score = np.where(free >= MIN_CLEARANCE_M, free - TURN_PENALTY_M_PER_RAD * np.abs(heads), np.nan)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 7), dpi=120, gridspec_kw={"width_ratios": [1, 1.25]})
    # (a) 평면도: 로봇 좌표 (x 전방 = 위, y 좌측 = 왼쪽) → 화면 (X=-y, Y=x)
    a1.set_aspect("equal"); a1.set_xlim(-1.6, 1.6); a1.set_ylim(-1.3, 1.9)
    a1.set_facecolor("#FAFBFC"); a1.tick_params(labelsize=9, colors=MUTED)
    for s in a1.spines.values(): s.set_color(LINE)
    a1.set_xlabel("좌 ← y (m) → 우", fontsize=10, color=SLATE); a1.set_ylabel("x 전방 (m)", fontsize=10, color=SLATE)
    for h, f in zip(heads, free):
        ok = f >= MIN_CLEARANCE_M
        a1.plot([0, -math.sin(h) * f], [0, math.cos(h) * f], color=("#9FD3B1" if ok else "#F2B8C1"), lw=1, zorder=1)
    a1.scatter(-pts[:, 1], pts[:, 0], s=7, color=INK, zorder=3, label="LiDAR 점")
    if best:
        h, d = best.heading_rad, best.clearance_m
        ux, uy = -math.sin(h), math.cos(h); px, py = math.cos(h), math.sin(h)   # 진행·수직 (화면 좌표)
        w = ROBOT_HALF_WIDTH_M
        corridor = [(w * px, w * py), (w * px + d * ux, w * py + d * uy), (-w * px + d * ux, -w * py + d * uy), (-w * px, -w * py)]
        a1.add_patch(Polygon(corridor, closed=True, fc=GREEN, ec=GREEN, alpha=0.28, zorder=2))
        a1.annotate("", xy=(d * ux, d * uy), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=3), zorder=4)
        a1.text(d * ux, d * uy + 0.08, f"h* = {best.heading_deg:+.0f}°\n여유 {d:.2f} m", color=GREEN, fontsize=11, weight="bold", ha="center")
    a1.add_patch(Circle((0, 0), 0.105, fc=WHITE, ec=INK, lw=2, zorder=5))
    a1.annotate("", xy=(0, 0.2), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5), zorder=6)
    a1.set_title("(a) 후보 방향별 로봇 폭 회랑 검사 (5° 간격)", fontsize=13, color=INK, loc="left", weight="bold")
    a1.plot([], [], color="#9FD3B1", label=f"통과 가능 (여유 ≥ {MIN_CLEARANCE_M} m)")
    a1.plot([], [], color="#F2B8C1", label="통과 불가")
    a1.legend(loc="lower right", fontsize=9, frameon=False)

    # (b) 방향별 여유거리와 비용
    deg = np.degrees(heads)
    a2.plot(deg, free, color=SLATE, lw=1.8, label="여유거리 d(h)")
    a2.plot(deg, score, color=GREEN, lw=2.4, label=f"비용 J(h) = d(h) - {TURN_PENALTY_M_PER_RAD}·|h|")
    a2.axhline(MIN_CLEARANCE_M, color=RED, lw=1, ls="--"); a2.text(-178, MIN_CLEARANCE_M + 0.03, "최소 여유 0.5 m", color=RED, fontsize=9)
    a2.axhline(PATH_HORIZON_M, color=LINE, lw=1, ls=":"); a2.text(-178, PATH_HORIZON_M + 0.03, "탐색 한계 1.5 m", color=MUTED, fontsize=9)
    if best:
        a2.axvline(best.heading_deg, color=GREEN, lw=1, ls="--")
        a2.scatter([best.heading_deg], [best.clearance_m - TURN_PENALTY_M_PER_RAD * abs(best.heading_rad)], s=60, color=GREEN, zorder=5)
        a2.text(best.heading_deg + 4, 1.62, f"argmax → {best.heading_deg:+.0f}°", color=GREEN, fontsize=11, weight="bold")
    a2.set_xlim(-180, 180); a2.set_ylim(-0.2, 1.8); a2.set_xticks(range(-180, 181, 45))
    a2.set_xlabel("후보 방향 h (°, +좌 / -우)", fontsize=10, color=SLATE); a2.set_ylabel("m", fontsize=10, color=SLATE)
    a2.tick_params(labelsize=9, colors=MUTED); a2.grid(color="#E6E9ED", lw=0.8)
    for s in a2.spines.values(): s.set_color(LINE)
    a2.legend(loc="lower center", fontsize=9.5, frameon=False, ncol=2)
    a2.set_title("(b) 방향별 여유거리·비용 — 최대값 방향 선택", fontsize=13, color=INK, loc="left", weight="bold")
    fig.tight_layout()
    path = os.path.join(ASSETS, "fig_escape_planner.png")
    fig.savefig(path, bbox_inches="tight", facecolor=WHITE); plt.close(fig)
    return path, best


def placeholders():
    out = []
    for name, (title, desc, aspect) in CAPTURE_SLOTS.items():
        w = 8.0; h = w / aspect
        fig, ax = plt.subplots(figsize=(w, h), dpi=110)
        ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.15, 0.15), w - 0.3, h - 0.3, boxstyle="round,pad=0,rounding_size=0.15",
                                    fc="#F4F6F8", ec="#9AA4AF", lw=2, ls=(0, (6, 4))))
        ax.text(w / 2, h / 2 + 0.45, title, ha="center", va="center", fontsize=22, weight="bold", color=SLATE)
        ax.text(w / 2, h / 2 - 0.15, desc, ha="center", va="center", fontsize=13, color=MUTED)
        ax.text(w / 2, h / 2 - 0.75, f"docs/assets/{name}.jpg 넣고 재빌드", ha="center", va="center", fontsize=11, color="#9AA4AF")
        path = os.path.join(ASSETS, f"placeholder_{name}.png")
        fig.savefig(path, facecolor=WHITE); plt.close(fig)
        out.append(path)
    return out


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    print(fig_architecture())
    print(fig_agent_loop())
    p, best = fig_escape_planner()
    print(p, f"→ h*={best.heading_deg:+.0f}°, 여유 {best.clearance_m:.2f} m" if best else "→ 경로 없음")
    for p in placeholders():
        print(p)
