import asyncio
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import api_server as api


def _player(name, price=1):
    return {"name": name, "buy_price": price, "role": "Batsman", "team": "RCB"}


def _room(deadline):
    return {
        "admin": "Admin",
        "tournament_type": "ipl",
        "game_phase": "Bidding",
        "current_gameweek": 1,
        "bidding_deadline": deadline.isoformat(),
        "squads_locked": False,
        "active_bids": [
            {
                "player": "Virat Kohli",
                "amount": 10,
                "bidder": "Alice",
                "expires": (deadline + timedelta(hours=24)).isoformat(),
            },
            {
                "player": "Unaffordable Player",
                "amount": 999,
                "bidder": "Bob",
                "expires": (deadline + timedelta(hours=24)).isoformat(),
            },
        ],
        "pending_trades": [
            {
                "id": "admin-trade",
                "from": "Alice",
                "to": "Bob",
                "type": "Transfer (Sell)",
                "player": "Player 1",
                "price": 5,
                "status": "pending_admin",
            },
            {
                "id": "open-trade",
                "from": "Bob",
                "to": "Alice",
                "type": "Transfer (Buy)",
                "player": "Player 2",
                "price": 5,
                "status": "pending",
            },
        ],
        "participants": [
            {"name": "Alice", "budget": 100, "squad": [_player("Player 1")], "eliminated": False},
            {"name": "Bob", "budget": 5, "squad": [_player("Player 2")], "eliminated": False},
        ],
    }


def test_deadline_rollover_waits_until_45_minutes():
    deadline = datetime(2026, 5, 1, 12, 0, tzinfo=api.IST)
    room = _room(deadline)

    changed = api._run_deadline_rollover_for_room("ROOM1", room, deadline + timedelta(minutes=44))

    assert changed is False
    assert room["current_gameweek"] == 1
    assert len(room["active_bids"]) == 2
    assert len(room["pending_trades"]) == 2
    assert "1" not in room.get("gameweek_squads", {})


def test_deadline_rollover_settles_rejects_locks_advances_and_is_idempotent():
    deadline = datetime(2026, 5, 1, 12, 0, tzinfo=api.IST)
    room = _room(deadline)

    changed = api._run_deadline_rollover_for_room("ROOM1", room, deadline + timedelta(minutes=45))

    assert changed is True
    assert room["current_gameweek"] == 2
    assert room["bidding_deadline"] is None
    assert room["squads_locked"] is False
    assert room["game_phase"] == "Awaiting Deadline"
    assert room["active_bids"] == []
    assert room["pending_trades"] == []
    assert "1" in room["gameweek_squads"]
    assert any(p["name"] == "Virat Kohli" for p in room["participants"][0]["squad"])
    assert room["participants"][0]["budget"] == 90
    assert not any(p["name"] == "Unaffordable Player" for p in room["participants"][1]["squad"])
    assert room["automation"]["deadline_rollovers"]["1"]["status"] == "completed"

    changed_again = api._run_deadline_rollover_for_room("ROOM1", room, deadline + timedelta(minutes=46))

    assert changed_again is False
    assert room["current_gameweek"] == 2
    assert room["participants"][0]["budget"] == 90
    assert sum(p["name"] == "Virat Kohli" for p in room["participants"][0]["squad"]) == 1


def test_lock_squads_does_not_double_charge_ir():
    room = {
        "participants": [
            {
                "name": "Alice",
                "budget": 20,
                "injury_reserve": "Player 0",
                "squad": [_player(f"Player {idx}", idx + 1) for idx in range(19)],
            }
        ],
        "current_gameweek": 1,
    }

    first = api._lock_squads_for_gameweek(room, 1)
    second = api._lock_squads_for_gameweek(room, 1)

    assert first["already_locked"] is False
    assert second["already_locked"] is True
    assert room["participants"][0]["budget"] == 18
    assert room["gameweek_squads"]["1"]["Alice"]["injury_reserve"] == "Player 0"


