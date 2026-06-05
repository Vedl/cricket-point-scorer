import time
from fantasy_auction.state import repo
from platform_core.config_layer import load_player_pool

doc = repo.load()
room = doc.get("rooms", {}).get("4MYGF1")
by = {p["name"]: p for p in room.get("participants", [])}

pool = load_player_pool(room.get("tournament_type", "T20 World Cup"))
p_map = {p.name.lower(): p for p in pool}

squad = by["Naman"]["squad"]
changed = False
for e in squad:
    if "neves" in e["name"].lower():
        e["buy_price"] = 33
        p_info = p_map.get(e["name"].lower())
        if p_info:
            e["role"] = p_info.role
            e["team"] = p_info.team
        print("Updated", e)
        changed = True

if changed:
    repo.save(doc)
    time.sleep(5)
