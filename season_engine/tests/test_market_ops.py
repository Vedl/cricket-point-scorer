"""Tests for platform_core.market_ops trade normalization."""

from platform_core.market_ops import _normalize_trade, incoming_trades, propose_trade


def test_normalize_trade_fills_missing_give_players():
    legacy = {
        "id": "abc",
        "from": "A",
        "to": "B",
        "get_players": ["Player X"],
        "give_cash": 5,
        "get_cash": 0,
        "status": "pending",
    }
    t = _normalize_trade(legacy)
    assert t["give_players"] == []
    assert t["get_players"] == ["Player X"]


def test_incoming_trades_tolerates_legacy_record():
    room = {
        "participants": [
            {"name": "A", "budget": 50, "squad": []},
            {"name": "B", "budget": 50, "squad": [{"name": "Player X", "role": "", "team": "", "buy_price": 1}]},
        ],
        "pending_trades": [{
            "id": "legacy1",
            "from": "A",
            "to": "B",
            "get_players": ["Player X"],
            "give_cash": 5,
            "get_cash": 0,
            "status": "pending",
        }],
    }
    trades = incoming_trades(room, "B")
    assert len(trades) == 1
    assert trades[0]["give_players"] == []


def test_propose_trade_always_sets_player_lists():
    room = {
        "participants": [
            {"name": "A", "budget": 50, "squad": [{"name": "P1", "role": "", "team": "", "buy_price": 1}]},
            {"name": "B", "budget": 50, "squad": [{"name": "P2", "role": "", "team": "", "buy_price": 1}]},
        ],
        "pending_trades": [],
    }
    propose_trade(room, "A", "B", ["P1"], ["P2"])
    t = room["pending_trades"][0]
    assert t["give_players"] == ["P1"]
    assert t["get_players"] == ["P2"]
