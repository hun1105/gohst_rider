@echo off
chcp 65001 > nul
title [PHYSICAL AI RELAY - TB1 + TB2 real]
echo ========================================================
echo  실물 2대 동시 연결 (T-025)
echo  - tb1 = 실물 TB1 (172.30.1.58, ROS 1 Noetic)
echo  - tb2 = 실물 TB2 (172.30.1.28, ROS 2 Humble, 카메라)
echo  - 두 대 각각 AUTO (Unity 관제 맵에서 로봇 클릭 → Y / R)
echo  - 1인칭(콕핏) 진입한 로봇만 MANUAL, 1.0m 만나면 둘 다 정지
echo ========================================================
cd /d "%~dp0.."

rem ---- 카메라 장착값 (영상 위 경로 투영) ----
rem CAM_HEIGHT : 렌즈 바닥 높이 m (Galaxy S20 FE 높이 실측 0.16)
rem CAM_PITCH  : 아래로 숙인 각 deg (현재 수평 장착 0)
rem CAM_FWD    : 로봇 중심 → 렌즈 앞쪽 거리 m
rem CAM_GRID   : 보정할 때만 --camera-grid (바닥 0.5/1.0/1.5/2.0m 선 표시)
set CAM_HEIGHT=0.16
set CAM_PITCH=0
set CAM_FWD=0.06
set CAM_GRID=

python ai_relay_server/ros2_multi_turtlebot_relay.py --no-ai --tb1-url ws://172.30.1.58:9090 --tb1-ros 1 --tb2-url ws://172.30.1.28:9090 --tb2-ros 2 --camera-url http://172.30.1.28:8080/stream --camera-robot tb2 --camera-height-m %CAM_HEIGHT% --camera-pitch-deg %CAM_PITCH% --camera-forward-m %CAM_FWD% %CAM_GRID%
pause
