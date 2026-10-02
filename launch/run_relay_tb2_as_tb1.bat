@echo off
chcp 65001 > nul
title [PHYSICAL AI RELAY - TB2 hardware as tb1]
echo ========================================================
echo  (1대 시험용) 실물 TB2(172.30.1.28)를 소프트웨어 tb1 역할로 연결
echo  - Unity 기본 조종 대상(tb1) = 실물 TB2 → 클릭 없이 WASD/썸스틱 주행
echo  - tb2는 가상 로봇 (왕복 순찰)
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

python ai_relay_server/ros2_multi_turtlebot_relay.py --no-ai --tb1-url ws://172.30.1.28:9090 --tb1-ros 2 --camera-url http://172.30.1.28:8080/stream --camera-height-m %CAM_HEIGHT% --camera-pitch-deg %CAM_PITCH% --camera-forward-m %CAM_FWD% %CAM_GRID%
pause
