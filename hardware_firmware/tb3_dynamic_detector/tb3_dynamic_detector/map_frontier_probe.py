#!/usr/bin/env python3
"""Print exact OccupancyGrid and frontier statistics, then exit."""

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class MapFrontierProbe(Node):
    """Count cells using the same unknown/free boundary idea as Explore Lite."""

    def __init__(self):
        super().__init__('map_frontier_probe')
        self.declare_parameter('map_topic', '/map')
        self.map_topic = self.get_parameter('map_topic').value
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(OccupancyGrid, self.map_topic, self.map_callback, qos)
        self.done = False
        self.get_logger().info(f'Waiting for one message on {self.map_topic}...')

    def map_callback(self, msg: OccupancyGrid):
        if self.done:
            return
        self.done = True

        width = msg.info.width
        height = msg.info.height
        data = msg.data
        unknown = sum(value == -1 for value in data)
        free = sum(value == 0 for value in data)
        occupied = sum(value >= 50 for value in data)
        other = len(data) - unknown - free - occupied

        # A frontier is an unknown cell directly next to a free cell.
        frontier_cells = 0
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                index = y * width + x
                if data[index] != -1:
                    continue
                if any(data[neighbor] == 0 for neighbor in (
                    index - 1, index + 1, index - width, index + width
                )):
                    frontier_cells += 1

        self.get_logger().info(
            f'topic={self.map_topic}, map={width}x{height}, unknown(-1)={unknown}, free(0)={free}, '
            f'occupied(>=50)={occupied}, other={other}, '
            f'raw_frontier_cells={frontier_cells}'
        )
        self.get_logger().info(
            'raw_frontier_cells > 0 means /map contains an explorable boundary.'
        )
        self.destroy_node()
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = MapFrontierProbe()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()
