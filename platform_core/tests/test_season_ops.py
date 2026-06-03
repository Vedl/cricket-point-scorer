from platform_core import season_ops as so


def _room():
    return {
        "tournament_type": "IPL 2026",
        "participants": [
            {"name": "Alice", "squad": [
                {"name": "Kohli", "role": "Batsman"},
                {"name": "Bumrah", "role": "Bowler"},
            ]},
            {"name": "Bob", "squad": [
                {"name": "Rohit", "role": "Batsman"},
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
    assert by["Alice"] == 80   # 50 + 30
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


def test_lock_squads_snapshot_and_freezes_market():
    room = _room()
    room["bidding_open"] = True
    so.lock_squads_for_gameweek(room, "1")
    assert "Alice" in room["gameweek_squads"]["1"]
    assert room["bidding_open"] is False


def test_lock_then_change_squad_uses_snapshot():
    room = _room()
    so.lock_squads_for_gameweek(room, "1")
    # Alice swaps her whole squad afterwards
    room["participants"][0]["squad"] = [{"name": "Nobody", "role": "Batsman"}]
    rows = so.compute_cumulative_standings(room)
    by = {r["participant"]: r["points"] for r in rows}
    # GW1 used the locked snapshot (Kohli+Bumrah=80); GW2 uses current squad (Nobody=0)
    assert by["Alice"] == 80


def test_advance_gameweek():
    room = {"current_gameweek": 2}
    assert so.advance_gameweek(room) == 3
    assert room["current_gameweek"] == 3
