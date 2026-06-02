from season_engine.knockout import select_for_elimination, survivors


def _standings(pairs):
    return [{"participant": n, "points": p} for n, p in pairs]


def test_eliminate_lowest_one():
    s = _standings([("A", 50), ("B", 20), ("C", 35)])
    assert select_for_elimination(s, count=1) == ["B"]


def test_eliminate_lowest_two():
    s = _standings([("A", 50), ("B", 20), ("C", 35), ("D", 10)])
    assert set(select_for_elimination(s, count=2)) == {"B", "D"}


def test_skips_already_eliminated():
    s = _standings([("A", 50), ("B", 20), ("C", 35)])
    # B already gone -> next lowest active is C
    assert select_for_elimination(s, count=1, already_eliminated={"B"}) == ["C"]


def test_survivors():
    s = _standings([("A", 50), ("B", 20), ("C", 35)])
    assert set(survivors(s, {"B"})) == {"A", "C"}
