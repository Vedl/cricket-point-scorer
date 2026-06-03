import pytest

from platform_core import season_ops as so


def _room():
    return {
        "tournament_type": "IPL 2026",
        "participants": [
            {"name": "Alice", "budget": 50, "squad": [
                {"name": "Kohli", "role": "Batsman", "buy_price": 50},
                {"name": "Bumrah", "role": "Bowler", "buy_price": 30},
            ]},
            {"name": "Bob", "budget": 50, "squad": [
                {"name": "Rohit", "role": "Batsman", "buy_price": 40},
            ]},
        ],
        "gameweek_scores": {
            "1": {"Kohli": 50, "Bumrah": 30, "Rohit": 40},
            "2": {"Kohli": 10, "Bumrah": 20, "Rohit": 5},
        },
    }


def test_gameweek_standings():
    rows = so.compute_gameweek_standings(_room(), "1")
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Alice"] == 80   # 50 + 30 (no IR set on the live squad)
    assert by["Bob"] == 40
    assert rows[0]["participant"] == "Alice"


def test_cumulative_standings():
    rows = so.compute_cumulative_standings(_room())
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Alice"] == 110   # (50+30) + (10+20)
    assert by["Bob"] == 45      # 40 + 5


def test_gameweeks_with_scores():
    assert so.gameweeks_with_scores(_room()) == ["1", "2"]


def test_parse_scores_text():
    scores, errors = so.parse_scores_text("Kohli, 50\nBumrah,30\nbad line\nRohit, x")
    assert scores == {"Kohli": 50, "Bumrah": 30}
    assert len(errors) == 2


def test_lock_freezes_market_snapshots_and_boosts():
    room = _room()
    room["bidding_open"] = True
    notes, first = so.lock_gameweek(room, "1")
    assert "Alice" in room["gameweek_squads"]["1"]
    assert room["bidding_open"] is False
    assert first is True
    alice = next(p for p in room["participants"] if p["name"] == "Alice")
    # small squad (<19) -> no forced IR, no 2M fee; +100 GW1 boost
    assert alice["ir"] is None
    assert alice["budget"] == 50 + 100


def test_lock_snapshot_used_for_scoring():
    room = _room()
    so.lock_gameweek(room, "1")
    next(p for p in room["participants"] if p["name"] == "Alice")["squad"] = [
        {"name": "Nobody", "role": "Batsman"}]
    rows = so.compute_cumulative_standings(room)
    by = {r["participant"]: r["points"] for r in rows}
    # GW1 uses the locked snapshot (Kohli 50 + Bumrah 30); no IR on a small squad
    assert by["Alice"] == 80


def test_ir_ignored_below_19():
    # A voluntary IR on a small (<19) squad does NOT count — the player still scores.
    room = _room()
    next(p for p in room["participants"] if p["name"] == "Alice")["ir"] = "Kohli"
    so.lock_gameweek(room, "1")
    rows = so.compute_cumulative_standings(room)
    by = {r["participant"]: r["points"] for r in rows}
    assert by["Alice"] == 110   # (50+30)+(10+20) — Kohli counts


def test_half_price_release_unlimited_before_gw1():
    room = _room()
    refund = so.half_price_release(room, "Alice", "Kohli")   # buy 50 -> +25
    a = next(p for p in room["participants"] if p["name"] == "Alice")
    assert refund == 25 and a["budget"] == 75
    assert all(e["name"] != "Kohli" for e in a["squad"])


def test_half_price_then_free_after_gw1():
    room = _room()
    room["gw1_locked"] = True
    assert so.half_price_release(room, "Alice", "Kohli") == 25   # first = half price
    assert so.half_price_release(room, "Alice", "Bumrah") == 0   # second = free


def test_set_ir_validates_ownership():
    room = _room()
    so.set_ir(room, "Alice", "Kohli")
    assert next(p for p in room["participants"] if p["name"] == "Alice")["ir"] == "Kohli"
    with pytest.raises(so.SeasonError):
        so.set_ir(room, "Alice", "Ronaldo")


def test_advance_gameweek():
    room = {"current_gameweek": 2}
    assert so.advance_gameweek(room) == 3
    assert room["current_gameweek"] == 3
