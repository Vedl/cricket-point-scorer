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
    # auto-IR'd the most expensive (Kohli) and charged 2M, then +100 GW1 boost
    alice = next(p for p in room["participants"] if p["name"] == "Alice")
    assert alice["ir"] == "Kohli"
    assert alice["budget"] == 50 - 2 + 100


def test_lock_snapshot_used_for_scoring_with_ir():
    room = _room()
    so.lock_gameweek(room, "1")   # Alice IR = Kohli (excluded)
    # Alice swaps her whole live squad afterwards
    next(p for p in room["participants"] if p["name"] == "Alice")["squad"] = [
        {"name": "Nobody", "role": "Batsman"}]
    rows = so.compute_cumulative_standings(room)
    by = {r["participant"]: r["points"] for r in rows}
    # GW1 uses the locked snapshot with Kohli in IR -> only Bumrah (30) counts
    assert by["Alice"] == 30


def test_advance_gameweek():
    room = {"current_gameweek": 2}
    assert so.advance_gameweek(room) == 3
    assert room["current_gameweek"] == 3
