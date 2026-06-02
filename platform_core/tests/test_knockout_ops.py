from platform_core import season_ops as so


def _room():
    return {
        "tournament_type": "IPL 2026",
        "participants": [
            {"name": "A", "squad": [{"name": "Kohli", "role": "Batsman"}]},
            {"name": "B", "squad": [{"name": "Rohit", "role": "Batsman"}]},
            {"name": "C", "squad": [{"name": "Gill", "role": "Batsman"}]},
        ],
        "gameweek_scores": {"1": {"Kohli": 80, "Rohit": 10, "Gill": 40}},
    }


def test_eliminate_for_gameweek():
    room = _room()
    losers = so.eliminate_for_gameweek(room, "1", count=1)
    assert losers == ["B"]   # Rohit lowest
    assert so.eliminated_names(room) == {"B"}
    assert room["knockout_history"][-1]["eliminated"] == ["B"]


def test_eliminate_skips_already_out_then_reverse():
    room = _room()
    so.eliminate_for_gameweek(room, "1", count=1)   # B out
    losers2 = so.eliminate_for_gameweek(room, "1", count=1)  # next lowest active = C (40)
    assert losers2 == ["C"]
    assert so.eliminated_names(room) == {"B", "C"}
    # reverse the last round (C comes back)
    restored = so.reverse_last_elimination(room)
    assert restored == ["C"]
    assert so.eliminated_names(room) == {"B"}


def test_reverse_with_no_history():
    assert so.reverse_last_elimination({"participants": []}) == []
