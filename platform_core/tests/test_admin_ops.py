import json

import pytest

from platform_core import admin_ops as ao


def _room():
    return {
        "tournament_type": "IPL 2026",
        "participants": [
            {"name": "A", "budget": 100, "squad": [
                {"name": "Kohli", "role": "Batsman", "team": "RCB", "buy_price": 40}], "pin": "1"},
            {"name": "B", "budget": 100, "squad": [], "pin": "2"},
        ],
        "gameweek_scores": {"1": {"Kohli": 50}},
    }


def test_force_add_and_release():
    room = _room()
    ao.force_add_player(room, "B", "Bumrah", "Bowler", "MI", price=20)
    by = {p["name"]: p for p in room["participants"]}
    assert by["B"]["budget"] == 80
    assert any(e["name"] == "Bumrah" for e in by["B"]["squad"])
    ao.force_release(room, "B", "Bumrah", refund=True)
    assert by["B"]["budget"] == 100
    assert by["B"]["squad"] == []


def test_force_add_duplicate_rejected():
    room = _room()
    with pytest.raises(ao.AdminError):
        ao.force_add_player(room, "A", "Kohli", "Batsman", "RCB")


def test_adjust_budget_and_reset_pin():
    room = _room()
    ao.adjust_budget(room, "A", 50)
    assert room["participants"][0]["budget"] == 150
    ao.reset_pin(room, "A", "9999")
    assert room["participants"][0]["pin"] == "9999"


def test_loan_and_reverse():
    room = _room()
    lid = ao.loan_player(room, "A", "B", "Kohli", return_gameweek="3")
    by = {p["name"]: p for p in room["participants"]}
    assert any(e["name"] == "Kohli" for e in by["B"]["squad"])
    assert all(e["name"] != "Kohli" for e in by["A"]["squad"])
    assert room["active_loans"][0]["return_gameweek"] == "3"
    ao.reverse_loan(room, lid)
    assert any(e["name"] == "Kohli" for e in by["A"]["squad"])
    assert room["active_loans"] == []


def test_reset_room_keeps_teams_clears_progress():
    room = _room()
    ao.reset_room(room)
    by = {p["name"]: p for p in room["participants"]}
    assert by["A"]["squad"] == [] and by["A"]["budget"] == 100
    assert by["A"]["pin"] == "1"            # PIN preserved
    assert room["gameweek_scores"] == {}
    assert room["current_gameweek"] == 0


def test_export_import_roundtrip():
    room = _room()
    text = ao.export_room(room)
    doc = {"rooms": {}}
    ao.import_room(doc, "XYZ", text)
    assert doc["rooms"]["XYZ"]["participants"][0]["name"] == "A"


def test_import_rejects_garbage():
    with pytest.raises(ao.AdminError):
        ao.import_room({"rooms": {}}, "X", "{not json")
    with pytest.raises(ao.AdminError):
        ao.import_room({"rooms": {}}, "X", json.dumps({"foo": 1}))


def test_delete_room():
    doc = {"rooms": {"ABC": {"participants": []}},
           "users": {"u": {"rooms_created": ["ABC"], "rooms_joined": []}}}
    ao.delete_room(doc, "ABC")
    assert "ABC" not in doc["rooms"]
    assert doc["users"]["u"]["rooms_created"] == []
