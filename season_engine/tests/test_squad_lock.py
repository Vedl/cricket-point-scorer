from season_engine.squad_lock import lock_participant


def _p(budget, players, ir=None):
    return {"name": "P", "budget": budget, "ir": ir,
            "squad": [{"name": n, "role": "Batsman", "buy_price": bp} for n, bp in players]}


def test_trims_over_19_releasing_cheapest():
    players = [(f"p{i}", i) for i in range(22)]  # 22 players, prices 0..21
    p = _p(100, players)
    released, notes = lock_participant(p)
    assert len(p["squad"]) == 19
    # the 3 cheapest (p0,p1,p2) were released
    assert {r["name"] for r in released} == {"p0", "p1", "p2"}


def test_auto_ir_most_expensive_when_none_set():
    p = _p(100, [("cheap", 5), ("dear", 80)])
    lock_participant(p)
    assert p["ir"] == "dear"
    assert p["budget"] == 98   # 2M IR fee


def test_keeps_valid_ir_and_charges_fee():
    p = _p(100, [("a", 10), ("b", 20)], ir="a")
    lock_participant(p)
    assert p["ir"] == "a"
    assert p["budget"] == 98


def test_cannot_afford_ir_releases_ir_player():
    p = _p(1, [("a", 10), ("b", 20)], ir="a")  # budget 1 < 2
    released, notes = lock_participant(p)
    assert p["ir"] is None
    assert all(e["name"] != "a" for e in p["squad"])
    assert any(r["name"] == "a" for r in released)
    assert p["budget"] == 1  # unchanged (no fee paid)


def test_stale_ir_reassigned():
    p = _p(100, [("a", 10), ("b", 50)], ir="ghost")  # ghost not in squad
    lock_participant(p)
    assert p["ir"] == "b"  # most expensive
