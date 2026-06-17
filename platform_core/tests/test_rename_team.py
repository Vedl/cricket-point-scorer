"""Tests for rename_team — verifying the fix that allows repeated renames
and correct propagation across all room data structures."""

import pytest

from platform_core.admin_ops import AdminError, rename_team


def _room():
    """Room fixture with rich cross-references for propagation tests."""
    return {
        "tournament_type": "FIFA World Cup 2026",
        "participants": [
            {"name": "Alice", "budget": 100, "user": "alice@test",
             "squad": [{"name": "Mbappe", "role": "FWD", "team": "France", "buy_price": 40}],
             "pin": "1111"},
            {"name": "Bob", "budget": 80, "squad": [], "user": "bob@test", "pin": "2222"},
            {"name": "Charlie", "budget": 60, "squad": [], "user": "charlie@test", "pin": "3333"},
        ],
        "active_bids": [
            {"player": "Haaland", "participant": "Alice", "amount": 30},
            {"player": "Vini Jr", "participant": "Bob", "amount": 20},
        ],
        "open_bids": {
            "Bellingham": {"high_bid": 25, "high_bidder": "Alice", "role": "MID", "team": "England"},
        },
        "pending_trades": [
            {"id": "t1", "from": "Alice", "to": "Bob", "give_players": ["Mbappe"],
             "get_players": [], "give_cash": 0, "get_cash": 10, "status": "pending"},
            {"id": "t2", "from": "Charlie", "to": "Alice", "give_players": [],
             "get_players": [], "give_cash": 5, "get_cash": 0, "status": "pending"},
        ],
        "transactions": [
            {"type": "market_buy", "participant": "Alice", "player": "Mbappe", "amount": 40},
        ],
        "auction_log": [
            {"buyer": "Alice", "player": "Mbappe", "amount": 40},
        ],
        "gameweek_squads": {
            "1": {"Alice": {"squad": [{"name": "Mbappe"}], "ir": None},
                  "Bob": {"squad": [], "ir": None}},
        },
        "gameweek_scores": {
            "1": {"Alice": 50, "Bob": 30},
        },
        "active_loans": [
            {"id": "l1", "from": "Alice", "to": "Bob", "player": "Mbappe",
             "return_gameweek": "3", "entry": {"name": "Mbappe"}},
        ],
    }


# --- Basic rename ---

def test_rename_basic():
    room = _room()
    rename_team(room, "Alice", "Zidane FC")
    names = {p["name"] for p in room["participants"]}
    assert "Alice" not in names
    assert "Zidane FC" in names


def test_rename_preserves_non_name_fields():
    room = _room()
    rename_team(room, "Alice", "Zidane FC")
    p = next(p for p in room["participants"] if p["name"] == "Zidane FC")
    assert p["budget"] == 100
    assert p["pin"] == "1111"
    assert p["user"] == "alice@test"
    assert any(e["name"] == "Mbappe" for e in p["squad"])


# --- Duplicate / validation ---

def test_rename_rejects_empty():
    with pytest.raises(AdminError, match="empty"):
        rename_team(_room(), "Alice", "   ")


def test_rename_rejects_duplicate_other_team():
    with pytest.raises(AdminError, match="already exists"):
        rename_team(_room(), "Alice", "Bob")


def test_rename_rejects_duplicate_other_team_case_insensitive():
    with pytest.raises(AdminError, match="already exists"):
        rename_team(_room(), "Alice", "bob")


def test_rename_allows_case_change_of_own_name():
    """The fix: renaming 'Alice' -> 'ALICE' should succeed (only a case change)."""
    room = _room()
    rename_team(room, "Alice", "ALICE")
    names = [p["name"] for p in room["participants"]]
    assert "ALICE" in names
    assert "Alice" not in names


def test_rename_unknown_team():
    with pytest.raises(AdminError, match="not found"):
        rename_team(_room(), "Nobody", "NewName")


# --- Repeated renames (the reported bug) ---

def test_rename_twice():
    """Core regression test: rename once, then rename again with a new name."""
    room = _room()
    rename_team(room, "Alice", "SuperTeam")
    # Second rename
    rename_team(room, "SuperTeam", "MegaTeam")
    names = {p["name"] for p in room["participants"]}
    assert "MegaTeam" in names
    assert "SuperTeam" not in names
    assert "Alice" not in names


def test_rename_three_times():
    room = _room()
    rename_team(room, "Alice", "Name1")
    rename_team(room, "Name1", "Name2")
    rename_team(room, "Name2", "Name3")
    names = {p["name"] for p in room["participants"]}
    assert names == {"Name3", "Bob", "Charlie"}


