@echo off
chcp 65001 > nul
title [TB1 SYSTEM LAUNCHER - ROS 1 Noetic]
echo ========================================================
echo  TB1 서비스 일괄 기동 (roscore + rosbridge + 브링업)
echo  TB1 172.30.1.58  계정 ubuntu (비밀번호: 팀 보관 자료)
echo  - 마스터를 TB1 자신으로 고정 (PC에 ROS 설치 불필요, rosbridge로 연결)
echo  - LiDAR 모델이 다르면 아래 TB1_LDS 값을 바꿀 것 (LDS-01 / LDS-02)
echo  - 다시 실행해도 됨: 시작 전에 TB1에 떠 있는 ROS를 먼저 정리함
echo ========================================================
set TB1_HOST=172.30.1.58
set TB1_USER=ubuntu
set TB1_LDS=LDS-02

ssh -tt -o StrictHostKeyChecking=no %TB1_USER%@%TB1_HOST% "bash -c 'source /opt/ros/noetic/setup.bash; [ -f ~/catkin_ws/devel/setup.bash ] && source ~/catkin_ws/devel/setup.bash; export ROS_MASTER_URI=http://%TB1_HOST%:11311; export ROS_HOSTNAME=%TB1_HOST%; export TURTLEBOT3_MODEL=burger; export LDS_MODEL=%TB1_LDS%; echo \"[0/3] 기존 ROS 정리 (중복 실행 방지)...\"; pkill -INT -x roslaunch; sleep 2; pkill -x rosbridge_webso; pkill -x rosmaster; sleep 1; echo \"[1/3] roscore...\"; roscore & sleep 5; echo \"[2/3] rosbridge...\"; roslaunch rosbridge_server rosbridge_websocket.launch & sleep 3; echo \"[3/3] Bringup...\"; roslaunch turtlebot3_bringup turtlebot3_robot.launch'"

pause
