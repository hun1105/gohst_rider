#!/usr/bin/env python3
"""Convert Cartographer probability maps into Explore Lite's trinary map."""

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class ExploreMapAdapter(Node):
    """Republish /map as -1 unknown, 0 free, 100 occupied at a fixed rate."""

    def __init__(self):
        super().__init__('explore_map_adapter')
        self.declare_parameter('input_topic', '/map')
        self.declare_parameter('output_topic', '/explore_costmap')
        self.declare_parameter('occupied_threshold', 52)
        self.declare_parameter('publish_period', 1.0)

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.occupied_threshold = int(
            self.get_parameter('occupied_threshold').value
        )
        period = float(self.get_parameter('publish_period').value)
        self.latest_map = None
        self.received_maps = 0
        self.published_maps = 0
        self._last_diagnostic_time = self.get_clock().now()

        input_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        output_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            OccupancyGrid, self.input_topic, self.map_callback, input_qos
        )
        self.publisher = self.create_publisher(
            OccupancyGrid, self.output_topic, output_qos
        )
        self.create_timer(period, self.publish_map)
        self.get_logger().info(
            f'Adapting {self.input_topic} -> {self.output_topic} '
            f'every {period:.1f}s (occupied threshold: {self.occupied_threshold}).'
        )

    def map_callback(self, msg: OccupancyGrid):
        converted = OccupancyGrid()
        converted.header = msg.header
        converted.info = msg.info
        converted.data = [
            -1 if value < 0 else 0 if value < self.occupied_threshold else 100
            for value in msg.data
        ]
        self.latest_map = converted
        self.received_maps += 1

        if self.received_maps == 1:
            unknown = sum(value < 0 for value in converted.data)
            free = sum(value == 0 for value in converted.data)
            occupied = sum(value == 100 for value in converted.data)
            self.get_logger().info(
                'Received first /map: '
                f'{msg.info.width}x{msg.info.height}, '
                f'unknown={unknown}, free={free}, occupied={occupied}'
            )

    def publish_map(self):
        if self.latest_map is not None:
            self.latest_map.header.stamp = self.get_clock().now().to_msg()
            self.publisher.publish(self.latest_map)
            self.published_maps += 1

            elapsed = (
                self.get_clock().now() - self._last_diagnostic_time
            ).nanoseconds / 1e9
            if elapsed >= 5.0:
                self.get_logger().info(
                    'Explore map adapter alive: '
                    f'received={self.received_maps}, '
                    f'published={self.published_maps}, '
                    f'topic={self.output_topic}'
                )
                self._last_diagnostic_time = self.get_clock().now()


def main(args=None):
    rclpy.init(args=args)
    node = ExploreMapAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
