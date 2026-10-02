import math

from tb3_dynamic_detector.core import (
    Cluster,
    ClusterTracker,
    ScanPoint,
    TemporalHistory,
    TemporalOccupancyGrid,
    cluster_scan_points,
)


def test_clusters_split_at_large_gap():
    points = [
        ScanPoint(0, 1.0, 1.0, 0.00),
        ScanPoint(1, 1.0, 1.0, 0.02),
        ScanPoint(2, 1.0, 1.0, 0.04),
        ScanPoint(3, 1.5, 1.5, 0.10),
        ScanPoint(4, 1.5, 1.5, 0.12),
        ScanPoint(5, 1.5, 1.5, 0.14),
    ]
    clusters = cluster_scan_points(points, 360, 0.08, 0.02, 0.18, 3)
    assert len(clusters) == 2


def test_temporal_support_for_repeated_point():
    history = TemporalHistory(max_frames=6, voxel_size=0.05)
    for offset in (0.00, 0.01, -0.01, 0.02):
        history.append([ScanPoint(0, 2.0, 1.0 + offset, 1.0)])
    point = ScanPoint(0, 2.0, 1.0, 1.0)
    assert math.isclose(history.point_support(point, 0.05, 0.02), 1.0)


def test_track_becomes_dynamic_after_confirmations():
    tracker = ClusterTracker(
        association_distance=0.35,
        velocity_alpha=0.0,
        velocity_threshold=0.15,
        support_threshold=0.50,
        confirmation_window=4,
        confirmations_required=3,
        dynamic_hold_seconds=0.8,
        track_timeout=0.5,
    )

    for frame in range(5):
        x = frame * 0.05
        cluster = Cluster(
            points=[ScanPoint(0, 1.0, x, 0.0)] * 3,
            centroid=(x, 0.0),
            support=0.0,
        )
        visible = tracker.update([cluster], frame * 0.1)

    assert visible[0].is_dynamic


def test_kalman_filter_associates_and_estimates_velocity():
    tracker = ClusterTracker(
        association_distance=0.35,
        velocity_alpha=0.0,
        velocity_threshold=0.01,
        support_threshold=0.50,
        confirmation_window=3,
        confirmations_required=2,
        dynamic_hold_seconds=0.8,
        track_timeout=0.5,
        use_kalman_filter=True,
        mahalanobis_gate=9.21,
        kalman_position_std=0.10,
        kalman_velocity_std=0.50,
        kalman_measurement_std=0.03,
        kalman_acceleration_std=0.80,
    )
    for frame in range(5):
        x = frame * 0.04
        cluster = Cluster(
            points=[ScanPoint(0, 1.0, x, 0.0)] * 3,
            centroid=(x, 0.0),
            support=0.0,
        )
        visible = tracker.update([cluster], frame * 0.1)

    assert visible[0].track_id == 1
    assert visible[0].velocity[0] > 0.10


def test_grid_evidence_rejects_reappearing_wall_cluster():
    tracker = ClusterTracker(
        association_distance=0.35,
        velocity_alpha=0.0,
        velocity_threshold=0.01,
        support_threshold=0.50,
        confirmation_window=3,
        confirmations_required=2,
        dynamic_hold_seconds=0.8,
        track_timeout=0.5,
        foreground_only_detection=True,
        require_grid_candidate_for_dynamic=True,
    )
    for frame in range(4):
        cluster = Cluster(
            points=[ScanPoint(0, 1.0, 0.02 * frame, 0.0)] * 3,
            centroid=(0.02 * frame, 0.0),
            support=0.0,
            grid_candidate=False,
        )
        visible = tracker.update([cluster], frame * 0.1)
    assert not visible[0].is_dynamic


def test_temporal_grid_marks_new_endpoint_in_known_free_space():
    grid = TemporalOccupancyGrid(resolution=0.10, max_cell_age=10.0)
    wall = ScanPoint(0, 1.0, 1.00, 0.00)
    for stamp in range(4):
        grid.update((0.0, 0.0), [wall], float(stamp))

    entering_object = ScanPoint(0, 0.5, 0.50, 0.00)
    candidates = grid.candidate_points(
        [entering_object], free_confirmations=3, stamp=4.0, hold_seconds=0.8
    )
    assert candidates == [entering_object]


def test_track_becomes_dynamic_from_persistent_displacement():
    tracker = ClusterTracker(
        association_distance=0.35,
        velocity_alpha=0.0,
        velocity_threshold=1.0,
        support_threshold=0.50,
        confirmation_window=3,
        confirmations_required=2,
        dynamic_hold_seconds=0.8,
        track_timeout=0.5,
        require_low_static_support=True,
        enable_displacement_detection=True,
        displacement_window_seconds=0.4,
        displacement_threshold=0.03,
    )

    for frame in range(7):
        x = frame * 0.01
        cluster = Cluster(
            points=[ScanPoint(0, 1.0, x, 0.0)] * 3,
            centroid=(x, 0.0),
            # Low static support: a wall-suppression-eligible foreground
            # cluster, not a full-history-matched wall (support=1.0 would
            # always fail require_low_static_support by design).
            support=0.0,
        )
        visible = tracker.update([cluster], frame * 0.1)

    assert visible[0].is_dynamic


if __name__ == '__main__':
    test_clusters_split_at_large_gap()
    test_temporal_support_for_repeated_point()
    test_track_becomes_dynamic_after_confirmations()
    test_kalman_filter_associates_and_estimates_velocity()
    test_grid_evidence_rejects_reappearing_wall_cluster()
    test_temporal_grid_marks_new_endpoint_in_known_free_space()
    test_track_becomes_dynamic_from_persistent_displacement()
    print('CORE_TESTS_OK')
