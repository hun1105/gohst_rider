#!/bin/bash
sudo modprobe bcm2835-v4l2 2>/dev/null
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-02
echo '[1/3] Starting rosbridge...'
ros2 launch rosbridge_server rosbridge_websocket_launch.xml &
PID1=$!
echo '[2/3] Starting ustreamer camera...'
ustreamer -d /dev/video0 -s 0.0.0.0 -p 8080 -r 640x480 -m YUYV -f 15 -q 70 --persistent &
PID2=$!
echo '[3/3] Starting robot bringup...'
trap 'kill $PID1 $PID2 2>/dev/null; exit' SIGINT SIGTERM
ros2 launch turtlebot3_bringup robot.launch.py
