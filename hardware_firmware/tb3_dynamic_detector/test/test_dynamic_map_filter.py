from tb3_dynamic_detector.dynamic_map_filter import mask_occupied_cells


def test_masks_only_occupied_cells_inside_radius():
    data = [0] * 25
    data[2 * 5 + 2] = 100
    data[2 * 5 + 3] = 80
    data[0] = 100

    filtered = mask_occupied_cells(
        data=data,
        width=5,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        origin_yaw=0.0,
        points=[(2.2, 2.2)],
        clear_radius=1.0,
        occupied_threshold=65,
    )

    assert filtered[2 * 5 + 2] == -1
    assert filtered[2 * 5 + 3] == -1
    assert filtered[0] == 100
    assert filtered[1] == 0


def test_preserves_cells_below_occupied_threshold():
    data = [0] * 9
    data[4] = 64

    filtered = mask_occupied_cells(
        data=data,
        width=3,
        height=3,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        origin_yaw=0.0,
        points=[(1.1, 1.1)],
        clear_radius=1.0,
        occupied_threshold=65,
    )

    assert filtered[4] == 64
