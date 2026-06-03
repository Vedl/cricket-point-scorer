import pytest

from season_engine.market import MarketError, release_player, resolve_sealed_bids
from season_engine.trading import TradeError, apply_trade, validate_trade


def _p(name, budget, players):
    return {"name": name, "budget": budget,
            "squad": [{"name": n, "role": "Batsman", "team": "X", "buy_price": bp}
                      for n, bp in players]}


# --- trading ------------------------------------------------------------- #
def test_valid_player_for_player_trade():
    a = _p("A", 50, [("Kohli", 40)])
    b = _p("B", 50, [("Rohit", 35)])
    rec = apply_trade(a, b, ["Kohli"], ["Rohit"])
    assert any(e["name"] == "Rohit" for e in a["squad"])
    assert any(e["name"] == "Kohli" for e in b["squad"])
    assert rec["type"] == "trade"
    # acquired_via marked
    assert a["squad"][0]["acquired_via"] == "trade"


def test_trade_with_cash_adjusts_budgets():
    a = _p("A", 50, [("Kohli", 40)])
    b = _p("B", 50, [])
    # A gives Kohli, receives 30M cash from B.
    apply_trade(a, b, ["Kohli"], [], give_cash=0, get_cash=30)
    assert a["budget"] == 80
    assert b["budget"] == 20
    assert any(e["name"] == "Kohli" for e in b["squad"])


def test_trade_rejects_unaffordable_cash():
    a = _p("A", 5, [])
    b = _p("B", 50, [("Rohit", 20)])
    errors = validate_trade(a, b, [], ["Rohit"], give_cash=20, get_cash=0)
    assert any("cannot afford" in e for e in errors)
    with pytest.raises(TradeError):
        apply_trade(a, b, [], ["Rohit"], give_cash=20, get_cash=0)


def test_trade_rejects_unowned_player():
    a = _p("A", 50, [])
    b = _p("B", 50, [("Rohit", 20)])
    errors = validate_trade(a, b, ["Ghost"], ["Rohit"])
    assert any("doesn't own Ghost" in e for e in errors)


def test_trade_respects_squad_cap():
    a = _p("A", 50, [("p1", 1)])
    b = _p("B", 50, [("q1", 1), ("q2", 1)])
    # A receives 2, gives 1 -> size 2; cap 2 ok. Lower cap to force failure:
    errors = validate_trade(a, b, ["p1"], ["q1", "q2"], max_squad=1)
    assert any("exceed the squad limit" in e for e in errors)


# --- market -------------------------------------------------------------- #
def test_release_with_refund():
    a = _p("A", 10, [("Kohli", 40)])
    rec = release_player(a, "Kohli", refund=True)
    assert rec["name"] == "Kohli"
    assert a["budget"] == 50
    assert a["squad"] == []


def test_release_without_refund():
    a = _p("A", 10, [("Kohli", 40)])
    release_player(a, "Kohli", refund=False)
    assert a["budget"] == 10


def test_release_unowned_raises():
    a = _p("A", 10, [])
    with pytest.raises(MarketError):
        release_player(a, "Ghost")


def test_sealed_bids_highest_valid_wins():
    a = _p("A", 100, [])
    b = _p("B", 100, [])
    parts = {"A": a, "B": b}
    player = {"name": "Free Agent", "role": "Bowler", "team": "Z"}
    rec = resolve_sealed_bids(parts, player, [
        {"participant": "A", "amount": 30},
        {"participant": "B", "amount": 45},
    ])
    assert rec["participant"] == "B" and rec["amount"] == 45
    assert b["budget"] == 55
    assert any(e["name"] == "Free Agent" for e in b["squad"])


def test_sealed_bids_skips_unaffordable():
    a = _p("A", 20, [])
    b = _p("B", 100, [])
    parts = {"A": a, "B": b}
    player = {"name": "FA", "role": "Bowler", "team": "Z"}
    # A bids 50 but only has 20 -> skipped; B wins at 25
    rec = resolve_sealed_bids(parts, player, [
        {"participant": "A", "amount": 50},
        {"participant": "B", "amount": 25},
    ])
    assert rec["participant"] == "B"


def test_sealed_bids_none_valid():
    a = _p("A", 5, [])
    parts = {"A": a}
    player = {"name": "FA", "role": "Bowler", "team": "Z"}
    assert resolve_sealed_bids(parts, player, [{"participant": "A", "amount": 50}]) is None
