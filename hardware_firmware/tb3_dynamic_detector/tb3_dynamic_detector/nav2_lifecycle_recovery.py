"""Recover partially-started Nav2 lifecycle nodes without restarting active ones."""

from functools import partial
import time

from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState
from nav_msgs.msg import OccupancyGrid, Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class Nav2LifecycleRecovery(Node):
    # Preserve Nav2's normal lifecycle activation order.
    NODES = (
        'controller_server',
        'smoother_server',
        'planner_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
        'velocity_smoother',
    )

    def __init__(self):
        super().__init__('nav2_lifecycle_recovery')
        self.declare_parameter('manager_name', '/lifecycle_manager_navigation_super')
        self.declare_parameter('retry_period_sec', 10.0)
        self.declare_parameter('startup_grace_sec', 0.0)
        self.declare_parameter('scan_topic', '/scan_fresh')
        self.declare_parameter('odom_topic', '/odom_fresh')
        self.declare_parameter('map_topic', '/map_static')

        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.last_seen = {}
        self.states = {name: None for name in self.NODES}
        self.pending_states = set()
        self.transition_pending = None
        self.next_attempt_time = 0.0
        self.started_at = time.monotonic()
        self.retry_period = float(self.get_parameter('retry_period_sec').value)

        scan_topic = str(self.get_parameter('scan_topic').value)
        odom_topic = str(self.get_parameter('odom_topic').value)
        map_topic = str(self.get_parameter('map_topic').value)
        self.create_subscription(
            LaserScan, scan_topic, partial(self._touch, 'scan'), sensor_qos
        )
        self.create_subscription(
            Odometry, odom_topic, partial(self._touch, 'odom'), sensor_qos
        )
        self.create_subscription(
            OccupancyGrid, map_topic, partial(self._touch, 'map'), map_qos
        )

        self.state_clients = {
            name: self.create_client(GetState, f'/{name}/get_state') for name in self.NODES
        }
        self.change_clients = {
            name: self.create_client(ChangeState, f'/{name}/change_state')
            for name in self.NODES
        }
        self.create_timer(1.0, self._poll_states)
        self.create_timer(1.0, self._recover)
        self.get_logger().info(
            'Selective Nav2 lifecycle recovery ready: active nodes are preserved.'
        )

    def _touch(self, key, _msg):
        self.last_seen[key] = time.monotonic()

    def _fresh(self, key, limit):
        stamp = self.last_seen.get(key)
        return stamp is not None and time.monotonic() - stamp <= limit

    def _poll_states(self):
        for name, client in self.state_clients.items():
            if (
                name in self.pending_states
                or name == self.transition_pending
                or not client.service_is_ready()
            ):
                continue
            self.pending_states.add(name)
            future = client.call_async(GetState.Request())
            future.add_done_callback(partial(self._state_done, name))

    def _state_done(self, name, future):
        self.pending_states.discard(name)
        try:
            self.states[name] = future.result().current_state.label
        except Exception:
            self.states[name] = None

    def _recover(self):
        if all(state == 'active' for state in self.states.values()):
            return
        # map_static is not required here: activating a lifecycle node is a
        # plain service call, and the static costmap layer is transient_local
        # so it picks up the map whenever it arrives. Gating on map freshness
        # only made recovery wait on Cartographer's first-map timing, which
        # varies run to run and could stall startup far longer than needed.
        if not (self._fresh('scan', 2.0) and self._fresh('odom', 2.0)):
            self.get_logger().warn(f'Nav2 startup deferred; inputs not ready: {self.last_seen.keys()}')
            return
        now = time.monotonic()
        grace = float(self.get_parameter('startup_grace_sec').value)
        if now - self.started_at < grace:
            return
        if self.transition_pending is not None or now < self.next_attempt_time:
            return

        for name in self.NODES:
            state = self.states[name]
            if state == 'active':
                continue
            if state is None:
                return
            if state == 'unconfigured':
                self._request_transition(
                    name,
                    Transition.TRANSITION_CONFIGURE,
                    'configure',
                    'inactive',
                )
                return
            if state == 'inactive':
                self._request_transition(
                    name,
                    Transition.TRANSITION_ACTIVATE,
                    'activate',
                    'active',
                )
                return
            if state == 'finalized':
                self.get_logger().error(
                    f'Cannot recover finalized lifecycle node: {name}'
                )
                self.next_attempt_time = now + self.retry_period
                return

            # A configure/activate/deactivate transition is already running.
            self.get_logger().info(
                f'Waiting for {name} lifecycle transition; state={state}'
            )
            return

    def _request_transition(
        self,
        name,
        transition_id,
        transition_name,
        expected_state,
    ):
        client = self.change_clients[name]
        if not client.service_is_ready():
            self.get_logger().warn(
                f'{name} change_state service unavailable; retrying later.'
            )
            self.next_attempt_time = time.monotonic() + self.retry_period
            return

        request = ChangeState.Request()
        request.transition.id = transition_id
        self.transition_pending = name
        self.get_logger().warn(
            f'Nav2 selective recovery: {transition_name} {name}; states={self.states}'
        )
        future = client.call_async(request)
        future.add_done_callback(
            partial(
                self._transition_done,
                name,
                transition_name,
                expected_state,
            )
        )

    def _transition_done(
        self,
        name,
        transition_name,
        expected_state,
        future,
    ):
        self.transition_pending = None
        try:
            success = bool(future.result().success)
            if success:
                self.states[name] = expected_state
                self.next_attempt_time = time.monotonic() + 0.2
                self.get_logger().info(
                    f'Nav2 selective recovery succeeded: '
                    f'{transition_name} {name} -> {expected_state}'
                )
            else:
                self.states[name] = None
                self.next_attempt_time = time.monotonic() + self.retry_period
                self.get_logger().error(
                    f'Nav2 selective recovery rejected: '
                    f'{transition_name} {name}'
                )
        except Exception as exc:
            self.states[name] = None
            self.next_attempt_time = time.monotonic() + self.retry_period
            self.get_logger().error(
                f'Nav2 selective recovery call failed for {name}: {exc}'
            )


def main(args=None):
    rclpy.init(args=args)
    node = Nav2LifecycleRecovery()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
