"""Drop stale, future-dated, duplicate, and out-of-order robot sensor data."""

from dataclasses import dataclass
from typing import Dict, Optional

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import String


NANOSECONDS_PER_SECOND = 1_000_000_000


@dataclass
class StreamState:
    name: str
    max_age_sec: float
    reset_backwards_sec: float = 1.0
    last_accepted_stamp_ns: Optional[int] = None
    accepted: int = 0
    dropped_stale: int = 0
    dropped_future: int = 0
    dropped_order: int = 0
    dropped_zero: int = 0
    timestamp_resets: int = 0
    last_age_sec: Optional[float] = None

    def accept(
        self,
        stamp_ns: int,
        now_ns: int,
        future_tolerance_sec: float,
    ) -> tuple[bool, str, float]:
        age_sec = (now_ns - stamp_ns) / NANOSECONDS_PER_SECOND
        self.last_age_sec = age_sec

        if stamp_ns <= 0:
            self.dropped_zero += 1
            return False, 'zero_stamp', age_sec

        if age_sec > self.max_age_sec:
            self.dropped_stale += 1
            return False, 'stale', age_sec

        if age_sec < -future_tolerance_sec:
            self.dropped_future += 1
            return False, 'future', age_sec

        if self.last_accepted_stamp_ns is not None:
            backwards_ns = self.last_accepted_stamp_ns - stamp_ns
            reset_ns = int(self.reset_backwards_sec * NANOSECONDS_PER_SECOND)
            if backwards_ns > reset_ns:
                # Both clocks may jump after NTP correction or system resume.
                # A fresh message is a safe boundary for resetting order state.
                self.last_accepted_stamp_ns = None
                self.timestamp_resets += 1
            elif stamp_ns <= self.last_accepted_stamp_ns:
                self.dropped_order += 1
                return False, 'out_of_order', age_sec

        self.last_accepted_stamp_ns = stamp_ns
        self.accepted += 1
        return True, 'accepted', age_sec


class SensorFreshnessFilter(Node):
    """Publish only the newest temporally valid sensor messages."""

    def __init__(self) -> None:
        super().__init__('sensor_freshness_filter')

        self.declare_parameter('scan_input_topic', '/scan')
        self.declare_parameter('scan_output_topic', '/scan_fresh')
        self.declare_parameter('imu_input_topic', '/imu')
        self.declare_parameter('imu_output_topic', '/imu_fresh')
        self.declare_parameter('odom_input_topic', '/odom')
        self.declare_parameter('odom_output_topic', '/odom_fresh')
        self.declare_parameter('scan_max_age_sec', 0.70)
        self.declare_parameter('imu_max_age_sec', 0.50)
        self.declare_parameter('odom_max_age_sec', 0.50)
        self.declare_parameter('future_tolerance_sec', 0.10)
        self.declare_parameter('reset_backwards_sec', 1.0)
        self.declare_parameter('status_period_sec', 5.0)
        self.declare_parameter('warning_throttle_sec', 2.0)

        self.future_tolerance_sec = float(
            self.get_parameter('future_tolerance_sec').value
        )
        self.warning_throttle_sec = float(
            self.get_parameter('warning_throttle_sec').value
        )
        reset_backwards_sec = float(
            self.get_parameter('reset_backwards_sec').value
        )

        self.states: Dict[str, StreamState] = {
            'scan': StreamState(
                'scan',
                float(self.get_parameter('scan_max_age_sec').value),
                reset_backwards_sec,
            ),
            'imu': StreamState(
                'imu',
                float(self.get_parameter('imu_max_age_sec').value),
                reset_backwards_sec,
            ),
            'odom': StreamState(
                'odom',
                float(self.get_parameter('odom_max_age_sec').value),
                reset_backwards_sec,
            ),
        }
        self.last_warning_ns: Dict[str, int] = {}

        # Latest-only sensor QoS prevents application-side backlog growth.
        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        scan_input = str(self.get_parameter('scan_input_topic').value)
        scan_output = str(self.get_parameter('scan_output_topic').value)
        imu_input = str(self.get_parameter('imu_input_topic').value)
        imu_output = str(self.get_parameter('imu_output_topic').value)
        odom_input = str(self.get_parameter('odom_input_topic').value)
        odom_output = str(self.get_parameter('odom_output_topic').value)

        self.scan_publisher = self.create_publisher(
            LaserScan, scan_output, sensor_qos
        )
        self.imu_publisher = self.create_publisher(Imu, imu_output, sensor_qos)
        self.odom_publisher = self.create_publisher(
            Odometry, odom_output, sensor_qos
        )
        self.status_publisher = self.create_publisher(
            String, '/sensor_freshness/status', 10
        )

        self.create_subscription(
            LaserScan,
            scan_input,
            lambda message: self._filter('scan', message, self.scan_publisher),
            sensor_qos,
        )
        self.create_subscription(
            Imu,
            imu_input,
            lambda message: self._filter('imu', message, self.imu_publisher),
            sensor_qos,
        )
        self.create_subscription(
            Odometry,
            odom_input,
            lambda message: self._filter('odom', message, self.odom_publisher),
            sensor_qos,
        )

        status_period = max(
            1.0, float(self.get_parameter('status_period_sec').value)
        )
        self.create_timer(status_period, self._publish_status)

        self.get_logger().info(
            'Freshness filter ready: '
            f'{scan_input}->{scan_output} max={self.states["scan"].max_age_sec:.2f}s, '
            f'{imu_input}->{imu_output} max={self.states["imu"].max_age_sec:.2f}s, '
            f'{odom_input}->{odom_output} max={self.states["odom"].max_age_sec:.2f}s, '
            f'future_tolerance={self.future_tolerance_sec:.2f}s'
        )

    @staticmethod
    def _stamp_ns(message) -> int:
        stamp = message.header.stamp
        return stamp.sec * NANOSECONDS_PER_SECOND + stamp.nanosec

    def _filter(self, name: str, message, publisher) -> None:
        now_ns = self.get_clock().now().nanoseconds
        accepted, reason, age_sec = self.states[name].accept(
            self._stamp_ns(message),
            now_ns,
            self.future_tolerance_sec,
        )
        if accepted:
            publisher.publish(message)
            return

        warning_key = f'{name}:{reason}'
        last_warning = self.last_warning_ns.get(warning_key, 0)
        throttle_ns = int(self.warning_throttle_sec * NANOSECONDS_PER_SECOND)
        if now_ns - last_warning >= throttle_ns:
            self.last_warning_ns[warning_key] = now_ns
            self.get_logger().warning(
                f'Dropped {name}: reason={reason}, age={age_sec:.3f}s'
            )

    def _publish_status(self) -> None:
        parts = []
        for name, state in self.states.items():
            age = 'none' if state.last_age_sec is None else f'{state.last_age_sec:.3f}'
            parts.append(
                f'{name}[ok={state.accepted},stale={state.dropped_stale},'
                f'future={state.dropped_future},order={state.dropped_order},'
                f'zero={state.dropped_zero},resets={state.timestamp_resets},'
                f'last_age={age}s]'
            )
        text = ' '.join(parts)
        self.status_publisher.publish(String(data=text))
        self.get_logger().info(text)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SensorFreshnessFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
