import time
from fantasy_auction.state import repo
from datetime import datetime, timedelta

doc = repo.load()
room = doc.get("rooms", {}).get("4MYGF1")

transactions = room.get("transactions", [])
new_transactions = []
open_bids = room.setdefault("open_bids", {})

participants = {p["name"]: p for p in room.get("participants", [])}

count = 0
for t in transactions:
    if t.get("type") == "market_buy":
        player = t["player"]
        participant = t["participant"]
        amount = t["amount"]
        
        p = participants.get(participant)
        if p:
            # Remove from squad
            squad = p.get("squad", [])
            squad_entry = next((e for e in squad if e["name"] == player), None)
            if squad_entry:
                squad.remove(squad_entry)
            
            # Refund budget
            p["budget"] = p.get("budget", 0) + amount
            
            # Add back to open_bids
            open_bids[player] = {
                "high_bid": amount,
                "high_bidder": participant,
                "team": squad_entry.get("team", "") if squad_entry else "",
                "role": squad_entry.get("role", "") if squad_entry else "",
                "expires": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            count += 1
            print(f"Reversed {player} for {participant}")
            continue
    new_transactions.append(t)

room["transactions"] = new_transactions
repo.save(doc)
print(f"Reversed {count} accidental awards. Waiting for flush...")
time.sleep(8)
