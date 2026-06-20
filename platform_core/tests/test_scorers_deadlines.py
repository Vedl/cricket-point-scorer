from datetime import datetime, timedelta

from platform_core import season_ops as so


def test_top_player_scorers_aggregates_with_owner():
    room = {
        "tournament_type": "IPL 2026",
        "participants": [{"name": "A", "squad": [{"name": "Kohli", "role": "Batsman"}]}],
        "gameweek_scores": {"1": {"Kohli": 50, "Rohit": 40}, "2": {"Kohli": 20, "Rohit": 10}},
    }
    rows = so.top_player_scorers(room)
    assert rows[0] == {"player": "Kohli", "points": 70, "owner": "A", "country": "—"}
    assert rows[1] == {"player": "Rohit", "points": 50, "owner": "—", "country": "—"}


def test_scorers_carry_country_from_squad_team():
    room = {
        "tournament_type": "fifa_world_cup",
        "participants": [{"name": "A", "squad": [{"name": "Messi", "team": "Argentina"}]}],
        "gameweek_scores": {"1": {"Messi": 30}, "2": {"Messi": 5}},
    }
    assert so.top_player_scorers(room)[0]["country"] == "Argentina"
    found = so.search_player_points(room, query="mess")
    assert found[0]["country"] == "Argentina"
    # cumulative vs single-gameweek both keep the country
    assert so.search_player_points(room, gameweek="1")[0]["country"] == "Argentina"


def test_process_due_deadlines_locks_and_advances():
    now = datetime(2026, 6, 3, 12, 0, 0)
    room = {
        "tournament_type": "IPL 2026", "current_gameweek": 0,
        "participants": [{"name": "A", "budget": 100,
                          "squad": [{"name": "K", "role": "Batsman", "buy_price": 10}]}],
        "gameweek_scores": {"1": {"K": 5}},
        "gameweek_deadlines": {
            "1": (now - timedelta(minutes=1)).isoformat(),   # due
            "2": (now + timedelta(days=1)).isoformat(),      # not due
        },
    }
    processed = so.process_due_deadlines(room, now)
    assert processed == ["1"]
    assert "1" in room["gameweek_squads"]      # locked
    assert room["current_gameweek"] == 1       # advanced
    # running again doesn't re-process an already-locked gameweek
    assert so.process_due_deadlines(room, now) == []


def test_set_deadline():
    room = {}
    so.set_deadline(room, "3", "2026-07-01T18:00:00")
    assert so.deadlines(room)["3"] == "2026-07-01T18:00:00"
