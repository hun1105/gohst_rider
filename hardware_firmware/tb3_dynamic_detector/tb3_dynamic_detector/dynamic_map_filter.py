"""Publish /map_static without blocking the LiDAR detector process."""

import copy
import math
import time
from typing import Dict, Iterable, List, Tuple

from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from tf2_ros import Buffer, TransformException, TransformListener


HistoryValue = Tuple[float, float, float]


def yaw_from_quaternion(rotation) -> float:
    sin_yaw = 2.0 * (
        rotation.w * rotation.z + rotation.x * rotation.y
    )
    cos_yaw = 1.0 - 2.0 * (
        rotation.y * rotation.y + rotation.z * rotation.z
    )
    return math.atan2(sin_yaw, cos_yaw)


def mask_occupied_cells(
    data: Iterable[int],
    width: int,
    height: int,
    resolution: float,
    origin_x: float,
    origin_y: float,
    origin_yaw: float,
    points: Iterable[Tuple[float, float]],
    clear_radius: float,
    occupied_threshold: int,
) -> List[int]:
    """Clear occupied map cells around map-frame dynamic points."""
    output = list(data)
    if width <= 0 or height <= 0 or resolution <= 0.0:
        return output

    cos_origin = math.cos(origin_yaw)
    sin_origin = math.sin(origin_yaw)
    radius_cells = max(1, math.ceil(clear_radius / resolution))

    for world_x, world_y in points:
        dx = world_x - origin_x
        dy = world_y - origin_y
        local_x = cos_origin * dx + sin_origin * dy
        local_y = -sin_origin * dx + cos_origin * dy
        center_x = math.floor(local_x / resolution)
        center_y = math.floor(local_y / resolution)

        for cell_y in range(center_y - radius_cells, center_y + radius_cells + 1):
            for cell_x in range(center_x - radius_cells, center_x + radius_cells + 1):
                if not (0 <= cell_x < width and 0 <= cell_y < height):
                    continue
                if math.hypot(cell_x - center_x, cell_y - center_y) > radius_cells:
                    continue
                index = cell_y * width + cell_x
                if output[index] >= occupied_threshold:
                    output[index] = -1
    return output


