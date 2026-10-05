"""
실물 TurtleBot3 odom·LiDAR 동기화 보정 (T-032)
================================================
시나리오: 로봇을 손 조작으로 정해진 실측 거리만큼 직진시키고, 멈춘 위치에서 앞 로봇까지의 실측 간격과
odom·LiDAR 값을 비교해 (1) odom 거리 배율, (2) LiDAR 측정 기준점 오프셋, (3) 출발 시 두 로봇 중심 간격을 계산한다.

기본값: Galaxy S20 FE 세로(159.8 mm) × 5 = 0.799 m 주행, 정지 후 앞 로봇과 간격 159.8 mm × 1.

※ 릴레이(run_relay_*.bat)를 반드시 끄고 실행 — 릴레이도 /cmd_vel을 20 Hz로 보내 서로 충돌함.
※ 로봇 측 ROS(start_tb1_robot.bat)는 켜 둔 상태여야 함.

조작 (이 창에 포커스):
  W (누르고 있기)  전진 0.05 m/s      S (누르고 있기)  후진
  A / D            제자리 좌/우 회전 (방향 맞출 때만, 측정 중엔 쓰지 말 것)
  Space            즉시 정지          Q / Esc          정지 후 종료·결과 계산
키를 떼면 0.25초 안에 자동 정지. 전방 LiDAR가 --stop-front-m 이하가 되면 전진 자동 차단.

실행 예:
  python tools/calibrate_tb.py                             # TB1 (172.30.1.58, ROS 1)
  python tools/calibrate_tb.py --url ws://172.30.1.28:9090 --ros 2 --robot tb2
"""

import argparse
import asyncio
import csv
import json
import math
import msvcrt
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_relay_server"))
from rosbridge_link import NO_RANGE, RosbridgeLink  # noqa: E402

PHONE_M = 0.1598                 # Galaxy S20 FE 세로 159.8 mm
BURGER_LENGTH_M = 0.138          # TurtleBot3 Burger 전장 (제원)
DRIVE_SPEED = 0.05               # 보정 주행 속도 (m/s) — 저속 고정
TURN_SPEED = 0.4                 # 방향 맞춤 회전 (rad/s)
KEY_HOLD_S = 0.25                # 마지막 키 입력 후 이 시간 지나면 정지 (키 반복 간격보다 김)
LOOP_S = 0.05                    # 20 Hz
CONNECT_TIMEOUT_S = 10.0


def wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


