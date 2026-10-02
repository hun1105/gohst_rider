from tb3_dynamic_detector.sensor_freshness_filter import (
    NANOSECONDS_PER_SECOND,
    StreamState,
)


def ns(seconds: float) -> int:
    return int(seconds * NANOSECONDS_PER_SECOND)


def test_accepts_fresh_increasing_messages():
    state = StreamState('scan', max_age_sec=0.7)

    assert state.accept(ns(9.8), ns(10.0), 0.1)[0]
    assert state.accept(ns(9.9), ns(10.0), 0.1)[0]
    assert state.accepted == 2


def test_drops_stale_message():
    state = StreamState('imu', max_age_sec=0.5)

    accepted, reason, _ = state.accept(ns(9.0), ns(10.0), 0.1)

    assert not accepted
    assert reason == 'stale'
    assert state.dropped_stale == 1


def test_drops_excessively_future_message():
    state = StreamState('odom', max_age_sec=0.5)

    accepted, reason, _ = state.accept(ns(10.2), ns(10.0), 0.1)

    assert not accepted
    assert reason == 'future'
    assert state.dropped_future == 1


def test_drops_duplicate_and_out_of_order_messages():
    state = StreamState('scan', max_age_sec=0.7)
    assert state.accept(ns(9.9), ns(10.0), 0.1)[0]

    duplicate = state.accept(ns(9.9), ns(10.0), 0.1)
    older = state.accept(ns(9.8), ns(10.0), 0.1)

    assert not duplicate[0]
    assert duplicate[1] == 'out_of_order'
    assert not older[0]
    assert older[1] == 'out_of_order'
    assert state.dropped_order == 2


def test_recovers_after_large_backwards_clock_jump():
    state = StreamState('scan', max_age_sec=0.7, reset_backwards_sec=1.0)
    assert state.accept(ns(99.9), ns(100.0), 0.1)[0]

    accepted, reason, _ = state.accept(ns(9.9), ns(10.0), 0.1)

    assert accepted
    assert reason == 'accepted'
    assert state.timestamp_resets == 1
