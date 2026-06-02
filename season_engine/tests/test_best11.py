from season_engine.best11 import (
    classify_cricket,
    classify_football,
    cricket_ranges,
    select_best_11,
    total_points,
)


def _cricket_squad():
    # 2 WK, 5 BAT, 4 AR, 4 BWL = 15 players
    squad = []
    for i in range(2):
        squad.append({"name": f"wk{i}", "role": "WK-Batsman"})
    for i in range(5):
        squad.append({"name": f"bat{i}", "role": "Batsman"})
    for i in range(4):
        squad.append({"name": f"ar{i}", "role": "Batting Allrounder"})
    for i in range(4):
        squad.append({"name": f"bwl{i}", "role": "Bowler"})
    return squad


def test_classifiers():
    assert classify_cricket("WK-Batsman") == "WK"
    assert classify_cricket("Bowling Allrounder") == "AR"
    assert classify_cricket("Bowler") == "BWL"
    assert classify_cricket("Batsman") == "BAT"
    assert classify_football("GK") == "GK"
    assert classify_football("Centre Back") == "DEF"
    assert classify_football("Striker") == "FWD"
    assert classify_football("Central Midfield") == "MID"


def test_fewer_than_11_returns_all():
    squad = [{"name": f"p{i}", "role": "Batsman"} for i in range(7)]
    scores = {f"p{i}": i for i in range(7)}
    team, warns = select_best_11(squad, scores, is_football=False)
    assert len(team) == 7
    assert warns == []


def test_cricket_valid_xi_respects_ranges():
    squad = _cricket_squad()
    scores = {p["name"]: 10 for p in squad}
    team, warns = select_best_11(squad, scores, is_football=False, gameweek=12)
    assert warns == []
    assert len(team) == 11
    assert len({p["name"] for p in team}) == 11
    counts = {}
    for p in team:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    for role, (lo, hi) in cricket_ranges(12).items():
        assert lo <= counts.get(role, 0) <= hi


def test_cricket_caps_high_scorers_by_role_max():
    squad = _cricket_squad()
    # Make all 5 BAT huge; max BAT is 4, so only 4 can be picked.
    scores = {p["name"]: 1 for p in squad}
    for i in range(5):
        scores[f"bat{i}"] = 1000
    team, _ = select_best_11(squad, scores, is_football=False, gameweek=12)
    bat_count = sum(1 for p in team if p["category"] == "BAT")
    assert bat_count <= 4


def test_ir_excluded_only_when_squad_ge_19():
    # 19 players: 3 WK, 6 BAT, 5 AR, 5 BWL
    squad = []
    for i in range(3): squad.append({"name": f"wk{i}", "role": "WK-Batsman"})
    for i in range(6): squad.append({"name": f"bat{i}", "role": "Batsman"})
    for i in range(5): squad.append({"name": f"ar{i}", "role": "Batting Allrounder"})
    for i in range(5): squad.append({"name": f"bwl{i}", "role": "Bowler"})
    assert len(squad) == 19
    scores = {p["name"]: 5 for p in squad}
    scores["bat0"] = 999
    team, _ = select_best_11(squad, scores, is_football=False, gameweek=12, ir_player="bat0")
    assert all(p["name"] != "bat0" for p in team)  # IR excluded

    # With a smaller squad, IR is ignored.
    small = _cricket_squad()  # 15
    sc = {p["name"]: 5 for p in small}
    sc["bat0"] = 999
    team2, _ = select_best_11(small, sc, is_football=False, gameweek=12, ir_player="bat0")
    assert any(p["name"] == "bat0" for p in team2)


def test_football_exactly_one_gk():
    squad = []
    for i in range(2): squad.append({"name": f"gk{i}", "role": "GK"})
    for i in range(6): squad.append({"name": f"def{i}", "role": "Defender"})
    for i in range(6): squad.append({"name": f"mid{i}", "role": "Midfielder"})
    for i in range(4): squad.append({"name": f"fwd{i}", "role": "Forward"})
    scores = {p["name"]: 5 for p in squad}
    team, warns = select_best_11(squad, scores, is_football=True)
    assert warns == []
    gk = sum(1 for p in team if p["category"] == "GK")
    assert gk == 1


def test_dual_position_player_counted_once():
    squad = _cricket_squad()
    # Give one player a dual-position score dict; they must appear at most once.
    scores = {p["name"]: 10 for p in squad}
    scores["ar0"] = {"AR": 50, "BWL": 80}
    team, _ = select_best_11(squad, scores, is_football=False, gameweek=12)
    assert sum(1 for p in team if p["name"] == "ar0") <= 1


def test_gameweek_changes_ranges():
    assert cricket_ranges(5)["AR"] == (3, 6)    # old rule (gw <= 10)
    assert cricket_ranges(12)["AR"] == (2, 6)   # new rule
    assert cricket_ranges(None)["BWL"] == (3, 4)


def test_greedy_fallback_when_impossible():
    # 1 WK, 8 BAT, 4 AR, 0 BWL -> cannot meet BWL>=3, but other roles fill up.
    squad = [{"name": "wk0", "role": "WK-Batsman"}]
    squad += [{"name": f"bat{i}", "role": "Batsman"} for i in range(8)]
    squad += [{"name": f"ar{i}", "role": "Batting Allrounder"} for i in range(4)]
    scores = {p["name"]: 10 for p in squad}
    team, warns = select_best_11(squad, scores, is_football=False, gameweek=12)
    assert warns and "Could not satisfy" in warns[0]
    assert len(team) == 11
    assert any(p["name"].startswith("[Empty BWL") for p in team)


def test_total_points_helper():
    squad = _cricket_squad()
    scores = {p["name"]: 7 for p in squad}
    assert total_points(squad, scores, is_football=False, gameweek=12) == 77