class DynamicMapFilter(Node):
    """Mask confirmed dynamic points in a process separate from scan tracking."""

    def __init__(self) -> None:
        super().__init__('dynamic_map_filter')

        self.declare_parameter('input_map_topic', '/map')
        self.declare_parameter('output_map_topic', '/map_static')
        self.declare_parameter('dynamic_cloud_topic', '/dynamic_clusters')
        self.declare_parameter('map_static_enabled', True)
        self.declare_parameter('map_dynamic_clear_radius', 0.18)
        self.declare_parameter('map_dynamic_mask_hold_seconds', 5.0)
        self.declare_parameter('map_occupied_threshold', 65)
        self.declare_parameter('history_resolution', 0.05)
        self.declare_parameter('tf_lookup_timeout', 0.05)
        self.declare_parameter('slow_callback_warning_sec', 0.25)
        self.declare_parameter('status_period_sec', 10.0)

        self.enabled = bool(self.get_parameter('map_static_enabled').value)
        self.clear_radius = float(
            self.get_parameter('map_dynamic_clear_radius').value
        )
        self.hold_seconds = float(
            self.get_parameter('map_dynamic_mask_hold_seconds').value
        )
        self.occupied_threshold = int(
            self.get_parameter('map_occupied_threshold').value
        )
        self.history_resolution = max(
            0.01, float(self.get_parameter('history_resolution').value)
        )
        self.tf_timeout = float(self.get_parameter('tf_lookup_timeout').value)
        self.slow_warning = float(
            self.get_parameter('slow_callback_warning_sec').value
        )

        self.map_frame = 'map'
        self.history: Dict[Tuple[int, int], HistoryValue] = {}
        self.maps_received = 0
        self.maps_published = 0
        self.clouds_received = 0
        self.tf_failures = 0
        self.last_callback_sec = 0.0
        self.max_callback_sec = 0.0

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        cloud_qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        input_map_topic = str(self.get_parameter('input_map_topic').value)
        output_map_topic = str(self.get_parameter('output_map_topic').value)
        dynamic_cloud_topic = str(
            self.get_parameter('dynamic_cloud_topic').value
        )

        self.map_publisher = self.create_publisher(
            OccupancyGrid, output_map_topic, map_qos
        )
        self.map_subscription = self.create_subscription(
            OccupancyGrid, input_map_topic, self._map_callback, map_qos
        )
        self.cloud_subscription = self.create_subscription(
            PointCloud2, dynamic_cloud_topic, self._cloud_callback, cloud_qos
        )
        self.status_timer = self.create_timer(
            float(self.get_parameter('status_period_sec').value),
            self._publish_status,
        )

        self.get_logger().info(
            f'Dynamic map filter ready: {input_map_topic} -> {output_map_topic}; '
            f'dynamic cloud={dynamic_cloud_topic}, hold={self.hold_seconds:.1f}s'
        )

    def _now_seconds(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _history_key(self, x: float, y: float) -> Tuple[int, int]:
        return (
            math.floor(x / self.history_resolution),
            math.floor(y / self.history_resolution),
        )

    def _prune_history(self, now: float) -> None:
        keep_after = now - self.hold_seconds
        self.history = {
            key: value
            for key, value in self.history.items()
            if value[2] >= keep_after
        }

    def _cloud_callback(self, message: PointCloud2) -> None:
        self.clouds_received += 1
        if not self.enabled or message.width * message.height == 0:
            return

        source_frame = message.header.frame_id
        if not source_frame or not self.map_frame:
            return

        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                source_frame,
                Time(),
                timeout=Duration(seconds=self.tf_timeout),
            )
        except TransformException as error:
            self.tf_failures += 1
            if self.tf_failures == 1 or self.tf_failures % 20 == 0:
                self.get_logger().warning(
                    f'TF {self.map_frame} <- {source_frame} unavailable: {error}'
                )
            return

        translation = transform.transform.translation
        yaw = yaw_from_quaternion(transform.transform.rotation)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        now = self._now_seconds()

        for point in point_cloud2.read_points(
            message,
            field_names=('x', 'y'),
            skip_nans=True,
        ):
            source_x = float(point[0])
            source_y = float(point[1])
            map_x = cos_yaw * source_x - sin_yaw * source_y + translation.x
            map_y = sin_yaw * source_x + cos_yaw * source_y + translation.y
            key = self._history_key(map_x, map_y)
            self.history[key] = (map_x, map_y, now)

        self._prune_history(now)

    def _map_callback(self, message: OccupancyGrid) -> None:
        started = time.perf_counter()
        self.maps_received += 1

        if message.header.frame_id and message.header.frame_id != self.map_frame:
            if self.map_frame != 'map':
                self.history.clear()
            self.map_frame = message.header.frame_id

        now = self._now_seconds()
        self._prune_history(now)

        if not self.enabled or not self.history:
            self.map_publisher.publish(message)
        else:
            filtered = copy.deepcopy(message)
            origin = filtered.info.origin
            filtered.data = mask_occupied_cells(
                data=filtered.data,
                width=int(filtered.info.width),
                height=int(filtered.info.height),
                resolution=float(filtered.info.resolution),
                origin_x=float(origin.position.x),
                origin_y=float(origin.position.y),
                origin_yaw=yaw_from_quaternion(origin.orientation),
                points=((value[0], value[1]) for value in self.history.values()),
                clear_radius=self.clear_radius,
                occupied_threshold=self.occupied_threshold,
            )
            self.map_publisher.publish(filtered)

        self.maps_published += 1
        elapsed = time.perf_counter() - started
        self.last_callback_sec = elapsed
        self.max_callback_sec = max(self.max_callback_sec, elapsed)
        if elapsed >= self.slow_warning:
            self.get_logger().warning(
                f'Slow map filter callback: {elapsed:.3f}s; '
                f'history_cells={len(self.history)}, '
                f'map={message.info.width}x{message.info.height}'
            )

    def _publish_status(self) -> None:
        self.get_logger().info(
            'Map filter status: '
            f'in={self.maps_received}, out={self.maps_published}, '
            f'clouds={self.clouds_received}, history_cells={len(self.history)}, '
            f'last={self.last_callback_sec:.3f}s, '
            f'max={self.max_callback_sec:.3f}s, tf_failures={self.tf_failures}'
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DynamicMapFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        # Shutdown-time races (DDS/rmw context tearing down mid-callback)
        # must not surface as a non-zero exit; the process is stopping
        # anyway once the launch system sends SIGINT to every node.
        node.get_logger().warning(f'Exiting after executor error: {error}')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
