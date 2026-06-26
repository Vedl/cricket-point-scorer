"""Window-math tests for the timed deadline push scheduler (platform_core.push_schedule).

The deadline is fixed at DL; `due_alerts` is probed at exact boundaries, one minute
late, and well past, to prove the windowed/jitter-tolerant firing behaves per spec.
"""

from datetime import datetime, timedelta

from platform_core import push_schedule as ps


DL = datetime(2026, 6, 26, 20, 0)  # bidding deadline T


def keys_at(now, fired=None):
    return {k for k, _t, _b in ps.due_alerts(DL, now, fired or set())}


# Milestone moments: A=DL-60, B=DL-30, C=DL, D=DL+30.

def test_new_close_1h_fires_exactly_at_window_open():
    # A "1h before" window is [ (DL-60)-60, (DL-60)-30 ) = [DL-120, DL-90)
    assert "new_close_60" in keys_at(DL - timedelta(minutes=120))      # exactly at open
    assert "new_close_60" in keys_at(DL - timedelta(minutes=119))      # one minute late
    assert "new_close_60" not in keys_at(DL - timedelta(minutes=121))  # before the window
    assert "new_close_60" not in keys_at(DL - timedelta(minutes=90))   # at window close (exclusive)


def test_new_close_30m_and_at():
    # A "30m before" = [DL-90, DL-60); "at" = [DL-60, DL-50)
    assert keys_at(DL - timedelta(minutes=90)) == {"new_close_30"}
    assert "new_close_0" in keys_at(DL - timedelta(minutes=60))
    assert "new_close_0" not in keys_at(DL - timedelta(minutes=49))    # past the +10m at-window


def test_raise_only_has_no_1h_alert():
    # B = DL-30. A "1h before" would be [DL-90, DL-60) — must NOT exist for raise_only.
    all_keys = set()
    for m in range(0, 180):
        all_keys |= keys_at(DL - timedelta(minutes=m))
    assert "raise_only_60" not in all_keys
    assert "raise_only_30" in all_keys
    assert "raise_only_0" in all_keys


def test_bid_close_windows():
    assert "bid_close_60" in keys_at(DL - timedelta(minutes=60))   # [DL-60, DL-30)
    assert "bid_close_30" in keys_at(DL - timedelta(minutes=30))   # [DL-30, DL)
    assert "bid_close_0" in keys_at(DL)                            # [DL, DL+10)
    assert "bid_close_0" in keys_at(DL + timedelta(minutes=9))
    assert "bid_close_0" not in keys_at(DL + timedelta(minutes=10))  # window closed


def test_squad_lock_windows():
    # D = DL+30. "1h"=[DL-30, DL), "30m"=[DL, DL+30), "at"=[DL+30, DL+40)
    assert "squad_lock_60" in keys_at(DL - timedelta(minutes=30))
    assert "squad_lock_30" in keys_at(DL)
    assert "squad_lock_0" in keys_at(DL + timedelta(minutes=30))
    assert "squad_lock_0" not in keys_at(DL + timedelta(minutes=41))


def test_dedup_skips_already_fired():
    now = DL - timedelta(minutes=30)   # bid_close_30 due here
    assert "bid_close_30" in keys_at(now)
    assert "bid_close_30" not in keys_at(now, fired={"bid_close_30"})


def test_missed_minute_defers_not_drops():
    # If the tick missed exactly DL-60, the next minute still fires bid_close_60.
    assert "bid_close_60" in keys_at(DL - timedelta(minutes=59))


def test_stale_heads_up_never_arrives_late():
    # 5 minutes before the deadline, no "1 hour left" may appear.
    late = keys_at(DL - timedelta(minutes=5))
    assert "bid_close_60" not in late
    assert "new_close_60" not in late


def test_schedule_horizon_is_past_lock_at_window():
    assert ps.schedule_horizon(DL) == DL + timedelta(minutes=40)
    # nothing is due once now >= horizon
    assert keys_at(DL + timedelta(minutes=40)) == set()


def test_total_unique_alerts_is_eleven():
    seen = set()
    for m in range(-130, 60):
        seen |= keys_at(DL + timedelta(minutes=m))
    assert len(seen) == 11