def test_ipl_scoring_waits_for_complete_match_and_does_not_double_count():
    schedule = {
        "gameweeks": {
            "1": {
                "matches": [
                    {
                        "match_id": 1,
                        "teams": ["RCB", "SRH"],
                        "date": "2026-03-28",
                        "time": "19:30",
                    }
                ]
            }
        }
    }
    room = {
        "tournament_type": "ipl",
        "gameweek_squads": {"1": {"Alice": {"squad": [_player("Virat Kohli")]}}},
        "gameweek_scores": {},
        "participants": [{"name": "Alice", "squad": [_player("Virat Kohli")]}],
    }

    with patch.object(api, "_load_ipl_schedule", return_value=schedule), \
            patch.object(api, "_fetch_cricbuzz_scorecard_candidates", return_value=[]), \
            patch.object(api, "_discover_cricbuzz_scorecard_url", side_effect=lambda match, candidates=None: {
                "url": "https://www.cricbuzz.com/live-cricket-scorecard/149618/srh-vs-rcb-1st-match-ipl-2026",
                "confidence": 95,
            }), \
            patch.object(api, "_fetch_cricbuzz_match_status", return_value={
                "url": "https://www.cricbuzz.com/live-cricket-scorecard/149618/srh-vs-rcb-1st-match-ipl-2026",
                "completed": True,
                "no_result": False,
                "result_text": "Royal Challengers Bengaluru won by 6 wickets",
            }), \
            patch.object(api.scraper, "fetch_match_data", return_value=[{"name": "Virat Kohli"}]), \
            patch.object(api.calculator, "calculate_score", return_value=42):
        changed = api._run_ipl_scoring_for_room("ROOM1", room, datetime(2026, 3, 29, tzinfo=api.IST))
        api._run_ipl_scoring_for_room("ROOM1", room, datetime(2026, 3, 29, 0, 1, tzinfo=api.IST))

    assert changed is True
    assert room["gameweek_match_scores"]["1"]["1"]["scores"] == {"Virat Kohli": 42}
    assert room["gameweek_scores"]["1"] == {"Virat Kohli": 42}
    assert room["automation"]["ipl_scoring"]["matches"]["1"]["status"] == "processed"


def test_ipl_scoring_skips_incomplete_match():
    schedule = {
        "gameweeks": {
            "1": {
                "matches": [
                    {"match_id": 1, "teams": ["RCB", "SRH"], "date": "2026-03-28", "time": "19:30"}
                ]
            }
        }
    }
    room = {
        "tournament_type": "ipl",
        "gameweek_squads": {"1": {"Alice": {"squad": []}}},
        "gameweek_scores": {},
    }

    with patch.object(api, "_load_ipl_schedule", return_value=schedule), \
            patch.object(api, "_fetch_cricbuzz_scorecard_candidates", return_value=[]), \
            patch.object(api, "_discover_cricbuzz_scorecard_url", side_effect=lambda match, candidates=None: {
                "url": "https://www.cricbuzz.com/live-cricket-scorecard/149618/test",
                "confidence": 95,
            }), \
            patch.object(api, "_fetch_cricbuzz_match_status", return_value={
                "url": "https://www.cricbuzz.com/live-cricket-scorecard/149618/test",
                "completed": False,
                "no_result": False,
                "result_text": "",
            }):
        changed = api._run_ipl_scoring_for_room("ROOM1", room, datetime(2026, 3, 28, tzinfo=api.IST))

    assert changed is True
    assert room["gameweek_scores"] == {}
    assert room["automation"]["ipl_scoring"]["gameweeks"]["1"]["status"] == "incomplete"


def test_automation_status_and_match_url_endpoints():
    data = {
        "rooms": {
            "ROOM1": {
                "admin": "Admin",
                "tournament_type": "ipl",
                "automation": {},
            }
        }
    }

    with patch.object(api, "_firebase_get", side_effect=lambda path="": data), \
            patch.object(api, "_firebase_put", side_effect=lambda updated, path="": None), \
            patch.object(api, "_find_schedule_match", side_effect=lambda match_id, gameweek=None: ("1", {"match_id": match_id, "teams": ["RCB", "SRH"]})):
        response = asyncio.run(
            api.set_match_url(
                api.MatchUrlOverrideRequest(
                    room_code="ROOM1",
                    admin_name="Admin",
                    match_id=1,
                    cricbuzz_url="https://www.cricbuzz.com/live-cricket-scorecard/149618/srh-vs-rcb-1st-match-ipl-2026",
                )
            )
        )
        assert response["match_id"] == 1

        payload = asyncio.run(api.automation_status(room_code="ROOM1"))
    assert payload["automation"]["ipl_scoring"]["matches"]["1"]["source"] == "admin_override"


class AdminAutomationTests(unittest.TestCase):
    pass


def _wrap_test(fn):
    def _test(self):
        fn()
    return _test


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn):
        setattr(AdminAutomationTests, _name, _wrap_test(_fn))


if __name__ == "__main__":
    unittest.main()
