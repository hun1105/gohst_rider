#!/usr/bin/env python3
"""Adapt the dynamic-filtered SLAM map for Frontier exploration.

/map_static is generated after confirmed moving clusters are masked from the
Cartographer map.  Explore Lite requires a strict trinary OccupancyGrid, so
this node converts it to -1 (unknown), 0 (free), and 100 (occupied).
"""

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class DynamicFrontierAdapter(Node):
    def __init__(self):
        super().__init__('dynamic_frontier_adapter')
        self.declare_parameter('input_topic', '/map_static')
        self.declare_parameter('output_topic', '/explore_costmap')
        self.declare_parameter('occupied_threshold', 55)
        self.declare_parameter('publish_period', 1.0)

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.occupied_threshold = int(
            self.get_parameter('occupied_threshold').value
        )
        self.latest_map = None

        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            OccupancyGrid, self.input_topic, self._map_callback, map_qos
        )
        self.publisher = self.create_publisher(
            OccupancyGrid, self.output_topic, 1
        )
        self.create_timer(
            float(self.get_parameter('publish_period').value), self._publish
        )
        self.get_logger().info(
            f'Integrated adapter: {self.input_topic} -> {self.output_topic}'
        )

    def _map_callback(self, msg: OccupancyGrid):
        converted = OccupancyGrid()
        converted.header = msg.header
        converted.info = msg.info
        converted.data = [
            -1 if cell < 0 else 0 if cell < self.occupied_threshold else 100
            for cell in msg.data
        ]
        self.latest_map = converted

    def _publish(self):
        if self.latest_map is None:
            return
        self.latest_map.header.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(self.latest_map)


def main(args=None):
    rclpy.init(args=args)
    node = DynamicFrontierAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
