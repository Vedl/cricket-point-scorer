from fantasy_auction.state import repo
doc = repo.load()
room = doc.get("rooms", {}).get("4MYGF1")
print([p["name"] for p in room.get("participants", [])])
