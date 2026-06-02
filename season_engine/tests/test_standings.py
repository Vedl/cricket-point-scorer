from season_engine.standings import (
    cumulative_standings,
    gameweek_standings,
    participant_gw_points,
    top_n,
)


def _squad(prefix, n_each=3):
    # small squad (<11) so Best-11 returns everyone -> easy point math
    squad = []
    for r, role in [("wk", "WK-Batsman"), ("bat", "Batsman"), ("bwl", "Bowler")]:
        for i in range(n_each):
            squad.append({"name": f"{prefix}_{r}{i}", "role": role})
    return squad


def test_participant_gw_points_small_squad_sums_all():
    squad = [{"name": "a", "role": "Batsman"}, {"name": "b", "role": "Bowler"}]
    scores = {"a": 30, "b": 20}
    pts, team, warns = participant_gw_points(squad, scores, is_football=False, gameweek=12)
    assert pts == 50
    assert len(team) == 2


def test_gameweek_standings_sorted():
    participants = [
        {"name": "Alice", "squad": _squad("al")},
        {"name": "Bob", "squad": _squad("bo")},
    ]
    scores = {}
    for p in participants:
        for s in p["squad"]:
            scores[s["name"]] = 10 if p["name"] == "Alice" else 5
    rows = gameweek_standings(participants, scores, is_football=False, gameweek=12)
    assert [r["participant"] for r in rows] == ["Alice", "Bob"]
    assert rows[0]["points"] > rows[1]["points"]


def test_cumulative_sums_across_gameweeks():
    participants = [
        {"name": "Alice", "squad": [{"name": "a", "role": "Batsman"}]},
        {"name": "Bob", "squad": [{"name": "b", "role": "Batsman"}]},
    ]
    all_scores = {
        "1": {"a": 10, "b": 5},
        "2": {"a": 20, "b": 30},
    }
    rows = cumulative_standings(participants, all_scores, is_football=False)
    by = {r["participant"]: r for r in rows}
    assert by["Alice"]["points"] == 30
    assert by["Bob"]["points"] == 35
    assert rows[0]["participant"] == "Bob"   # 35 > 30
    assert by["Alice"]["by_gameweek"] == {"1": 10, "2": 20}


def test_cumulative_uses_locked_snapshot_when_present():
    participants = [{"name": "Alice", "squad": [{"name": "current", "role": "Batsman"}]}]
    all_scores = {"1": {"locked": 50, "current": 5}}
    squads_by_gw = {"1": {"Alice": {"squad": [{"name": "locked", "role": "Batsman"}]}}}
    rows = cumulative_standings(participants, all_scores, is_football=False,
                                squads_by_gw=squads_by_gw)
    assert rows[0]["points"] == 50   # used the locked squad, not the current one


def test_top_n():
    standings = [{"participant": x, "points": p} for x, p in
                 [("A", 50), ("B", 40), ("C", 30), ("D", 20)]]
    assert [r["participant"] for r in top_n(standings, 3)] == ["A", "B", "C"]
