#!/usr/bin/env python3
"""
YMMO07 Room Data Restoration Script
Restores correct squad data from Gameweek 1 Auction Squads.csv
"""

import json
import csv
from datetime import datetime, timezone

# Configuration
CSV_FILE = "Gameweek 1 Auction Squads.csv"
DATA_FILE = "auction_data.json"
ROOM_CODE = "YMMO07"

# Pre-lock budgets (before IR deduction)
PRE_LOCK_BUDGETS = {
    "Arrow": 19,
    "Falcon": 77,
    "Johnthedon69": 73,
    "Ladda CC": 23,
    "Mithuphetamine": 54,
    "Smudge49": 60,
    "Suvaan": 9
}

# Injury Reserves
INJURY_RESERVES = {
    "Smudge49": "Glenn Maxwell",
    "Mithuphetamine": "Sanjay Krishnamurthi",
    "Suvaan": "Tim David",
    "Arrow": "Pathum Nissanka",
    "Falcon": "Quinton de Kock"
}

# User mappings (participant name -> user account)
USER_MAPPINGS = {
    "Arrow": "Arrow",
    "Falcon": "Falcon ",  # Note: trailing space in original
    "Johnthedon69": "Johnthedon69",
    "Ladda CC": "Ladda CC",
    "Mithuphetamine": "Mithuphetamine",
    "Smudge49": None,  # Admin-managed
    "Suvaan": "Suvaan"
}

def main():
    # Load existing data
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    # Parse CSV to build squads
    squads = {}  # participant -> list of players
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = row['Participant'].strip()
            if not participant:
                continue
            
            if participant not in squads:
                squads[participant] = []
            
            squads[participant].append({
                "name": row['Player'].strip(),
                "role": row['Role'].strip(),
                "team": row['Team'].strip(),
                "buy_price": int(row['Price']),
                "active": True
            })
    
    print("Squads parsed from CSV:")
    for p, s in squads.items():
        print(f"  {p}: {len(s)} players")
    
    # Build participants array
    participants = []
    for participant_name in squads.keys():
        squad = squads[participant_name]
        ir_player = INJURY_RESERVES.get(participant_name)
        pre_lock_budget = PRE_LOCK_BUDGETS.get(participant_name, 0)
        
        # Calculate final budget: pre_lock - IR_fee(2) + boost(100)
        ir_fee = 2 if ir_player else 0
        final_budget = pre_lock_budget - ir_fee + 100
        
        user = USER_MAPPINGS.get(participant_name)
        
        participant_obj = {
            "name": participant_name,
            "squad": squad,
            "budget": final_budget,
            "injury_reserve": ir_player
        }
        if user:
            participant_obj["user"] = user
        
        participants.append(participant_obj)
        print(f"  {participant_name}: {len(squad)} players, Budget: {final_budget}M, IR: {ir_player}")
    
    # Build GW1 snapshot (pre-boost, post-IR)
    gw1_snapshot = {}
    for participant_name in squads.keys():
        squad = squads[participant_name]
        ir_player = INJURY_RESERVES.get(participant_name)
        pre_lock_budget = PRE_LOCK_BUDGETS.get(participant_name, 0)
        ir_fee = 2 if ir_player else 0
        budget_after_ir = pre_lock_budget - ir_fee
        
        gw1_snapshot[participant_name] = {
            "squad": [{"name": p["name"], "buy_price": p["buy_price"]} for p in squad],
            "injury_reserve": ir_player,
            "budget": budget_after_ir
        }
    
    # Update room
    room = data["rooms"][ROOM_CODE]
    room["participants"] = participants
    room["gameweek_squads"] = {"1": gw1_snapshot}
    room["current_gameweek"] = 2
    room["squads_locked"] = False
    room["big_auction_complete"] = True
    room["bidding_open"] = True
    room["trading_open"] = True
    room["active_bids"] = []
    room["pending_trades"] = []
    room["game_phase"] = "Trading"
    
    # Add Smudge49 to members if not present
    if "Smudge49" not in room["members"] and "smudge4955" not in room["members"]:
        room["members"].append("Smudge49")
        print("Added Smudge49 to room members")
    
    # Save
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Room {ROOM_CODE} restored successfully!")
    print(f"   - {len(participants)} participants")
    print(f"   - Gameweek: 2")
    print(f"   - GW1 snapshot created")

if __name__ == "__main__":
    main()
