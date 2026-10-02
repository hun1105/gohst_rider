"""ROS 2 node for LiDAR-only dynamic cluster boxes."""

import copy
import math
from typing import List, Tuple

from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
import rclpy
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan, PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header, Int32
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

from .core import (
    ClusterTracker,
    ScanPoint,
    TemporalHistory,
    TemporalOccupancyGrid,
    cluster_scan_points,
)


class DynamicDetector(Node):
    """Track LiDAR clusters and publish RViz bounding boxes."""

    def __init__(self) -> None:
        super().__init__('tb3_dynamic_detector')

        self._declare_parameters()
        self.fixed_frame = str(self.get_parameter('fixed_frame').value)
        self.minimum_range = float(self.get_parameter('minimum_range').value)
        self.maximum_range = float(self.get_parameter('maximum_range').value)
        self.cluster_base = float(self.get_parameter('cluster_base_distance').value)
        self.cluster_scale = float(self.get_parameter('cluster_range_scale').value)
        self.maximum_gap = float(self.get_parameter('maximum_cluster_gap').value)
        self.minimum_points = int(self.get_parameter('minimum_cluster_points').value)
        self.match_base = float(self.get_parameter('history_match_base').value)
        self.match_scale = float(self.get_parameter('history_match_range_scale').value)
        self.static_support_threshold = float(
            self.get_parameter('static_support_threshold').value
        )
        self.minimum_history = int(self.get_parameter('minimum_history_frames').value)
        self.box_padding = float(self.get_parameter('box_padding').value)
        self.show_all_clusters = bool(self.get_parameter('show_all_clusters').value)
        self.latest_tf_fallback = bool(
            self.get_parameter('latest_tf_fallback').value
        )
        self.tf_lookup_timeout = float(
            self.get_parameter('tf_lookup_timeout').value
        )
        self.foreground_only_detection = bool(
            self.get_parameter('foreground_only_detection').value
        )
        self.temporal_grid_enabled = bool(
            self.get_parameter('temporal_grid_enabled').value
        )
        self.grid_free_confirmations = int(
            self.get_parameter('grid_free_confirmations').value
        )
        self.grid_candidate_hold_seconds = float(
            self.get_parameter('grid_candidate_hold_seconds').value
        )
        self.static_scan_enabled = bool(
            self.get_parameter('static_scan_enabled').value
        )
        self.rotation_gate_enabled = bool(
            self.get_parameter('rotation_gate_enabled').value
        )
        self.rotation_gate_threshold = float(
            self.get_parameter('rotation_gate_threshold').value
        )
        self.rotation_gate_resume_delay = float(
            self.get_parameter('rotation_gate_resume_delay').value
        )
        self.rotation_gate_odom_timeout = float(
            self.get_parameter('rotation_gate_odom_timeout').value
        )

        history_frames = int(self.get_parameter('history_frames').value)
        voxel_size = float(self.get_parameter('history_voxel_size').value)
        self.history = TemporalHistory(history_frames, voxel_size)
        self.temporal_grid = TemporalOccupancyGrid(
            resolution=float(self.get_parameter('grid_resolution').value),
            max_cell_age=float(self.get_parameter('grid_max_cell_age').value),
        )
        self.tracker = ClusterTracker(
            association_distance=float(
                self.get_parameter('association_distance').value
            ),
            velocity_alpha=float(self.get_parameter('velocity_filter_alpha').value),
            velocity_threshold=float(
                self.get_parameter('dynamic_velocity_threshold').value
            ),
            support_threshold=self.static_support_threshold,
            confirmation_window=int(
                self.get_parameter('confirmation_window').value
            ),
            confirmations_required=int(
                self.get_parameter('dynamic_confirmations').value
            ),
            dynamic_hold_seconds=float(
                self.get_parameter('dynamic_hold_seconds').value
            ),
            track_timeout=float(self.get_parameter('track_timeout').value),
            require_low_static_support=bool(
                self.get_parameter('require_low_static_support').value
            ),
            enable_displacement_detection=bool(
                self.get_parameter('enable_displacement_detection').value
            ),
            displacement_window_seconds=float(
                self.get_parameter('displacement_window_seconds').value
            ),
            displacement_threshold=float(
                self.get_parameter('displacement_threshold').value
            ),
            foreground_only_detection=self.foreground_only_detection,
            use_kalman_filter=bool(
                self.get_parameter('use_kalman_filter').value
            ),
            mahalanobis_gate=float(
                self.get_parameter('mahalanobis_gate').value
            ),
            kalman_position_std=float(
                self.get_parameter('kalman_position_std').value
            ),
            kalman_velocity_std=float(
                self.get_parameter('kalman_velocity_std').value
            ),
            kalman_measurement_std=float(
                self.get_parameter('kalman_measurement_std').value
            ),
            kalman_acceleration_std=float(
                self.get_parameter('kalman_acceleration_std').value
            ),
            require_grid_candidate_for_dynamic=bool(
                self.get_parameter(
                    'require_grid_candidate_for_dynamic'
                ).value
            ),
        )

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.marker_publisher = self.create_publisher(
            MarkerArray, '/dynamic_boxes', 10
        )
        self.cloud_publisher = self.create_publisher(
            PointCloud2, '/dynamic_clusters', 10
        )
        self.count_publisher = self.create_publisher(
            Int32, '/dynamic_object_count', 10
        )
        self.static_scan_publisher = self.create_publisher(
            LaserScan, '/scan_static', qos_profile_sensor_data
        )
        self.grid_candidate_publisher = self.create_publisher(
            MarkerArray, '/dynamic_grid_candidates', 10
        )
        input_topic = str(self.get_parameter('input_topic').value)
        self.scan_subscription = self.create_subscription(
            LaserScan,
            input_topic,
            self._scan_callback,
            qos_profile_sensor_data,
        )
        self.odom_subscription = self.create_subscription(
            Odometry,
            '/odom',
            self._odom_callback,
            qos_profile_sensor_data,
        )
        self.latest_angular_z = 0.0
        self.last_odom_receive_time = float('-inf')
        self.rotation_gate_until = float('-inf')
        self.rotation_gate_active = False
        self.tf_failures = 0
        self.get_logger().info(
            f'Dynamic detector ready: {input_topic} -> /dynamic_boxes '
            f'(fixed_frame={self.fixed_frame})'
        )

    def _declare_parameters(self) -> None:
        defaults = {
            'input_topic': '/scan',
            'fixed_frame': 'odom',
            'minimum_range': 0.20,
            'maximum_range': 3.50,
            'cluster_base_distance': 0.08,
            'cluster_range_scale': 0.02,
            'maximum_cluster_gap': 0.18,
            'minimum_cluster_points': 3,
            'history_frames': 6,
            'minimum_history_frames': 4,
            'history_voxel_size': 0.05,
            'history_match_base': 0.05,
            'history_match_range_scale': 0.02,
            'static_support_threshold': 0.50,
            'foreground_only_detection': False,
            # Temporal occupancy-grid candidate visualization.  This is kept
            # separate from the red dynamic decision until its RViz behavior
            # is validated with TB1.
            'temporal_grid_enabled': True,
            'grid_resolution': 0.05,
            'grid_free_confirmations': 8,
            'grid_candidate_hold_seconds': 0.8,
            # Confirmed red clusters are masked only in /scan_static.
            # Raw /scan remains untouched for diagnostics.
            'static_scan_enabled': True,
            # Suppress dynamic decisions while the robot rotates quickly.
            # LDS-02 needs about 0.1 s for one scan, so rotation otherwise
            # bends static walls and creates false motion.
            'rotation_gate_enabled': True,
            'rotation_gate_threshold': 0.25,
            'rotation_gate_resume_delay': 0.35,
            'rotation_gate_odom_timeout': 1.0,
            # Constant-velocity Kalman Filter and 2-D Mahalanobis gate.
            'use_kalman_filter': True,
            'mahalanobis_gate': 5.99,
            'kalman_position_std': 0.08,
            'kalman_velocity_std': 0.50,
            'kalman_measurement_std': 0.04,
            'kalman_acceleration_std': 0.80,
            # Prevent a wall reappearing after occlusion from becoming red.
            'require_grid_candidate_for_dynamic': True,
            'grid_max_cell_age': 8.0,
            'require_low_static_support': True,
            'enable_displacement_detection': False,
            'displacement_window_seconds': 0.60,
            'displacement_threshold': 0.04,
            'association_distance': 0.35,
            'velocity_filter_alpha': 0.60,
            'dynamic_velocity_threshold': 0.15,
            'confirmation_window': 4,
            'dynamic_confirmations': 3,
            'dynamic_hold_seconds': 0.80,
            'track_timeout': 0.50,
            'box_padding': 0.08,
            'show_all_clusters': False,
            # Use only when a scan timestamp is ahead of received /tf.
            # Timestamped TF remains more accurate while the robot moves.
            'latest_tf_fallback': False,
            # Wait for delayed remote TF while preserving the exact scan time.
            'tf_lookup_timeout': 0.30,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)

    def _now_seconds(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _odom_callback(self, message: Odometry) -> None:
        """Track angular speed using local receive time for robust gating."""
        now = self._now_seconds()
        self.latest_angular_z = abs(float(message.twist.twist.angular.z))
        self.last_odom_receive_time = now
        if self.latest_angular_z >= self.rotation_gate_threshold:
            self.rotation_gate_until = max(
                self.rotation_gate_until,
                now + self.rotation_gate_resume_delay,
            )

    def _rotation_is_gated(self) -> bool:
        if not self.rotation_gate_enabled:
            return False
        now = self._now_seconds()
        odom_is_fresh = (
            now - self.last_odom_receive_time
            <= self.rotation_gate_odom_timeout
        )
        if not odom_is_fresh:
            return False
        return (
            self.latest_angular_z >= self.rotation_gate_threshold
            or now <= self.rotation_gate_until
        )

    def _set_rotation_gate(self, active: bool) -> None:
        if active == self.rotation_gate_active:
            return
        self.rotation_gate_active = active
        if active:
            # Do not carry apparent wall velocity across a robot rotation.
            self.tracker.reset()
            self.get_logger().info(
                'Rotation gate ON: dynamic decisions paused '
                f'(|wz|={self.latest_angular_z:.3f} rad/s)'
            )
        else:
            self.get_logger().info(
                'Rotation gate OFF: dynamic decisions resumed'
            )

    def _publish_gated_outputs(self, scan: LaserScan) -> None:
        """Keep SLAM input alive while publishing no dynamic detections."""
        delete_markers = MarkerArray()
        delete = Marker()
        delete.action = Marker.DELETEALL
        delete_markers.markers.append(delete)
        self.marker_publisher.publish(delete_markers)
        self.grid_candidate_publisher.publish(delete_markers)
        self.static_scan_publisher.publish(scan)
        header = Header()
        header.frame_id = self.fixed_frame
        header.stamp = scan.header.stamp
        self.cloud_publisher.publish(
            point_cloud2.create_cloud_xyz32(header, [])
        )
        self.count_publisher.publish(Int32(data=0))

    @staticmethod
    def _yaw_from_quaternion(rotation) -> float:
        sin_yaw = 2.0 * (
            rotation.w * rotation.z + rotation.x * rotation.y
        )
        cos_yaw = 1.0 - 2.0 * (
            rotation.y * rotation.y + rotation.z * rotation.z
        )
        return math.atan2(sin_yaw, cos_yaw)

    def _transform_points(
        self, scan: LaserScan
    ) -> Tuple[List[ScanPoint], float, Tuple[float, float]]:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.fixed_frame,
                scan.header.frame_id,
                scan.header.stamp,
                timeout=Duration(seconds=self.tf_lookup_timeout),
            )
        except TransformException:
            if not self.latest_tf_fallback:
                raise
            # For a stationary robot this prevents remote DDS timing jitter
            # from discarding a scan whose exact TF has not arrived yet.
            transform = self.tf_buffer.lookup_transform(
                self.fixed_frame,
                scan.header.frame_id,
                Time(),
                timeout=Duration(seconds=0.05),
            )
        translation = transform.transform.translation
        yaw = self._yaw_from_quaternion(transform.transform.rotation)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        points: List[ScanPoint] = []

        for index, range_m in enumerate(scan.ranges):
            if not math.isfinite(range_m):
                continue
            lower = max(self.minimum_range, float(scan.range_min))
            upper = min(self.maximum_range, float(scan.range_max))
            if not lower <= range_m <= upper:
                continue

            angle = scan.angle_min + index * scan.angle_increment
            local_x = range_m * math.cos(angle)
            local_y = range_m * math.sin(angle)
            fixed_x = cos_yaw * local_x - sin_yaw * local_y + translation.x
            fixed_y = sin_yaw * local_x + cos_yaw * local_y + translation.y
            points.append(
                ScanPoint(
                    index=index,
                    range_m=float(range_m),
                    x=fixed_x,
                    y=fixed_y,
                )
            )

        stamp = scan.header.stamp.sec + scan.header.stamp.nanosec * 1e-9
        return points, stamp, (translation.x, translation.y)

    def _scan_callback(self, scan: LaserScan) -> None:
        rotation_gated = self._rotation_is_gated()
        self._set_rotation_gate(rotation_gated)
        if rotation_gated:
            self._publish_gated_outputs(scan)
            return

        try:
            points, stamp, sensor_origin = self._transform_points(scan)
        except TransformException as error:
            self.tf_failures += 1
            if self.tf_failures == 1 or self.tf_failures % 20 == 0:
                self.get_logger().warning(
                    f'TF {self.fixed_frame} <- {scan.header.frame_id} unavailable: '
                    f'{error}'
                )
            return

        grid_clusters = []
        grid_candidate_indices = set()
        if self.temporal_grid_enabled:
            grid_points = self.temporal_grid.candidate_points(
                points,
                self.grid_free_confirmations,
                stamp,
                self.grid_candidate_hold_seconds,
            )
            grid_clusters = cluster_scan_points(
                points=grid_points,
                beam_count=len(scan.ranges),
                base_distance=self.cluster_base,
                range_scale=self.cluster_scale,
                maximum_gap=self.maximum_gap,
                minimum_points=self.minimum_points,
            )
            grid_candidate_indices = {point.index for point in grid_points}
            self.temporal_grid.update(sensor_origin, points, stamp)

        if self.foreground_only_detection and len(self.history) >= self.minimum_history:
            # Cluster only scan points that differ from the learned static
            # background. This prevents long wall segments from becoming
            # moving clusters when their visible endpoint changes.
            foreground_points = [
                point for point in points
                if self.history.point_support(
                    point, self.match_base, self.match_scale
                ) < self.static_support_threshold
            ]
            clusters = cluster_scan_points(
                points=foreground_points,
                beam_count=len(scan.ranges),
                base_distance=self.cluster_base,
                range_scale=self.cluster_scale,
                maximum_gap=self.maximum_gap,
                minimum_points=self.minimum_points,
            )
        elif self.foreground_only_detection:
            # Build background before publishing any dynamic candidate.
            clusters = []
        else:
            clusters = cluster_scan_points(
                points=points,
                beam_count=len(scan.ranges),
                base_distance=self.cluster_base,
                range_scale=self.cluster_scale,
                maximum_gap=self.maximum_gap,
                minimum_points=self.minimum_points,
            )

        if len(self.history) >= self.minimum_history:
            for cluster in clusters:
                cluster.support = self.history.cluster_support(
                    cluster, self.match_base, self.match_scale
                )
        else:
            for cluster in clusters:
                cluster.support = 1.0
        for cluster in clusters:
            cluster.grid_candidate = any(
                point.index in grid_candidate_indices
                for point in cluster.points
            )

        visible_tracks = self.tracker.update(clusters, stamp)
        self.history.append(points)
        self._publish_outputs(scan, visible_tracks, grid_clusters)

    def _publish_outputs(self, scan: LaserScan, tracks, grid_clusters) -> None:
        markers = MarkerArray()
        delete = Marker()
        delete.action = Marker.DELETEALL
        markers.markers.append(delete)
        dynamic_points = []
        dynamic_count = 0

        for track in tracks:
            if track.cluster is None:
                continue
            if track.is_dynamic:
                dynamic_count += 1
                dynamic_points.extend(
                    (point.x, point.y, 0.10) for point in track.cluster.points
                )
            if self.show_all_clusters or track.is_dynamic:
                markers.markers.extend(self._track_markers(scan, track))

        self.marker_publisher.publish(markers)
        if self.static_scan_enabled:
            self.static_scan_publisher.publish(self._static_scan(scan, tracks))
        else:
            self.static_scan_publisher.publish(scan)
        header = Header()
        header.frame_id = self.fixed_frame
        header.stamp = scan.header.stamp
        cloud = point_cloud2.create_cloud_xyz32(header, dynamic_points)
        self.cloud_publisher.publish(cloud)
        self.count_publisher.publish(Int32(data=dynamic_count))
        self.grid_candidate_publisher.publish(
            self._grid_candidate_markers(scan, grid_clusters)
        )

    @staticmethod
    def _static_scan(scan: LaserScan, tracks) -> LaserScan:
        """Mask confirmed dynamic returns for Cartographer only."""
        static_scan = copy.deepcopy(scan)
        ranges = list(static_scan.ranges)
        for track in tracks:
            if not track.is_dynamic or track.cluster is None:
                continue
            for index in track.cluster.scan_indices:
                if 0 <= index < len(ranges):
                    # NaN makes Cartographer ignore this ray entirely.
                    ranges[index] = float('nan')
        static_scan.ranges = ranges
        return static_scan

    def _grid_candidate_markers(self, scan: LaserScan, clusters) -> MarkerArray:
        """Publish green boxes for occupancy-grid candidates only."""
        markers = MarkerArray()
        delete = Marker()
        delete.action = Marker.DELETEALL
        markers.markers.append(delete)
        for index, cluster in enumerate(clusters):
            min_x, max_x, min_y, max_y = cluster.bounds
            box = Marker()
            box.header.frame_id = self.fixed_frame
            box.header.stamp = scan.header.stamp
            box.ns = 'temporal_grid_candidates'
            box.id = index
            box.type = Marker.LINE_STRIP
            box.action = Marker.ADD
            box.scale.x = 0.025
            box.color.r = 0.15
            box.color.g = 1.0
            box.color.b = 0.10
            box.color.a = 0.95
            box.pose.orientation.w = 1.0
            box.points = [
                self._point(min_x - self.box_padding, min_y - self.box_padding, 0.12),
                self._point(max_x + self.box_padding, min_y - self.box_padding, 0.12),
                self._point(max_x + self.box_padding, max_y + self.box_padding, 0.12),
                self._point(min_x - self.box_padding, max_y + self.box_padding, 0.12),
                self._point(min_x - self.box_padding, min_y - self.box_padding, 0.12),
            ]
            markers.markers.append(box)
        return markers

    def _track_markers(self, scan: LaserScan, track) -> List[Marker]:
        cluster = track.cluster
        min_x, max_x, min_y, max_y = cluster.bounds
        min_x -= self.box_padding
        max_x += self.box_padding
        min_y -= self.box_padding
        max_y += self.box_padding
        red, green, blue = (
            (1.0, 0.10, 0.05) if track.is_dynamic else (0.05, 0.75, 1.0)
        )

        box = Marker()
        box.header.frame_id = self.fixed_frame
        box.header.stamp = scan.header.stamp
        box.ns = 'dynamic_boxes'
        box.id = track.track_id * 10
        box.type = Marker.LINE_STRIP
        box.action = Marker.ADD
        box.scale.x = 0.035
        box.color.r = red
        box.color.g = green
        box.color.b = blue
        box.color.a = 0.95
        box.pose.orientation.w = 1.0
        box.points = [
            self._point(min_x, min_y, 0.10),
            self._point(max_x, min_y, 0.10),
            self._point(max_x, max_y, 0.10),
            self._point(min_x, max_y, 0.10),
            self._point(min_x, min_y, 0.10),
        ]

        arrow = Marker()
        arrow.header = copy.deepcopy(box.header)
        arrow.ns = 'dynamic_velocity'
        arrow.id = track.track_id * 10 + 1
        arrow.type = Marker.ARROW
        arrow.action = Marker.ADD
        arrow.scale.x = 0.035
        arrow.scale.y = 0.075
        arrow.scale.z = 0.10
        arrow.color.r = red
        arrow.color.g = green
        arrow.color.b = blue
        arrow.color.a = 0.95
        arrow.pose.orientation.w = 1.0
        center_x, center_y = track.centroid
        arrow.points = [
            self._point(center_x, center_y, 0.14),
            self._point(
                center_x + track.velocity[0],
                center_y + track.velocity[1],
                0.14,
            ),
        ]

        speed = math.hypot(track.velocity[0], track.velocity[1])
        text = Marker()
        text.header = copy.deepcopy(box.header)
        text.ns = 'dynamic_labels'
        text.id = track.track_id * 10 + 2
        text.type = Marker.TEXT_VIEW_FACING
        text.action = Marker.ADD
        text.pose.position.x = center_x
        text.pose.position.y = center_y
        text.pose.position.z = 0.35
        text.pose.orientation.w = 1.0
        text.scale.z = 0.14
        text.color.r = red
        text.color.g = green
        text.color.b = blue
        text.color.a = 1.0
        state = 'DYN' if track.is_dynamic else 'OBS'
        text.text = (
            f'{state} #{track.track_id}  {speed:.2f} m/s  '
            f'H={cluster.support:.2f}  D={track.motion_displacement:.2f} m'
        )
        return [box, arrow, text]

    @staticmethod
    def _point(x: float, y: float, z: float) -> Point:
        point = Point()
        point.x = float(x)
        point.y = float(y)
        point.z = float(z)
        return point


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DynamicDetector()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
