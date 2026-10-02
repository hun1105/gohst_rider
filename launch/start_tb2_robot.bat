@echo off
chcp 65001 > nul
title [TB2 SYSTEM LAUNCHER - ROS 2 Humble]
echo ========================================================
echo  TB2 서비스 일괄 기동 (브링업 + 웹소켓 + 카메라)
echo  TB2 172.30.1.28  계정 user (비밀번호: 팀 보관 자료)
echo ========================================================

ssh -tt -o StrictHostKeyChecking=no user@172.30.1.28 "bash -c 'sudo modprobe bcm2835-v4l2 2>/dev/null; source /opt/ros/humble/setup.bash; export TURTLEBOT3_MODEL=burger; export LDS_MODEL=LDS-02; echo \"[1/3] rosbridge...\"; ros2 launch rosbridge_server rosbridge_websocket_launch.xml & echo \"[2/3] ustreamer camera...\"; ustreamer -d /dev/video0 -s 0.0.0.0 -p 8080 -r 640x480 -m YUYV -f 15 -q 70 --persistent & echo \"[3/3] Bringup...\"; ros2 launch turtlebot3_bringup robot.launch.py'"

pause