# --- Propagation: active_bids ---

def test_rename_propagates_active_bids():
    room = _room()
    rename_team(room, "Alice", "New")
    alice_bids = [b for b in room["active_bids"] if b["participant"] == "New"]
    assert len(alice_bids) == 1
    assert alice_bids[0]["player"] == "Haaland"
    # Bob's bid unchanged
    bob_bids = [b for b in room["active_bids"] if b["participant"] == "Bob"]
    assert len(bob_bids) == 1


def test_rename_propagates_active_bids_after_second_rename():
    room = _room()
    rename_team(room, "Alice", "Mid")
    rename_team(room, "Mid", "Final")
    alice_bids = [b for b in room["active_bids"] if b["participant"] == "Final"]
    assert len(alice_bids) == 1
    assert not any(b["participant"] == "Mid" for b in room["active_bids"])


# --- Propagation: open_bids ---

def test_rename_propagates_open_bids():
    room = _room()
    rename_team(room, "Alice", "New")
    assert room["open_bids"]["Bellingham"]["high_bidder"] == "New"


# --- Propagation: pending_trades ---

def test_rename_propagates_trades_from():
    room = _room()
    rename_team(room, "Alice", "New")
    t1 = next(t for t in room["pending_trades"] if t["id"] == "t1")
    assert t1["from"] == "New"
    assert t1["to"] == "Bob"  # unchanged


def test_rename_propagates_trades_to():
    room = _room()
    rename_team(room, "Alice", "New")
    t2 = next(t for t in room["pending_trades"] if t["id"] == "t2")
    assert t2["to"] == "New"
    assert t2["from"] == "Charlie"  # unchanged


def test_rename_propagates_trades_after_second_rename():
    room = _room()
    rename_team(room, "Alice", "Mid")
    rename_team(room, "Mid", "Final")
    t1 = next(t for t in room["pending_trades"] if t["id"] == "t1")
    assert t1["from"] == "Final"
    t2 = next(t for t in room["pending_trades"] if t["id"] == "t2")
    assert t2["to"] == "Final"


# --- Propagation: transactions ---

def test_rename_propagates_transactions():
    room = _room()
    rename_team(room, "Alice", "New")
    assert room["transactions"][0]["participant"] == "New"


# --- Propagation: auction_log ---

def test_rename_propagates_auction_log():
    room = _room()
    rename_team(room, "Alice", "New")
    assert room["auction_log"][0]["buyer"] == "New"


# --- Propagation: gameweek_squads ---

def test_rename_propagates_gameweek_squads():
    room = _room()
    rename_team(room, "Alice", "New")
    gw1 = room["gameweek_squads"]["1"]
    assert "New" in gw1
    assert "Alice" not in gw1
    assert "Bob" in gw1  # unchanged


# --- Propagation: gameweek_scores ---

def test_rename_propagates_gameweek_scores():
    room = _room()
    rename_team(room, "Alice", "New")
    scores = room["gameweek_scores"]["1"]
    assert scores["New"] == 50
    assert "Alice" not in scores


# --- Propagation: active_loans ---

def test_rename_propagates_loans_from():
    room = _room()
    rename_team(room, "Alice", "New")
    loan = room["active_loans"][0]
    assert loan["from"] == "New"
    assert loan["to"] == "Bob"  # unchanged


def test_rename_propagates_loans_to():
    room = _room()
    rename_team(room, "Bob", "NewBob")
    loan = room["active_loans"][0]
    assert loan["to"] == "NewBob"
    assert loan["from"] == "Alice"  # unchanged


# --- Edge cases ---

def test_rename_strips_whitespace():
    room = _room()
    rename_team(room, "Alice", "  New  ")
    names = {p["name"] for p in room["participants"]}
    assert "New" in names


def test_rename_with_no_optional_fields():
    """Minimal room with only participants — no bids, trades, etc."""
    room = {"participants": [{"name": "A", "budget": 100, "squad": []}]}
    rename_team(room, "A", "B")
    assert room["participants"][0]["name"] == "B"


def test_rename_does_not_affect_other_teams():
    room = _room()
    bob_before = dict(next(p for p in room["participants"] if p["name"] == "Bob"))
    rename_team(room, "Alice", "New")
    bob_after = next(p for p in room["participants"] if p["name"] == "Bob")
    assert bob_after["budget"] == bob_before["budget"]
    assert bob_after["pin"] == bob_before["pin"]
