"""ROS-independent clustering and tracking logic."""

from collections import deque
from dataclasses import dataclass, field
import math
from statistics import median
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class ScanPoint:
    """One valid LaserScan return transformed into a fixed frame."""

    index: int
    range_m: float
    x: float
    y: float


@dataclass
class Cluster:
    """A contiguous group of scan returns."""

    points: List[ScanPoint]
    centroid: Tuple[float, float]
    support: float = 0.0
    grid_candidate: bool = False

    @property
    def scan_indices(self) -> List[int]:
        return [point.index for point in self.points]

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        xs = [point.x for point in self.points]
        ys = [point.y for point in self.points]
        return min(xs), max(xs), min(ys), max(ys)


@dataclass
class ConstantVelocityKalmanFilter:
    """Small dependency-free 2-D constant-velocity Kalman filter.

    State order is [x, y, vx, vy].  Measurements contain only [x, y].
    """

    x: List[float]
    p: List[List[float]]
    measurement_variance: float
    acceleration_variance: float

    @classmethod
    def create(
        cls,
        position: Tuple[float, float],
        position_std: float,
        velocity_std: float,
        measurement_std: float,
        acceleration_std: float,
    ) -> 'ConstantVelocityKalmanFilter':
        return cls(
            x=[position[0], position[1], 0.0, 0.0],
            p=[
                [position_std ** 2, 0.0, 0.0, 0.0],
                [0.0, position_std ** 2, 0.0, 0.0],
                [0.0, 0.0, velocity_std ** 2, 0.0],
                [0.0, 0.0, 0.0, velocity_std ** 2],
            ],
            measurement_variance=measurement_std ** 2,
            acceleration_variance=acceleration_std ** 2,
        )

    @property
    def position(self) -> Tuple[float, float]:
        return self.x[0], self.x[1]

    @property
    def velocity(self) -> Tuple[float, float]:
        return self.x[2], self.x[3]

    def predict(self, dt: float) -> None:
        if dt <= 0.0:
            return
        f = [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        self.x = [sum(row[j] * self.x[j] for j in range(4)) for row in f]
        fp = [
            [sum(f[row][j] * self.p[j][col] for j in range(4)) for col in range(4)]
            for row in range(4)
        ]
        self.p = [
            [sum(fp[row][j] * f[col][j] for j in range(4)) for col in range(4)]
            for row in range(4)
        ]

        # White-noise acceleration model, arranged for [x, y, vx, vy].
        q = self.acceleration_variance
        q_pos = 0.25 * dt ** 4 * q
        q_cross = 0.5 * dt ** 3 * q
        q_vel = dt ** 2 * q
        for row, col, value in (
            (0, 0, q_pos), (1, 1, q_pos),
            (0, 2, q_cross), (2, 0, q_cross),
            (1, 3, q_cross), (3, 1, q_cross),
            (2, 2, q_vel), (3, 3, q_vel),
        ):
            self.p[row][col] += value

    def mahalanobis_squared(self, measurement: Tuple[float, float]) -> float:
        dx = measurement[0] - self.x[0]
        dy = measurement[1] - self.x[1]
        s00 = self.p[0][0] + self.measurement_variance
        s01 = self.p[0][1]
        s10 = self.p[1][0]
        s11 = self.p[1][1] + self.measurement_variance
        determinant = s00 * s11 - s01 * s10
        if determinant <= 1e-12:
            return float('inf')
        inv00 = s11 / determinant
        inv01 = -s01 / determinant
        inv10 = -s10 / determinant
        inv11 = s00 / determinant
        return dx * (inv00 * dx + inv01 * dy) + dy * (inv10 * dx + inv11 * dy)

    def correct(self, measurement: Tuple[float, float]) -> None:
        innovation = [measurement[0] - self.x[0], measurement[1] - self.x[1]]
        s00 = self.p[0][0] + self.measurement_variance
        s01 = self.p[0][1]
        s10 = self.p[1][0]
        s11 = self.p[1][1] + self.measurement_variance
        determinant = s00 * s11 - s01 * s10
        if determinant <= 1e-12:
            return
        inverse_s = [
            [s11 / determinant, -s01 / determinant],
            [-s10 / determinant, s00 / determinant],
        ]
        k = [
            [
                self.p[row][0] * inverse_s[0][col]
                + self.p[row][1] * inverse_s[1][col]
                for col in range(2)
            ]
            for row in range(4)
        ]
        for row in range(4):
            self.x[row] += k[row][0] * innovation[0] + k[row][1] * innovation[1]

        # Joseph form keeps the covariance symmetric and non-negative.
        identity_minus_kh = [
            [
                (1.0 if row == col else 0.0)
                - (k[row][col] if col < 2 else 0.0)
                for col in range(4)
            ]
            for row in range(4)
        ]
        left = [
            [
                sum(identity_minus_kh[row][j] * self.p[j][col] for j in range(4))
                for col in range(4)
            ]
            for row in range(4)
        ]
        new_p = [
            [
                sum(left[row][j] * identity_minus_kh[col][j] for j in range(4))
                for col in range(4)
            ]
            for row in range(4)
        ]
        for row in range(4):
            for col in range(4):
                new_p[row][col] += (
                    self.measurement_variance * k[row][0] * k[col][0]
                    + self.measurement_variance * k[row][1] * k[col][1]
                )
        self.p = new_p


@dataclass
class Track:
    """Persistent state for one associated cluster."""

    track_id: int
    centroid: Tuple[float, float]
    velocity: Tuple[float, float]
    last_stamp: float
    decisions: Deque[bool]
    dynamic_until: float = 0.0
    cluster: Optional[Cluster] = None
    is_dynamic: bool = False
    position_history: Deque[Tuple[float, float, float]] = field(default_factory=deque)
    motion_displacement: float = 0.0
    kalman: Optional[ConstantVelocityKalmanFilter] = None
    filter_stamp: float = 0.0


def point_distance(a: ScanPoint, b: ScanPoint) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def cluster_threshold(
    range_m: float,
    base_distance: float,
    range_scale: float,
    maximum_gap: float,
) -> float:
    return min(maximum_gap, base_distance + range_scale * range_m)


def make_cluster(points: List[ScanPoint]) -> Cluster:
    count = float(len(points))
    centroid = (
        sum(point.x for point in points) / count,
        sum(point.y for point in points) / count,
    )
    return Cluster(points=points, centroid=centroid)


def cluster_scan_points(
    points: Sequence[ScanPoint],
    beam_count: int,
    base_distance: float,
    range_scale: float,
    maximum_gap: float,
    minimum_points: int,
) -> List[Cluster]:
    """Cluster contiguous beams using an adaptive Euclidean gap."""
    if not points:
        return []

    ordered = sorted(points, key=lambda point: point.index)
    groups: List[List[ScanPoint]] = []
    current = [ordered[0]]

    for point in ordered[1:]:
        previous = current[-1]
        contiguous = point.index == previous.index + 1
        threshold = cluster_threshold(
            max(point.range_m, previous.range_m),
            base_distance,
            range_scale,
            maximum_gap,
        )
        if contiguous and point_distance(previous, point) <= threshold:
            current.append(point)
        else:
            groups.append(current)
            current = [point]
    groups.append(current)

    # A 360-degree object can cross the last/first LaserScan index.
    if (
        len(groups) > 1
        and groups[0][0].index == 0
        and groups[-1][-1].index == beam_count - 1
    ):
        first = groups[0][0]
        last = groups[-1][-1]
        threshold = cluster_threshold(
            max(first.range_m, last.range_m),
            base_distance,
            range_scale,
            maximum_gap,
        )
        if point_distance(first, last) <= threshold:
            merged = groups[-1] + groups[0]
            groups = [merged] + groups[1:-1]

    return [
        make_cluster(group)
        for group in groups
        if len(group) >= minimum_points
    ]


class TemporalHistory:
    """Voxel-indexed recent scans for temporal support queries."""

    def __init__(self, max_frames: int, voxel_size: float) -> None:
        self._frames: Deque[Dict[Tuple[int, int], List[Tuple[float, float]]]] = deque(
            maxlen=max_frames
        )
        self.voxel_size = voxel_size

    def __len__(self) -> int:
        return len(self._frames)

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return (
            math.floor(x / self.voxel_size),
            math.floor(y / self.voxel_size),
        )

    def append(self, points: Iterable[ScanPoint]) -> None:
        frame: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        for point in points:
            frame.setdefault(self._cell(point.x, point.y), []).append(
                (point.x, point.y)
            )
        self._frames.append(frame)

    def point_support(
        self,
        point: ScanPoint,
        match_base: float,
        match_range_scale: float,
    ) -> float:
        if not self._frames:
            return 0.0

        radius = match_base + match_range_scale * point.range_m
        cell_x, cell_y = self._cell(point.x, point.y)
        cell_radius = max(1, math.ceil(radius / self.voxel_size))
        radius_squared = radius * radius
        matched_frames = 0

        for frame in self._frames:
            matched = False
            for dx in range(-cell_radius, cell_radius + 1):
                if matched:
                    break
                for dy in range(-cell_radius, cell_radius + 1):
                    for x, y in frame.get((cell_x + dx, cell_y + dy), ()):
                        squared = (point.x - x) ** 2 + (point.y - y) ** 2
                        if squared <= radius_squared:
                            matched = True
                            break
                    if matched:
                        break
            if matched:
                matched_frames += 1

        return matched_frames / len(self._frames)

    def cluster_support(
        self,
        cluster: Cluster,
        match_base: float,
        match_range_scale: float,
    ) -> float:
        supports = [
            self.point_support(point, match_base, match_range_scale)
            for point in cluster.points
        ]
        return median(supports) if supports else 0.0


@dataclass
class GridCellState:
    """Short-term occupancy evidence for one fixed-frame grid cell."""

    free_observations: int = 0
    occupied_observations: int = 0
    last_stamp: float = 0.0
    candidate_until: float = 0.0


class TemporalOccupancyGrid:
    """Evidence grid used to find objects entering observed free space.

    This is intentionally a short-term detector, not a replacement for the
    Cartographer map.  A point becomes a candidate only when its endpoint cell
    was repeatedly observed as free before the current scan reaches it.
    """

    def __init__(self, resolution: float, max_cell_age: float) -> None:
        self.resolution = resolution
        self.max_cell_age = max_cell_age
        self._cells: Dict[Tuple[int, int], GridCellState] = {}

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return (
            math.floor(x / self.resolution),
            math.floor(y / self.resolution),
        )

    @staticmethod
    def _line_cells(
        start: Tuple[int, int], end: Tuple[int, int]
    ) -> Iterable[Tuple[int, int]]:
        """Yield Bresenham cells from start through end."""
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            yield x0, y0
            if x0 == x1 and y0 == y1:
                return
            twice_error = 2 * error
            if twice_error >= dy:
                error += dy
                x0 += step_x
            if twice_error <= dx:
                error += dx
                y0 += step_y

    def candidate_points(
        self,
        points: Sequence[ScanPoint],
        free_confirmations: int,
        stamp: float,
        hold_seconds: float,
    ) -> List[ScanPoint]:
        """Return endpoints entering repeatedly free cells, with short hold."""
        candidates = []
        for point in points:
            state = self._cells.get(self._cell(point.x, point.y))
            if state is None:
                continue
            if state.free_observations >= free_confirmations:
                state.candidate_until = max(state.candidate_until, stamp + hold_seconds)
            if stamp <= state.candidate_until:
                candidates.append(point)
        return candidates

    def update(
        self,
        sensor_origin: Tuple[float, float],
        points: Sequence[ScanPoint],
        stamp: float,
    ) -> None:
        """Update free ray cells and occupied endpoints from one LaserScan."""
        origin_cell = self._cell(*sensor_origin)
        endpoint_cells = {self._cell(point.x, point.y) for point in points}

        # Rays are free until their endpoint.  Deduplication prevents a dense
        # cluster from artificially increasing the evidence in one scan.
        free_cells = set()
        for endpoint in endpoint_cells:
            for cell in self._line_cells(origin_cell, endpoint):
                if cell == endpoint:
                    break
                free_cells.add(cell)

        for cell in free_cells:
            state = self._cells.setdefault(cell, GridCellState())
            state.free_observations += 1
            state.occupied_observations = 0
            state.last_stamp = stamp

        for cell in endpoint_cells:
            state = self._cells.setdefault(cell, GridCellState())
            state.occupied_observations += 1
            state.free_observations = 0
            state.last_stamp = stamp

        expired = [
            cell
            for cell, state in self._cells.items()
            if stamp - state.last_stamp > self.max_cell_age
        ]
        for cell in expired:
            del self._cells[cell]


class ClusterTracker:
    """Greedy one-to-one centroid tracker with filtered velocity."""

    def __init__(
        self,
        association_distance: float,
        velocity_alpha: float,
        velocity_threshold: float,
        support_threshold: float,
        confirmation_window: int,
        confirmations_required: int,
        dynamic_hold_seconds: float,
        track_timeout: float,
        require_low_static_support: bool = True,
        enable_displacement_detection: bool = False,
        displacement_window_seconds: float = 0.60,
        displacement_threshold: float = 0.04,
        foreground_only_detection: bool = False,
        use_kalman_filter: bool = True,
        mahalanobis_gate: float = 5.99,
        kalman_position_std: float = 0.08,
        kalman_velocity_std: float = 0.50,
        kalman_measurement_std: float = 0.04,
        kalman_acceleration_std: float = 0.80,
        require_grid_candidate_for_dynamic: bool = False,
    ) -> None:
        self.association_distance = association_distance
        self.velocity_alpha = velocity_alpha
        self.velocity_threshold = velocity_threshold
        self.support_threshold = support_threshold
        self.confirmation_window = confirmation_window
        self.confirmations_required = confirmations_required
        self.dynamic_hold_seconds = dynamic_hold_seconds
        self.track_timeout = track_timeout
        self.require_low_static_support = require_low_static_support
        self.enable_displacement_detection = enable_displacement_detection
        self.displacement_window_seconds = displacement_window_seconds
        self.displacement_threshold = displacement_threshold
        self.foreground_only_detection = foreground_only_detection
        self.use_kalman_filter = use_kalman_filter
        self.mahalanobis_gate = mahalanobis_gate
        self.kalman_position_std = kalman_position_std
        self.kalman_velocity_std = kalman_velocity_std
        self.kalman_measurement_std = kalman_measurement_std
        self.kalman_acceleration_std = kalman_acceleration_std
        self.require_grid_candidate_for_dynamic = (
            require_grid_candidate_for_dynamic
        )
        self.tracks: Dict[int, Track] = {}
        self.next_track_id = 1

    def reset(self) -> None:
        """Discard motion state after an unreliable ego-motion interval."""
        self.tracks.clear()

    def _new_track(self, cluster: Cluster, stamp: float) -> Track:
        track = Track(
            track_id=self.next_track_id,
            centroid=cluster.centroid,
            velocity=(0.0, 0.0),
            last_stamp=stamp,
            decisions=deque(maxlen=self.confirmation_window),
            cluster=cluster,
            position_history=deque([(stamp, *cluster.centroid)]),
            filter_stamp=stamp,
        )
        if self.use_kalman_filter:
            track.kalman = ConstantVelocityKalmanFilter.create(
                position=cluster.centroid,
                position_std=self.kalman_position_std,
                velocity_std=self.kalman_velocity_std,
                measurement_std=self.kalman_measurement_std,
                acceleration_std=self.kalman_acceleration_std,
            )
        self.next_track_id += 1
        self.tracks[track.track_id] = track
        return track

    def _update_motion_displacement(
        self, track: Track, centroid: Tuple[float, float], stamp: float
    ) -> None:
        """Measure net centroid displacement over a fixed time window."""
        track.position_history.append((stamp, *centroid))
        keep_after = stamp - 2.0 * self.displacement_window_seconds
        while (
            len(track.position_history) > 1
            and track.position_history[0][0] < keep_after
        ):
            track.position_history.popleft()

        target_age = stamp - self.displacement_window_seconds
        reference = None
        for sample in reversed(track.position_history):
            if sample[0] <= target_age:
                reference = sample
                break

        if reference is None:
            track.motion_displacement = 0.0
            return

        _, old_x, old_y = reference
        track.motion_displacement = math.hypot(
            centroid[0] - old_x,
            centroid[1] - old_y,
        )

    def update(self, clusters: Sequence[Cluster], stamp: float) -> List[Track]:
        candidates = []
        for track in self.tracks.values():
            if self.use_kalman_filter and track.kalman is not None:
                track.kalman.predict(max(0.0, stamp - track.filter_stamp))
                track.filter_stamp = stamp
                predicted = track.kalman.position
            else:
                elapsed = max(0.0, stamp - track.last_stamp)
                predicted = (
                    track.centroid[0] + track.velocity[0] * elapsed,
                    track.centroid[1] + track.velocity[1] * elapsed,
                )
            for cluster_index, cluster in enumerate(clusters):
                distance = math.hypot(
                    predicted[0] - cluster.centroid[0],
                    predicted[1] - cluster.centroid[1],
                )
                if distance > self.association_distance:
                    continue
                score = distance
                if self.use_kalman_filter and track.kalman is not None:
                    score = track.kalman.mahalanobis_squared(cluster.centroid)
                    if score > self.mahalanobis_gate:
                        continue
                candidates.append((score, track.track_id, cluster_index))

        assigned_tracks = set()
        assigned_clusters = set()
        assignments = []
        for _, track_id, cluster_index in sorted(candidates):
            if track_id in assigned_tracks or cluster_index in assigned_clusters:
                continue
            assigned_tracks.add(track_id)
            assigned_clusters.add(cluster_index)
            assignments.append((track_id, cluster_index))

        visible_tracks: List[Track] = []
        for track_id, cluster_index in assignments:
            track = self.tracks[track_id]
            cluster = clusters[cluster_index]
            elapsed = stamp - track.last_stamp
            if self.use_kalman_filter and track.kalman is not None:
                track.kalman.correct(cluster.centroid)
                track.centroid = track.kalman.position
                track.velocity = track.kalman.velocity
            elif elapsed > 1e-4:
                raw_velocity = (
                    (cluster.centroid[0] - track.centroid[0]) / elapsed,
                    (cluster.centroid[1] - track.centroid[1]) / elapsed,
                )
                alpha = self.velocity_alpha
                track.velocity = (
                    alpha * track.velocity[0] + (1.0 - alpha) * raw_velocity[0],
                    alpha * track.velocity[1] + (1.0 - alpha) * raw_velocity[1],
                )

            speed = math.hypot(track.velocity[0], track.velocity[1])
            support_is_dynamic = (
                not self.require_low_static_support
                or cluster.support < self.support_threshold
            )
            self._update_motion_displacement(track, cluster.centroid, stamp)
            grid_evidence = (
                not self.require_grid_candidate_for_dynamic
                or cluster.grid_candidate
            )
            velocity_candidate = (
                speed > self.velocity_threshold
                and support_is_dynamic
                and grid_evidence
            )
            displacement_candidate = (
                self.enable_displacement_detection
                and track.motion_displacement >= self.displacement_threshold
                and support_is_dynamic
                and grid_evidence
            )
            # Foreground evidence is only an entry gate.  It must never make a
            # cluster dynamic by itself because ego-motion/TF error can shift
            # a static wall outside the recent-background tolerance.
            candidate = (
                velocity_candidate
                or displacement_candidate
            )
            track.decisions.append(candidate)
            if sum(track.decisions) >= self.confirmations_required:
                track.dynamic_until = stamp + self.dynamic_hold_seconds

            track.is_dynamic = stamp <= track.dynamic_until
            if not (self.use_kalman_filter and track.kalman is not None):
                track.centroid = cluster.centroid
            track.last_stamp = stamp
            track.cluster = cluster
            visible_tracks.append(track)

        for cluster_index, cluster in enumerate(clusters):
            if cluster_index not in assigned_clusters:
                visible_tracks.append(self._new_track(cluster, stamp))

        stale_ids = [
            track_id
            for track_id, track in self.tracks.items()
            if stamp - track.last_stamp > self.track_timeout
        ]
        for track_id in stale_ids:
            del self.tracks[track_id]

        return visible_tracks
