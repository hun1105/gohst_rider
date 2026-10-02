"""Standalone cmd_vel value reader (bypasses ros2 topic echo)."""

import time

import rclpy
from rclpy.node import Node


def main() -> None:
    from geometry_msgs.msg import Twist

    rclpy.init()
    node = Node('cmdvel_reader')
    count = [0]

    def callback(msg: Twist) -> None:
        count[0] += 1
        print(
            f'#{count[0]:04d}  linear.x={msg.linear.x:+.4f}  '
            f'angular.z={msg.angular.z:+.4f}',
            flush=True,
        )

    node.create_subscription(Twist, '/cmd_vel', callback, 10)

    print('Listening on /cmd_vel for 15 seconds...', flush=True)
    start = time.time()
    while time.time() - start < 15.0:
        rclpy.spin_once(node, timeout_sec=0.2)

    print(f'Done. Total messages received: {count[0]}', flush=True)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
