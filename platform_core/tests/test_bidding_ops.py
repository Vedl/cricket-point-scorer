from datetime import datetime, timedelta

import pytest

from platform_core import bidding_ops as bo
from platform_core import season_ops as so
from season_engine.open_bidding import BidError


def _room(deadline=None):
    r = {
        "tournament_type": "FIFA World Cup 2026",
        "player_pool": [
            {"name": "Messi", "role": "FWD", "team": "Argentina"},
            {"name": "Mbappe", "role": "FWD", "team": "France"},
            {"name": "Neuer", "role": "GK", "team": "Germany"},
        ],
        "participants": [
            {"name": "A", "budget": 100, "squad": [
                {"name": "Messi", "role": "FWD", "team": "Argentina", "buy_price": 30}]},
            {"name": "B", "budget": 100, "squad": []},
        ],
    }
    if deadline:
        r["bidding_deadline"] = deadline.isoformat()
    return r


NOW = datetime(2026, 6, 3, 12, 0, 0)


def test_owned_excluded_from_available():
    names = {p["name"] for p in bo.available_players(_room())}
    assert "Messi" not in names and {"Mbappe", "Neuer"} <= names


def test_frozen_when_no_deadline():
    with pytest.raises(BidError, match="frozen"):
        bo.place(_room(), "B", "Mbappe", 10, NOW)


def test_min_bid_5_and_place():
    room = _room(deadline=NOW + timedelta(hours=3))
    with pytest.raises(BidError, match="at least 5M"):
        bo.place(room, "B", "Mbappe", 4, NOW)
    bo.place(room, "B", "Mbappe", 5, NOW)
    assert bo.active(room)[0]["high_bid"] == 5


def test_increment_of_5_after_50():
    room = _room(deadline=NOW + timedelta(hours=3))
    bo.place(room, "B", "Mbappe", 50, NOW)
    with pytest.raises(BidError, match="multiples of 5M"):
        bo.place(room, "A", "Mbappe", 57, NOW)   # >= 55 min but not a multiple of 5
    bo.place(room, "A", "Mbappe", 55, NOW)
    assert bo.active(room)[0]["high_bid"] == 55


def test_budget_reservation_across_bids():
    room = _room(deadline=NOW + timedelta(hours=3))
    room["participants"][1]["budget"] = 100
    bo.place(room, "B", "Mbappe", 60, NOW)        # reserves 60
    with pytest.raises(BidError, match="available budget"):
        bo.place(room, "B", "Neuer", 50, NOW)     # 60+50 > 100
    bo.place(room, "B", "Neuer", 40, NOW)         # 60+40 = 100 ok


def test_no_new_players_in_final_hour():
    room = _room(deadline=NOW + timedelta(minutes=45))   # inside T-60m window
    with pytest.raises(BidError, match="no new players"):
        bo.place(room, "B", "Mbappe", 10, NOW)


def _raise_only_room(cur):
    """Room in the final (raise-only) window with a single seeded bid at ``cur``."""
    room = _room(deadline=NOW + timedelta(minutes=20))
    room["open_bids"] = {"Mbappe": {"high_bid": cur, "high_bidder": "B",
                                    "role": "FWD", "team": "France"}}
    return room


def test_raise_only_in_final_30m():
    room = _raise_only_room(20)
    with pytest.raises(BidError):
        bo.place(room, "A", "Mbappe", 22, NOW)     # not an exact +5 step
    bo.place(room, "A", "Mbappe", 25, NOW)
    assert bo.active(room)[0]["high_bid"] == 25


def test_raise_only_exact_5m_steps_and_post_50_snap():
    # (current bid, the min valid raise, an amount that must be rejected)
    cases = [
        (20, 25, 26),   # exact +5 below 50; +6 rejected
        (44, 49, 50),   # +5 keeps a sub-50 non-multiple (49); 50 isn't a +5 step from 44
        (46, 55, 51),   # +5 → 51 is past 50 → snap up to 55; 51 rejected
        (47, 55, 54),   # 47/48/49 all jump straight to 55
        (49, 55, 54),
        (50, 55, 52),   # at 50 → next is 55; multiples of 5 only past 50
    ]
    for cur, ok, bad in cases:
        room = _raise_only_room(cur)
        with pytest.raises(BidError):
            bo.place(room, "A", "Mbappe", bad, NOW)
        bo.place(room, "A", "Mbappe", ok, NOW)
        assert bo.active(room)[0]["high_bid"] == ok, f"cur={cur}"


def test_resolve_and_lock_timeline():
    dl = NOW
    room = _room(deadline=dl)
    so.set_bidding_deadline(room, dl.isoformat())
    room["open_bids"] = {"Mbappe": {"high_bid": 20, "high_bidder": "B", "role": "FWD", "team": "France"}}
    # at the deadline -> bids awarded
    events = so.process_room_deadline(room, dl)
    assert any("awarded" in e for e in events)
    by = {p["name"]: p for p in room["participants"]}
    assert any(e["name"] == "Mbappe" for e in by["B"]["squad"])
    # at +30m -> lock + advance + freeze
    events2 = so.process_room_deadline(room, dl + timedelta(minutes=31))
    assert any("locked" in e for e in events2)
    assert room["bidding_deadline"] is None      # frozen
    assert room["current_gameweek"] == 2


def test_trading_open_window():
    dl = NOW
    assert so.trading_open(_room(), NOW) is False              # no deadline
    assert so.trading_open(_room(deadline=dl), dl - timedelta(minutes=5)) is True
    assert so.trading_open(_room(deadline=dl), dl + timedelta(minutes=31)) is False
