from season_engine.squad_lock import lock_participant


def _p(budget, players, ir=None):
    return {"name": "P", "budget": budget, "ir": ir,
            "squad": [{"name": n, "role": "Batsman", "buy_price": bp} for n, bp in players]}


def test_trims_over_19_releasing_cheapest():
    players = [(f"p{i}", i) for i in range(22)]  # 22 players, prices 0..21
    p = _p(100, players)
    released, notes = lock_participant(p)
    assert len(p["squad"]) == 19
    assert {r["name"] for r in released} == {"p0", "p1", "p2"}  # 3 cheapest


def test_no_forced_ir_below_19():
    p = _p(100, [("cheap", 5), ("dear", 80)])  # only 2 players
    lock_participant(p)
    assert p["ir"] is None       # IR not mandatory below 19
    assert p["budget"] == 100    # no 2M fee


def test_forced_ir_at_19():
    players = [(f"p{i}", i + 1) for i in range(19)]  # 19 players, p18 most expensive
    p = _p(100, players)
    lock_participant(p)
    assert p["ir"] == "p18"      # most expensive auto-benched
    assert p["budget"] == 98     # 2M IR fee


def test_voluntary_ir_is_charged():
    p = _p(100, [("a", 10), ("b", 20)], ir="a")
    lock_participant(p)
    assert p["ir"] == "a"
    assert p["budget"] == 98


def test_cannot_afford_ir_releases_ir_player():
    p = _p(1, [("a", 10), ("b", 20)], ir="a")
    released, _ = lock_participant(p)
    assert p["ir"] is None
    assert all(e["name"] != "a" for e in p["squad"])
    assert any(r["name"] == "a" for r in released)
    assert p["budget"] == 1


def test_full_squad_stale_ir_reassigned():
    players = [(f"p{i}", i + 1) for i in range(19)]
    p = _p(100, players, ir="ghost")  # not in squad
    lock_participant(p)
    assert p["ir"] == "p18"  # reassigned to most expensive
