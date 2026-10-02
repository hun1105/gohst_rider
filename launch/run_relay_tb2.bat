@echo off
chcp 65001 > nul
title [PHYSICAL AI RELAY - TB2 only]
echo ========================================================
echo  (1대 시험용) 실물 TB2만 tb2로 연결, tb1은 가상
echo  Target: TB2 (172.30.1.28:9090) + uStreamer (172.30.1.28:8080)
echo ========================================================
cd /d "%~dp0.."
python ai_relay_server/ros2_multi_turtlebot_relay.py --no-ai --tb2-url ws://172.30.1.28:9090 --camera-url http://172.30.1.28:8080/stream --camera-robot tb2
pause
