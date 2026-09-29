#!/usr/bin/env python3
"""
TurtleBot3 Burger On-Robot ROS 2 Humble Node
============================================
실물 TurtleBot3 라즈베리파이(Ubuntu 22.04 LTS + ROS 2 Humble)에서 실행하는 로봇 전용 노드.
- 네임스페이스 매핑: /tb1 또는 /tb2
- 토픽:
  - 수신: /{robot_name}/cmd_vel -> 모터 구동 OpenCR 전달
  - 송신: /{robot_name}/odom -> 오도메트리 브리지 중계
  - 송신: /{robot_name}/camera/image_raw -> 파이캠 영상 송출
"""

import sys
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import websockets
import asyncio
import json

class TurtleBotHumbleBridge(Node):
    def __init__(self, robot_name="tb1", relay_ip="192.168.0.50", relay_port=9090):
        super().__init__(f"{robot_name}_humble_bridge")
        self.robot_name = robot_name
        self.relay_uri = f"ws://{relay_ip}:{relay_port}"

        # ROS 2 퍼블리셔 & 서브스크라이버
        self.cmd_sub = self.create_subscription(
            Twist,
            f"/{self.robot_name}/cmd_vel",
            self.cmd_vel_callback,
            10
        )
        self.odom_sub = self.create_subscription(
            Odometry,
            f"/{self.robot_name}/odom",
            self.odom_callback,
            10
        )

        self.latest_odom = None
        self.get_logger().info(f"TurtleBot3 Humble Node initialized for [{self.robot_name}]")

    def cmd_vel_callback(self, msg: Twist):
        # 로봇 하드웨어 OpenCR로 명령 전달
        pass

    def odom_callback(self, msg: Odometry):
        # 오도메트리 수신 및 저장
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        self.latest_odom = {
            "x": pos.x,
            "y": pos.y,
            "z": pos.z,
            "qx": ori.x,
            "qy": ori.y,
            "qz": ori.z,
            "qw": ori.w
        }

def main(args=None):
    rclpy.init(args=args)
    robot_name = sys.argv[1] if len(sys.argv) > 1 else "tb1"
    node = TurtleBotHumbleBridge(robot_name=robot_name)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
