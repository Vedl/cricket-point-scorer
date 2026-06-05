from fantasy_auction.state import repo
doc = repo.load()
room = doc.get("rooms", {}).get("4MYGF1")
print(f"Room has {len(room.get('open_bids', {}))} open bids.")
for k, v in room.get("open_bids", {}).items():
    print(k, v)