async def main(args) -> int:
    link = RosbridgeLink(args.robot, args.url, args.ros)
    task = asyncio.create_task(link.run())
    t0 = time.monotonic()
    while time.monotonic() - t0 < CONNECT_TIMEOUT_S and not (link.feedback.odom_stamp and link.feedback.scan_stamp):
        await asyncio.sleep(0.1)
    fb = link.feedback
    if not (fb.odom_stamp and fb.scan_stamp):
        print(f"[ERR] {args.url} 에서 odom/scan 수신 실패 — 로봇 ROS(start_*_robot.bat)가 켜져 있는지 확인")
        task.cancel()
        return 1

    os.makedirs(args.log_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.log_dir, f"calib_{args.robot}_{stamp}.csv")
    start = {"x": fb.x, "y": fb.y, "yaw": fb.yaw, "front": fb.front_min, "rear": fb.rear_min}
    print(f"[OK] 연결됨. 시작 odom ({fb.x:.3f}, {fb.y:.3f}) yaw {math.degrees(fb.yaw):.1f}°, "
          f"전방 LiDAR {fb.front_min:.3f} m, 후방 {fb.rear_min:.3f} m")
    print("     W 누르고 있기 = 전진, Space = 정지, Q = 종료·계산")

    lin = ang = 0.0
    last_key = 0.0
    blocked_logged = False
    t_start = time.monotonic()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "cmd_linear", "cmd_angular", "odom_x", "odom_y", "yaw_deg", "travel_m", "front_min", "rear_min"])
        try:
            while True:
                now = time.monotonic()
                while msvcrt.kbhit():
                    k = msvcrt.getwch().lower()
                    if k in ("q", "\x1b"):
                        raise KeyboardInterrupt
                    if k == " ":
                        lin = ang = 0.0
                        last_key = 0.0
                    elif k in ("w", "s", "a", "d"):
                        lin = {"w": DRIVE_SPEED, "s": -DRIVE_SPEED}.get(k, 0.0)
                        ang = {"a": TURN_SPEED, "d": -TURN_SPEED}.get(k, 0.0)
                        last_key = now
                if now - last_key > KEY_HOLD_S:
                    lin = ang = 0.0
                fb = link.feedback
                # 안전: 전방 근접 시 전진 차단 (LiDAR 데이터 없으면 전진 금지)
                if lin > 0 and (fb.front_min == NO_RANGE or fb.front_min <= args.stop_front_m):
                    lin = 0.0
                    if not blocked_logged:
                        print(f"[STOP] 전방 LiDAR {fb.front_min:.3f} m ≤ {args.stop_front_m} m → 전진 차단")
                        blocked_logged = True
                elif lin <= 0:
                    blocked_logged = False
                link.request_twist(lin, ang)
                travel = math.hypot(fb.x - start["x"], fb.y - start["y"])
                w.writerow([round(now - t_start, 3), lin, ang, round(fb.x, 4), round(fb.y, 4),
                            round(math.degrees(fb.yaw), 2), round(travel, 4), round(fb.front_min, 4), round(fb.rear_min, 4)])
                print(f"\r  odom 이동 {travel:6.3f} m | 전방 LiDAR {fb.front_min:6.3f} m | yaw 변화 "
                      f"{math.degrees(wrap(fb.yaw - start['yaw'])):+6.1f}°   ", end="", flush=True)
                await asyncio.sleep(LOOP_S)
        except KeyboardInterrupt:
            pass
        finally:
            await link.send_stop()
            await asyncio.sleep(0.3)
            await link.send_stop()
    print()
    task.cancel()

    fb = link.feedback
    odom_travel = math.hypot(fb.x - start["x"], fb.y - start["y"])
    real_travel = args.travel_phones * PHONE_M
    real_gap_end = args.gap_phones * PHONE_M
    real_gap_start = real_gap_end + real_travel
    res = {
        "robot": args.robot,
        "real_travel_m": round(real_travel, 4),
        "odom_travel_m": round(odom_travel, 4),
        "yaw_drift_deg": round(math.degrees(wrap(fb.yaw - start["yaw"])), 2),
        "odom_scale (실측/odom)": round(real_travel / odom_travel, 4) if odom_travel > 0.01 else None,
        "lidar_front_start_m": round(start["front"], 4),
        "lidar_front_end_m": round(fb.front_min, 4),
        "real_gap_start_m (범퍼 간)": round(real_gap_start, 4),
        "real_gap_end_m (범퍼 간)": round(real_gap_end, 4),
        "lidar_offset_start_m (LiDAR - 실측 간격)": round(start["front"] - real_gap_start, 4) if start["front"] > 0 else None,
        "lidar_offset_end_m": round(fb.front_min - real_gap_end, 4) if fb.front_min > 0 else None,
        "lidar_travel_m (전방 거리 감소량)": round(start["front"] - fb.front_min, 4) if start["front"] > 0 and fb.front_min > 0 else None,
        "center_spacing_start_m (Unity 스폰 간격 후보)": round(real_gap_start + BURGER_LENGTH_M, 4),
        "csv": csv_path,
    }
    print(json.dumps(res, ensure_ascii=False, indent=2))
    with open(csv_path.replace(".csv", "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="TurtleBot3 odom·LiDAR 실측 보정")
    p.add_argument("--robot", default="tb1")
    p.add_argument("--url", default="ws://172.30.1.58:9090")
    p.add_argument("--ros", type=int, choices=(1, 2), default=1)
    p.add_argument("--travel-phones", type=float, default=5.0, help="실측 주행 거리 (S20 FE 세로 개수)")
    p.add_argument("--gap-phones", type=float, default=1.0, help="정지 후 앞 로봇까지 실측 간격 (S20 FE 세로 개수)")
    p.add_argument("--stop-front-m", type=float, default=0.15, help="전방 LiDAR 이 값 이하면 전진 자동 차단 (m)")
    p.add_argument("--log-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_relay_server", "logs"))
    sys.exit(asyncio.run(main(p.parse_args())))
