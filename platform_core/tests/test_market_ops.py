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


def test_propose_accept_then_admin_approve():
    room = _room()
    tid = mo.propose_trade(room, "A", "B", ["Kohli"], ["Rohit"])
    assert len(mo.incoming_trades(room, "B")) == 1
    # counterparty accepts -> awaits admin, NOT yet applied
    mo.accept_trade(room, tid)
    assert mo.trades_awaiting_admin(room)
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Kohli" for e in by["A"]["squad"])  # unchanged pre-approval
    # admin approves -> applied
    mo.admin_approve_trade(room, tid)
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Rohit" for e in by["A"]["squad"])
    assert any(e["name"] == "Kohli" for e in by["B"]["squad"])
    assert mo.transactions(room)[0]["type"] == "trade"
    assert mo.trades_awaiting_admin(room) == []


def test_admin_reject_trade():
    room = _room()
    tid = mo.propose_trade(room, "A", "B", ["Kohli"], ["Rohit"])
    mo.accept_trade(room, tid)
    mo.admin_reject_trade(room, tid)
    assert mo.trades_awaiting_admin(room) == []
    by = mo.participants_by_name(room)
    assert any(e["name"] == "Kohli" for e in by["A"]["squad"])  # not applied


def test_reject_trade_by_counterparty():
    room = _room()
    tid = mo.propose_trade(room, "A", "B", ["Kohli"], ["Rohit"])
    mo.reject_trade(room, tid)
    assert mo.incoming_trades(room, "B") == []


def test_propose_invalid_raises():
    room = _room()
    with pytest.raises(TradeError):
        mo.propose_trade(room, "A", "B", ["Ghost"], ["Rohit"])


def test_incoming_trades_normalizes_legacy_singular_keys():
    room = {
        "pending_trades": [{
            "id": "abc", "from": "A", "to": "B", "status": "pending",
            "give_player": "Kohli", "get_player": "Rohit",
            "give_cash": 5, "get_cash": 0,
        }],
    }
    trades = mo.incoming_trades(room, "B")
    assert trades[0]["give_players"] == ["Kohli"]
    assert trades[0]["get_players"] == ["Rohit"]


def test_incoming_trades_missing_player_lists_default_empty():
    room = {
        "pending_trades": [{
            "id": "cash", "from": "A", "to": "B", "status": "pending",
            "give_cash": 10, "get_cash": 0,
        }],
    }
    trades = mo.incoming_trades(room, "B")
    assert trades[0]["give_players"] == []
    assert trades[0]["get_players"] == []


def test_release_to_pool_and_refund():
    room = _room()
    mo.release(room, "A", "Kohli", refund=True)
    by = mo.participants_by_name(room)
    assert by["A"]["budget"] == 140
    assert any(p["name"] == "Kohli" for p in mo.available_players(room))
