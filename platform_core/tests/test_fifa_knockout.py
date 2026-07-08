from platform_core import season_ops as so


def _room(n_teams, scores):
    parts = []
    sc = {}
    for i in range(n_teams):
        name = f"T{i}"
        player = f"p{i}"
        parts.append({"name": name, "squad": [{"name": player, "role": "Forward",
                                               "team": "X", "buy_price": 10}]})
        sc[player] = scores[i]
    return {"tournament_type": "FIFA World Cup 2026", "participants": parts,
            "gameweek_scores": {"R16": sc}}


def test_keep_top_8_releases_losers_players():
    # 10 teams, scores 100..10 -> keep top 8, eliminate T8 (20) and T9 (10)
    room = _room(10, [100, 90, 80, 70, 60, 50, 40, 30, 20, 10])
    elim, released = so.eliminate_below_position(room, "R16", keep_top=8)
    assert set(elim) == {"T8", "T9"}
    assert set(so.eliminated_names(room)) == {"T8", "T9"}
    # their players freed to the market pool
    pool = {p["name"] for p in room["unsold_players"]}
    assert {"p8", "p9"} <= pool
    # and removed from their squads
    by = {p["name"]: p for p in room["participants"]}
    assert by["T8"]["squad"] == []


def test_no_elimination_when_at_or_below_cutoff():
    room = _room(6, [60, 50, 40, 30, 20, 10])
    elim, released = so.eliminate_below_position(room, "R16", keep_top=8)
    assert elim == [] and released == []


def test_reverse_restores_squad_and_pool():
    room = _room(10, [100, 90, 80, 70, 60, 50, 40, 30, 20, 10])
    so.eliminate_below_position(room, "R16", keep_top=8)
    restored = so.reverse_last_elimination(room)
    assert set(restored) == {"T8", "T9"}
    assert so.eliminated_names(room) == set()
    by = {p["name"]: p for p in room["participants"]}
    assert by["T8"]["squad"] and by["T8"]["squad"][0]["name"] == "p8"  # squad restored
    assert {p["name"] for p in room["unsold_players"]} == set()        # pool cleaned


def test_progressive_rounds_keep_shrinking():
    room = _room(10, [100, 90, 80, 70, 60, 50, 40, 30, 20, 10])
    so.eliminate_below_position(room, "R16", keep_top=8)   # -> 8 left
    # reuse same scores for simplicity; next round keep top 4
    room["gameweek_scores"]["QF"] = room["gameweek_scores"]["R16"]
    elim2, _ = so.eliminate_below_position(room, "QF", keep_top=4)
    assert set(elim2) == {"T4", "T5", "T6", "T7"}   # the next 4 below top 4 (of remaining 8)
    assert len(so.eliminated_names(room)) == 6       # 2 + 4


def test_elimination_ranks_by_cumulative_not_single_gameweek():
    # A leads cumulatively but has a bad final gameweek; B has a great final GW
    # but is worst overall. Knockout must keep the best CUMULATIVE teams.
    room = {
        "tournament_type": "FIFA World Cup 2026",
        "participants": [
            {"name": "A", "squad": [{"name": "pA", "role": "Forward", "team": "X", "buy_price": 10}]},
            {"name": "B", "squad": [{"name": "pB", "role": "Forward", "team": "X", "buy_price": 10}]},
            {"name": "C", "squad": [{"name": "pC", "role": "Forward", "team": "X", "buy_price": 10}]},
        ],
        "gameweek_scores": {
            "1": {"pA": 100, "pB": 90, "pC": 5},    # cumulative: A=105, B=100, C=105
            "2": {"pA": 5, "pB": 10, "pC": 100},    # latest GW alone: C=100, B=10, A=5
        },
    }
    # keep_top=2 on the latest GW ("2") would eliminate A (worst that single week);
    # by cumulative, B is last (100 vs A/C at 105) and must be the one to go.
    elim, _ = so.eliminate_below_position(room, "2", keep_top=2)
    assert elim == ["B"]
