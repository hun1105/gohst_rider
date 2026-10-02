"""Runtime diagnostics for rejected Frontier/Nav2 goals."""

from functools import partial
import time

from action_msgs.msg import GoalStatusArray
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry
from rcl_interfaces.msg import Log
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener


class Nav2FailureDiagnostics(Node):
    """Report actionable causes when explore_lite has a rejected goal."""

    LIFECYCLE_NODES = (
        '/planner_server',
        '/controller_server',
        '/bt_navigator',
        '/velocity_smoother',
    )

    def __init__(self):
        super().__init__('nav2_failure_diagnostics')
        self.declare_parameter('report_period_sec', 10.0)
        self.declare_parameter('stale_timeout_sec', 2.0)
        self.declare_parameter('map_timeout_sec', 8.0)

        self.last_seen = {}
        self.lifecycle_states = {name: 'SERVICE_UNAVAILABLE' for name in self.LIFECYCLE_NODES}
        self.pending_state_calls = set()
        self.last_rejection_report = 0.0

        sensor_qos = QoSProfile(depth=10)
        sensor_qos.reliability = ReliabilityPolicy.BEST_EFFORT
        map_qos = QoSProfile(depth=1)
        map_qos.reliability = ReliabilityPolicy.RELIABLE
        map_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.create_subscription(LaserScan, '/scan', partial(self._touch, 'scan'), sensor_qos)
        self.create_subscription(Odometry, '/odom', partial(self._touch, 'odom'), 10)
        self.create_subscription(OccupancyGrid, '/map_static', partial(self._touch, 'map_static'), map_qos)
        self.create_subscription(
            OccupancyGrid,
            '/global_costmap/costmap',
            partial(self._touch, 'global_costmap'),
            map_qos,
        )
        self.create_subscription(
            OccupancyGrid,
            '/local_costmap/costmap',
            partial(self._touch, 'local_costmap'),
            map_qos,
        )
        self.create_subscription(GoalStatusArray, '/navigate_to_pose/_action/status', self._status_cb, 10)
        self.create_subscription(Log, '/rosout', self._rosout_cb, 100)

        self.tf_buffer = Buffer(cache_time=Duration(seconds=15.0))
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.state_clients = {
            name: self.create_client(GetState, f'{name}/get_state')
            for name in self.LIFECYCLE_NODES
        }

        self.create_timer(1.0, self._poll_lifecycle)
        self.create_timer(float(self.get_parameter('report_period_sec').value), self._periodic_report)
        self.get_logger().info(
            'Nav2 failure diagnostics ready. Rejected goals trigger an immediate cause report.'
        )

    def _touch(self, key, _msg):
        self.last_seen[key] = time.monotonic()

    def _status_cb(self, _msg):
        self.last_seen['navigate_status'] = time.monotonic()

    def _rosout_cb(self, msg):
        text = msg.msg.lower()
        if 'goal was rejected' in text or 'goal rejected' in text:
            now = time.monotonic()
            if now - self.last_rejection_report > 1.0:
                self.last_rejection_report = now
                self.get_logger().error(
                    f'NAV2_GOAL_REJECTED detected from {msg.name}; collecting causes now.'
                )
                self._report('REJECTION')

    def _poll_lifecycle(self):
        for name, client in self.state_clients.items():
            if name in self.pending_state_calls:
                continue
            if not client.service_is_ready():
                self.lifecycle_states[name] = 'SERVICE_UNAVAILABLE'
                continue
            self.pending_state_calls.add(name)
            future = client.call_async(GetState.Request())
            future.add_done_callback(partial(self._state_done, name))

    def _state_done(self, name, future):
        self.pending_state_calls.discard(name)
        try:
            state = future.result().current_state
            self.lifecycle_states[name] = f'{state.label}[{state.id}]'
        except Exception as exc:  # ROS service failures must remain visible.
            self.lifecycle_states[name] = f'ERROR:{exc}'

    def _age(self, key):
        stamp = self.last_seen.get(key)
        return None if stamp is None else time.monotonic() - stamp

    def _fresh(self, key, timeout):
        age = self._age(key)
        return age is not None and age <= timeout

    def _tf_ok(self, target, source):
        try:
            return self.tf_buffer.can_transform(
                target, source, Time(), timeout=Duration(seconds=0.05)
            )
        except Exception:
            return False

    def _report(self, reason):
        stale = float(self.get_parameter('stale_timeout_sec').value)
        map_timeout = float(self.get_parameter('map_timeout_sec').value)
        action_ready = self.nav_client.server_is_ready()
        lifecycle_ok = all(value.startswith('active') for value in self.lifecycle_states.values())
        tf_map_base = self._tf_ok('map', 'base_link')
        tf_odom_base = self._tf_ok('odom', 'base_footprint')

        checks = {
            'action_server': action_ready,
            'lifecycle_all_active': lifecycle_ok,
            'tf_map_base_link': tf_map_base,
            'tf_odom_base_footprint': tf_odom_base,
            'scan_fresh': self._fresh('scan', stale),
            'odom_fresh': self._fresh('odom', stale),
            'map_static_fresh': self._fresh('map_static', map_timeout),
            'global_costmap_fresh': self._fresh('global_costmap', map_timeout),
            'local_costmap_fresh': self._fresh('local_costmap', map_timeout),
        }
        failed = [name for name, passed in checks.items() if not passed]

        self.get_logger().warn(
            f'NAV2_DIAG[{reason}] failed={failed if failed else "none"}; '
            f'lifecycle={self.lifecycle_states}'
        )
        ages = {key: None if self._age(key) is None else round(self._age(key), 2)
                for key in ('scan', 'odom', 'map_static', 'global_costmap', 'local_costmap')}
        self.get_logger().warn(f'NAV2_DIAG[{reason}] ages_sec={ages}; checks={checks}')

        if not action_ready:
            self.get_logger().error('CAUSE: /navigate_to_pose action server unavailable.')
        if not lifecycle_ok:
            self.get_logger().error('CAUSE: Nav2 lifecycle node inactive or get_state service unavailable.')
        if not tf_map_base:
            self.get_logger().error('CAUSE: TF map -> base_link unavailable.')
        if not tf_odom_base:
            self.get_logger().error('CAUSE: TF odom -> base_footprint unavailable.')
        if not checks['global_costmap_fresh']:
            self.get_logger().error('CAUSE: global costmap missing or stale.')
        if not checks['local_costmap_fresh']:
            self.get_logger().error('CAUSE: local costmap missing or stale.')
        if not checks['map_static_fresh']:
            self.get_logger().error('CAUSE: /map_static missing or stale.')
        if not checks['scan_fresh'] or not checks['odom_fresh']:
            self.get_logger().error('CAUSE: robot sensor transport missing or stale.')
        if not failed:
            self.get_logger().warn(
                'CAUSE: infrastructure is healthy; suspect frontier goal outside costmap, '
                'occupied/inflated goal cell, or a concurrent navigation goal.'
            )

    def _periodic_report(self):
        self._report('PERIODIC')


def main(args=None):
    rclpy.init(args=args)
    node = Nav2FailureDiagnostics()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
