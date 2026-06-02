import pytest

from platform_core import market_ops as mo
from season_engine.trading import TradeError


def _room():
    return {
        "tournament_type": "IPL 2026",
        "participants": [
            {"name": "A", "budget": 100, "squad": [
                {"name": "Kohli", "role": "Batsman", "team": "RCB", "buy_price": 40}]},
            {"name": "B", "budget": 100, "squad": [
                {"name": "Rohit", "role": "Batsman", "team": "MI", "buy_price": 35}]},
        ],
    }


def test_propose_and_accept_trade():
    room = _room()
    tid = mo.propose_trade(room, "A", "B", ["Kohli"], ["Rohit"])
    assert len(mo.incoming_trades(room, "B")) == 1
    mo.accept_trade(room, tid)
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Rohit" for e in by["A"]["squad"])
    assert any(e["name"] == "Kohli" for e in by["B"]["squad"])
    assert mo.transactions(room)[0]["type"] == "trade"
    assert mo.incoming_trades(room, "B") == []  # no longer pending


def test_reject_trade():
    room = _room()
    tid = mo.propose_trade(room, "A", "B", ["Kohli"], ["Rohit"])
    mo.reject_trade(room, tid)
    assert mo.incoming_trades(room, "B") == []
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Kohli" for e in by["A"]["squad"])  # unchanged


def test_propose_invalid_raises():
    room = _room()
    with pytest.raises(TradeError):
        mo.propose_trade(room, "A", "B", ["Ghost"], ["Rohit"])


def test_release_to_pool_and_refund():
    room = _room()
    mo.release(room, "A", "Kohli", refund=True)
    by = mo.participants_by_name(room)
    assert by["A"]["budget"] == 140
    assert any(p["name"] == "Kohli" for p in mo.available_players(room))


def test_market_bid_and_resolve():
    room = _room()
    mo.release(room, "A", "Kohli", refund=False)   # Kohli now a free agent
    mo.place_market_bid(room, "B", "Kohli", 25)
    rec = mo.resolve_market(room, "Kohli")
    assert rec["participant"] == "B" and rec["amount"] == 25
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Kohli" for e in by["B"]["squad"])
    assert mo.available_players(room) == []   # removed from pool


def test_market_bid_over_budget_rejected():
    room = _room()
    room["participants"][1]["budget"] = 10
    mo.release(room, "A", "Kohli")
    with pytest.raises(TradeError):
        mo.place_market_bid(room, "B", "Kohli", 50)


def test_bid_replaces_previous():
    room = _room()
    mo.release(room, "A", "Kohli")
    mo.place_market_bid(room, "B", "Kohli", 20)
    mo.place_market_bid(room, "B", "Kohli", 30)
    bids = [b for b in room["active_bids"] if b["player"] == "Kohli"]
    assert len(bids) == 1 and bids[0]["amount"] == 30
