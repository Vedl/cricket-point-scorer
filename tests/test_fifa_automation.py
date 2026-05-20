import asyncio
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch, mock_open
import pandas as pd
import json
from pathlib import Path

import api_server as api

def _player(name, role="Midfielder", country="France"):
    return {"name": name, "role": role, "country": country}

def _room():
    return {
        "admin": "Admin",
        "tournament_type": "FIFA World Cup 2026",
        "game_phase": "Bidding",
        "current_gameweek": 1,
        "participants": [
            {"name": "Alice", "budget": 100, "squad": [_player("Kylian Mbappé", "Forward")], "eliminated": False},
            {"name": "Bob", "budget": 100, "squad": [_player("Kevin De Bruyne", "Midfielder")], "eliminated": False},
        ],
        "gameweek_squads": {
            "1": {
                "Alice": {"squad": [_player("Kylian Mbappé", "Forward")]},
                "Bob": {"squad": [_player("Kevin De Bruyne", "Midfielder")]}
            }
        },
        "gameweek_scores": {}
    }

def test_parse_fifa_match_datetime():
    # Test valid UTC offset
    dt = api._parse_fifa_match_datetime("2026-06-11", "13:00 UTC-6")
    assert dt is not None
    assert dt.hour == 13
    assert dt.minute == 0
    assert dt.tzinfo.utcoffset(dt) == timedelta(hours=-6)

    # Test clean ISO fallback
    dt = api._parse_fifa_match_datetime("2026-06-11T20:00:00", "20:00 UTC")
    assert dt is not None
    assert dt.tzinfo == timezone.utc

def test_find_fifa_schedule_match():
    schedule = {
        "gameweeks": {
            "1": {
                "matches": [
                    {"match_id": 42, "teams": ["France", "Italy"], "date": "2026-06-11", "time": "20:00 UTC"}
                ]
            }
        }
    }
    with patch.object(api, "_load_fifa_schedule", return_value=schedule):
        gw, match = api._find_fifa_schedule_match(42)
        assert gw == "1"
        assert match["teams"] == ["France", "Italy"]

def test_update_football_player_db():
    df = pd.DataFrame([
        {"Player": "New Guy", "Team": "Germany", "Position": "MID"}
    ])
    
    # We mock out Path.exists and writing/reading JSON
    mock_data = json.dumps([{"name": "Old Guy", "role": "Defender", "country": "Spain"}])
    
    with patch("builtins.open", mock_open(read_data=mock_data)) as mocked_file, \
         patch("pathlib.Path.exists", return_value=True):
        api._update_football_player_db(df)
        mocked_file.assert_called()

def test_fifa_scoring_24h_delay():
    schedule = {
        "gameweeks": {
            "1": {
                "matches": [
                    {"match_id": 1, "teams": ["Mexico", "South Africa"], "date": "2026-06-11", "time": "13:00 UTC-6"}
                ]
            }
        }
    }
    room = _room()
    
    # Run scoring when 'now' is less than 24 hours after kickoff
    kickoff = datetime(2026, 6, 11, 13, 0, tzinfo=timezone(timedelta(hours=-6)))
    now = kickoff + timedelta(hours=23) # 23 hours later (before 24h limit)
    
    with patch.object(api, "_load_fifa_schedule", return_value=schedule):
        changed = api._run_fifa_scoring_for_room("ROOM1", room, now)
        
    assert changed is False
    assert room["automation"]["fifa_scoring"]["gameweeks"]["1"]["status"] == "waiting_24h"

def test_fifa_scoring_success():
    schedule = {
        "gameweeks": {
            "1": {
                "matches": [
                    {"match_id": 1, "teams": ["Mexico", "South Africa"], "date": "2026-06-11", "time": "13:00 UTC-6"}
                ]
            }
        }
    }
    room = _room()
    
    kickoff = datetime(2026, 6, 11, 13, 0, tzinfo=timezone(timedelta(hours=-6)))
    now = kickoff + timedelta(hours=25) # 25 hours later
    
    df_result = pd.DataFrame([
        {"Player": "Kylian Mbappé", "Team": "France", "Position": "FWD", "Score": 12.0, "minutes_played": 90},
        {"Player": "Kevin De Bruyne", "Team": "Belgium", "Position": "MID", "Score": 8.0, "minutes_played": 90}
    ])
    
    with patch.object(api, "_load_fifa_schedule", return_value=schedule), \
         patch.object(api, "_search_whoscored_match_url", return_value="https://www.whoscored.com/Matches/1234/Live"), \
         patch("football_score_calculator.calc_all_players_whoscored", return_value=df_result), \
         patch.object(api, "_update_football_player_db", return_value=None):
        changed = api._run_fifa_scoring_for_room("ROOM1", room, now)
        
    assert changed is True
    assert room["gameweek_scores"]["1"]["Kylian Mbappé"] == 12
    assert room["gameweek_scores"]["1"]["Kevin De Bruyne"] == 8
    assert room["automation"]["fifa_scoring"]["gameweeks"]["1"]["status"] == "processed"

def test_fifa_standings_dual_position():
    room = _room()
    room["gameweek_scores"] = {
        "1": {
            "Kylian Mbappé": {"FWD": 15, "MID": 5},
            "Kevin De Bruyne": 10
        }
    }
    
    # Standings mock GET
    with patch.object(api, "_firebase_get", return_value={"rooms": {"ROOM1": room}}):
        response = asyncio.run(api.get_standings(room_code="ROOM1", gameweek=1))
        
    standings = response["standings"]
    # Alice should get 15 points (Mbappe's highest-scoring position FWD)
    # Bob should get 10 points (Kevin De Bruyne)
    alice_entry = next(s for s in standings if s["participant"] == "Alice")
    bob_entry = next(s for s in standings if s["participant"] == "Bob")
    
    assert alice_entry["points"] == 15
    assert bob_entry["points"] == 10

class FifaAutomationTests(unittest.TestCase):
    pass

def _wrap_test(fn):
    def _test(self):
        fn()
    return _test

for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn):
        setattr(FifaAutomationTests, _name, _wrap_test(_fn))

if __name__ == "__main__":
    unittest.main()
