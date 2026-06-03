import pytest

from platform_core import bidding_ops as bo
from platform_core import season_ops as so
from season_engine.open_bidding import BidError


def _room():
    return {
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


def test_owned_players_excluded_from_available():
    room = _room()
    names = {p["name"] for p in bo.available_players(room)}
    assert "Messi" not in names          # owned via (CSV) auction
    assert {"Mbappe", "Neuer"} <= names


def test_place_bid_and_resolve_after_window():
    room = _room()
    bo.place(room, "B", "Mbappe", 20, now=1000.0, window=10)
    # not yet due
    assert bo.resolve(room, now=1005.0) == []
    assert bo.active(room, now=1005.0)[0]["player"] == "Mbappe"
    # window elapsed -> awarded
    awarded = bo.resolve(room, now=1011.0)
    assert awarded and awarded[0]["participant"] == "B"
    by = {p["name"]: p for p in room["participants"]}
    assert any(e["name"] == "Mbappe" for e in by["B"]["squad"])
    assert by["B"]["budget"] == 80
    assert bo.active(room, now=1011.0) == []   # bid cleared


def test_outbid_resets_window():
    room = _room()
    bo.place(room, "A", "Neuer", 10, now=1000.0, window=100)
    bo.place(room, "B", "Neuer", 15, now=1050.0, window=100)  # higher -> resets to 1150
    # at t=1120 (past A's original 1100 but not B's 1150) still active
    assert bo.resolve(room, now=1120.0) == []
    awarded = bo.resolve(room, now=1151.0)
    assert awarded[0]["participant"] == "B" and awarded[0]["amount"] == 15


def test_bid_must_beat_current():
    room = _room()
    bo.place(room, "A", "Neuer", 10, now=1000.0, window=100)
    with pytest.raises(BidError):
        bo.place(room, "B", "Neuer", 10, now=1001.0, window=100)  # not higher


def test_bid_over_budget_rejected():
    room = _room()
    room["participants"][1]["budget"] = 5
    with pytest.raises(BidError):
        bo.place(room, "B", "Mbappe", 50, now=1000.0)


def test_half_price_release_unlimited_before_gw1():
    room = _room()
    # A owns Messi (buy 30); release for half -> +15, and pre-GW1 unlimited
    refund = so.half_price_release(room, "A", "Messi")
    assert refund == 15
    a = next(p for p in room["participants"] if p["name"] == "A")
    assert a["budget"] == 115
    assert all(e["name"] != "Messi" for e in a["squad"])
    # Messi now available for open bidding again
    assert "Messi" in {p["name"] for p in bo.available_players(room)}


def test_half_price_limited_after_gw1():
    room = _room()
    room["gw1_locked"] = True
    room["participants"][0]["squad"].append(
        {"name": "X", "role": "FWD", "team": "Z", "buy_price": 20})
    so.half_price_release(room, "A", "Messi")
    with pytest.raises(so.SeasonError):
        so.half_price_release(room, "A", "X")   # second in same GW blocked


def test_set_ir_validates_ownership():
    room = _room()
    so.set_ir(room, "A", "Messi")
    assert room["participants"][0]["ir"] == "Messi"
    with pytest.raises(so.SeasonError):
        so.set_ir(room, "A", "Ronaldo")
