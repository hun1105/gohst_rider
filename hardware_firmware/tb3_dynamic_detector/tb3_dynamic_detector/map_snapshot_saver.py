"""Accumulate occupancy grids and save them on request or shutdown."""

from datetime import datetime
import binascii
import math
import os
import struct
from typing import Optional
import zlib

from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_srvs.srv import Trigger

from tb3_dynamic_detector.paths import map_path


DEFAULT_MAP_PATH = map_path('tb3_map')

# ==================== 사용자 수정 위치 ====================
# 누적 지도에서 이 점유확률(0~100) 미만인 셀은
# 두 번째 PNG에서 장애물로 표시하지 않습니다.
ACCUMULATED_MAP_FILTER_THRESHOLD = 70
# ==========================================================


class MapSnapshotSaver(Node):
    """Save an accumulated /map as Nav2 PGM/YAML plus a viewable PNG."""

    def __init__(self) -> None:
        super().__init__('tb3_map_snapshot_saver')

        self.declare_parameter('map_topic', '/map')
        self.declare_parameter('map_path', DEFAULT_MAP_PATH)
        self.declare_parameter('append_timestamp', True)
        self.declare_parameter('save_on_shutdown', True)
        self.declare_parameter('accumulate_map', True)
        self.declare_parameter('occupied_threshold', 65)
        self.declare_parameter('free_threshold', 25)
        self.declare_parameter('clear_unknown_cells', False)
        self.declare_parameter(
            'filtered_map_threshold',
            ACCUMULATED_MAP_FILTER_THRESHOLD,
        )

        self.map_topic = str(self.get_parameter('map_topic').value)
        self.map_path = str(self.get_parameter('map_path').value)
        self.append_timestamp = bool(
            self.get_parameter('append_timestamp').value
        )
        self.save_on_shutdown = bool(
            self.get_parameter('save_on_shutdown').value
        )
        self.accumulate_map = bool(
            self.get_parameter('accumulate_map').value
        )
        self.occupied_threshold = int(
            self.get_parameter('occupied_threshold').value
        )
        self.free_threshold = int(
            self.get_parameter('free_threshold').value
        )
        self.clear_unknown_cells = bool(
            self.get_parameter('clear_unknown_cells').value
        )
        self.filtered_map_threshold = int(
            self.get_parameter('filtered_map_threshold').value
        )
        if not 0 <= self.filtered_map_threshold <= 100:
            raise ValueError('filtered_map_threshold must be between 0 and 100.')
        self.latest_map: Optional[OccupancyGrid] = None
        self.accumulated_data: Optional[list[int]] = None
        self.accumulated_width = 0
        self.accumulated_height = 0
        self.accumulated_resolution = 0.0
        self.accumulated_origin_x = 0.0
        self.accumulated_origin_y = 0.0
        self.accumulated_yaw = 0.0

        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.map_subscription = self.create_subscription(
            OccupancyGrid,
            self.map_topic,
            self._map_callback,
            map_qos,
        )
        self.save_service = self.create_service(
            Trigger,
            '/save_map_now',
            self._save_callback,
        )
        self.get_logger().info(
            f'Map saver ready: {self.map_topic}; '
            f'accumulate_map={self.accumulate_map}; '
            f'filtered_map_threshold={self.filtered_map_threshold}; '
            'call /save_map_now or stop the launch to save.'
        )

    def _map_callback(self, message: OccupancyGrid) -> None:
        self.latest_map = message
        if self.accumulate_map:
            try:
                self._merge_into_accumulated_map(message)
            except ValueError as error:
                self.get_logger().warning(
                    f'Map frame not accumulated: {error}'
                )

    def _initialize_accumulated_map(self, message: OccupancyGrid) -> None:
        width = int(message.info.width)
        height = int(message.info.height)
        if width <= 0 or height <= 0 or len(message.data) != width * height:
            raise ValueError('Received invalid occupancy grid dimensions.')

        self.accumulated_width = width
        self.accumulated_height = height
        self.accumulated_resolution = float(message.info.resolution)
        self.accumulated_origin_x = float(message.info.origin.position.x)
        self.accumulated_origin_y = float(message.info.origin.position.y)
        self.accumulated_yaw = self._yaw_from_quaternion(
            message.info.origin.orientation
        )
        self.accumulated_data = [int(value) for value in message.data]

    def _merge_occupancy(self, old: int, new: int) -> int:
        """Keep occupied history while combining known free-space evidence."""
        if new < 0:
            return -1 if self.clear_unknown_cells else old
        if old < 0:
            return new
        if old >= self.occupied_threshold:
            return max(old, new) if new >= self.occupied_threshold else old
        if new >= self.occupied_threshold:
            return new
        return min(old, new)

    def _merge_into_accumulated_map(self, message: OccupancyGrid) -> None:
        if self.accumulated_data is None:
            self._initialize_accumulated_map(message)
            return

        width = int(message.info.width)
        height = int(message.info.height)
        resolution = float(message.info.resolution)
        if width <= 0 or height <= 0 or len(message.data) != width * height:
            raise ValueError('Received invalid occupancy grid dimensions.')
        if not math.isclose(
            resolution,
            self.accumulated_resolution,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError('Map resolution changed during accumulation.')

        yaw = self._yaw_from_quaternion(message.info.origin.orientation)
        yaw_error = math.atan2(
            math.sin(yaw - self.accumulated_yaw),
            math.cos(yaw - self.accumulated_yaw),
        )
        if abs(yaw_error) > 1e-6:
            raise ValueError('Map origin rotation changed during accumulation.')

        dx = float(message.info.origin.position.x) - self.accumulated_origin_x
        dy = float(message.info.origin.position.y) - self.accumulated_origin_y
        cos_yaw = math.cos(self.accumulated_yaw)
        sin_yaw = math.sin(self.accumulated_yaw)
        offset_x_float = (cos_yaw * dx + sin_yaw * dy) / resolution
        offset_y_float = (-sin_yaw * dx + cos_yaw * dy) / resolution
        offset_x = int(round(offset_x_float))
        offset_y = int(round(offset_y_float))
        if (
            abs(offset_x_float - offset_x) > 0.05
            or abs(offset_y_float - offset_y) > 0.05
        ):
            raise ValueError('Map origin is not aligned to the occupancy grid.')

        minimum_x = min(0, offset_x)
        minimum_y = min(0, offset_y)
        maximum_x = max(self.accumulated_width, offset_x + width)
        maximum_y = max(self.accumulated_height, offset_y + height)
        merged_width = maximum_x - minimum_x
        merged_height = maximum_y - minimum_y
        merged = [-1] * (merged_width * merged_height)

        old_x_offset = -minimum_x
        old_y_offset = -minimum_y
        for y in range(self.accumulated_height):
            old_start = y * self.accumulated_width
            merged_start = (y + old_y_offset) * merged_width + old_x_offset
            merged[merged_start:merged_start + self.accumulated_width] = (
                self.accumulated_data[
                    old_start:old_start + self.accumulated_width
                ]
            )

        new_x_offset = offset_x - minimum_x
        new_y_offset = offset_y - minimum_y
        for y in range(height):
            source_start = y * width
            destination_start = (y + new_y_offset) * merged_width + new_x_offset
            for x in range(width):
                destination = destination_start + x
                merged[destination] = self._merge_occupancy(
                    merged[destination],
                    int(message.data[source_start + x]),
                )

        shift_x = minimum_x * resolution
        shift_y = minimum_y * resolution
        self.accumulated_origin_x += (
            cos_yaw * shift_x - sin_yaw * shift_y
        )
        self.accumulated_origin_y += (
            sin_yaw * shift_x + cos_yaw * shift_y
        )
        self.accumulated_width = merged_width
        self.accumulated_height = merged_height
        self.accumulated_data = merged

    def _save_callback(self, request, response):
        del request
        try:
            path = self.save_latest()
        except (OSError, ValueError) as error:
            response.success = False
            response.message = str(error)
            return response

        response.success = True
        response.message = (
            f'Saved map: {path}.pgm, {path}.yaml, {path}.png, '
            f'{path}_threshold.png'
        )
        return response

    def _output_path(self) -> str:
        path = os.path.abspath(os.path.expanduser(self.map_path))
        if self.append_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = f'{path}_{timestamp}'
        return path

    @staticmethod
    def _yaw_from_quaternion(rotation) -> float:
        sin_yaw = 2.0 * (
            rotation.w * rotation.z + rotation.x * rotation.y
        )
        cos_yaw = 1.0 - 2.0 * (
            rotation.y * rotation.y + rotation.z * rotation.z
        )
        return math.atan2(sin_yaw, cos_yaw)

    @staticmethod
    def _write_png(path: str, width: int, height: int, pixels: bytes) -> None:
        """Write an 8-bit grayscale PNG using only Python standard library."""

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            payload = chunk_type + data
            checksum = binascii.crc32(payload) & 0xffffffff
            return (
                struct.pack('>I', len(data))
                + payload
                + struct.pack('>I', checksum)
            )

        scanlines = bytearray()
        for row in range(height):
            start = row * width
            scanlines.append(0)  # PNG filter: None
            scanlines.extend(pixels[start:start + width])

        png = bytearray(b'\x89PNG\r\n\x1a\n')
        png.extend(chunk(
            b'IHDR',
            struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0),
        ))
        png.extend(chunk(b'IDAT', zlib.compress(bytes(scanlines), level=9)))
        png.extend(chunk(b'IEND', b''))

        with open(path, 'wb') as png_file:
            png_file.write(png)

    def save_latest(self) -> str:
        message = self.latest_map
        if message is None:
            raise ValueError('No /map message received yet.')

        if self.accumulate_map and self.accumulated_data is not None:
            width = self.accumulated_width
            height = self.accumulated_height
            resolution = self.accumulated_resolution
            origin_x = self.accumulated_origin_x
            origin_y = self.accumulated_origin_y
            yaw = self.accumulated_yaw
            grid_data = self.accumulated_data
        else:
            width = int(message.info.width)
            height = int(message.info.height)
            resolution = float(message.info.resolution)
            origin_x = float(message.info.origin.position.x)
            origin_y = float(message.info.origin.position.y)
            yaw = self._yaw_from_quaternion(message.info.origin.orientation)
            grid_data = message.data

        expected_size = width * height
        if width <= 0 or height <= 0 or len(grid_data) != expected_size:
            raise ValueError('Received invalid occupancy grid dimensions.')

        output_path = self._output_path()
        output_directory = os.path.dirname(output_path)
        os.makedirs(output_directory, exist_ok=True)

        pgm_path = f'{output_path}.pgm'
        yaml_path = f'{output_path}.yaml'
        png_path = f'{output_path}.png'
        threshold_png_path = f'{output_path}_threshold.png'
        pixels = bytearray(expected_size)
        threshold_pixels = bytearray(expected_size)
        destination = 0

        # OccupancyGrid starts at the lower-left; PGM starts at the upper-left.
        for y in range(height - 1, -1, -1):
            row_start = y * width
            for x in range(width):
                occupancy = int(grid_data[row_start + x])
                if occupancy < 0:
                    pixel = 205
                elif occupancy >= self.occupied_threshold:
                    pixel = 0
                elif occupancy <= self.free_threshold:
                    pixel = 254
                else:
                    pixel = 205
                pixels[destination] = pixel

                # Unknown remains gray. Known cells below the user threshold
                # are removed from the filtered obstacle image as white.
                if occupancy < 0:
                    threshold_pixel = 205
                elif occupancy >= self.filtered_map_threshold:
                    threshold_pixel = 0
                else:
                    threshold_pixel = 254
                threshold_pixels[destination] = threshold_pixel
                destination += 1

        with open(pgm_path, 'wb') as pgm_file:
            pgm_file.write(f'P5\n{width} {height}\n255\n'.encode('ascii'))
            pgm_file.write(pixels)

        self._write_png(png_path, width, height, pixels)
        self._write_png(
            threshold_png_path,
            width,
            height,
            threshold_pixels,
        )

        with open(yaml_path, 'w', encoding='utf-8') as yaml_file:
            yaml_file.write(
                f'image: {os.path.basename(pgm_path)}\n'
                'mode: trinary\n'
                f'resolution: {resolution:.9g}\n'
                f'origin: [{origin_x:.9g}, '
                f'{origin_y:.9g}, {yaw:.9g}]\n'
                'negate: 0\n'
                f'occupied_thresh: {self.occupied_threshold / 100.0:.9g}\n'
                f'free_thresh: {self.free_threshold / 100.0:.9g}\n'
            )

        self.get_logger().info(
            f'Saved map: {pgm_path}, {yaml_path}, {png_path}, '
            f'{threshold_png_path}'
        )
        return output_path


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MapSnapshotSaver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node.save_on_shutdown:
            try:
                node.save_latest()
            except (OSError, ValueError) as error:
                node.get_logger().warning(f'Map not saved on shutdown: {error}')
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
