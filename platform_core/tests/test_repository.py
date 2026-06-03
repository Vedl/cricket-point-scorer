import pytest

from auction_engine import AuctionEngine
from platform_core.csv_import import parse_squad_csv
from platform_core.firebase_store import FirebaseStore
from platform_core.repository import (
    Repository,
    RepositoryError,
    apply_pool_import,
    apply_roster_import,
    engine_from_room,
    participant_from_room,
    participant_to_room,
    save_engine_to_room,
)


@pytest.fixture
def repo(tmp_path):
    store = FirebaseStore(local_file_path=str(tmp_path / "data.json"), database_url="")
    return Repository(store)


def test_create_room_and_admin_participates(repo):
    doc = {"users": {"alice": {}}, "rooms": {}}
    code = repo.create_room(doc, "alice", "My League", "IPL 2026", admin_participating=True)
    assert code in doc["rooms"]
    room = doc["rooms"][code]
    assert room["admin"] == "alice"
    assert room["tournament_type"] == "IPL 2026"
    assert [p["name"] for p in room["participants"]] == ["alice"]
    assert code in doc["users"]["alice"]["rooms_created"]


def test_create_room_admin_only(repo):
    doc = {"users": {"alice": {}}, "rooms": {}}
    code = repo.create_room(doc, "alice", "Admin Only", "T20 World Cup", admin_participating=False)
    assert doc["rooms"][code]["participants"] == []


def test_add_team_and_claim_with_pin(repo):
    doc = {"users": {"alice": {}, "bob": {}}, "rooms": {}}
    code = repo.create_room(doc, "alice", "L", "IPL 2026", admin_participating=False)
    room = doc["rooms"][code]
    repo.add_team(room, "Bob's XI", pin="4321")

    with pytest.raises(RepositoryError, match="Incorrect PIN"):
        repo.claim_team(doc, code, "bob", "Bob's XI", "0000")

    part = repo.claim_team(doc, code, "bob", "Bob's XI", "4321")
    assert part["user"] == "bob"
    assert "bob" in room["members"]
    assert code in doc["users"]["bob"]["rooms_joined"]


def test_claim_team_already_claimed(repo):
    doc = {"users": {}, "rooms": {}}
    code = repo.create_room(doc, "alice", "L", "IPL 2026", admin_participating=False)
    room = doc["rooms"][code]
    repo.add_team(room, "Team A", pin="11")
    repo.claim_team(doc, code, "bob", "Team A", "11")
    with pytest.raises(RepositoryError, match="already been claimed"):
        repo.claim_team(doc, code, "carol", "Team A", "11")


def test_participant_round_trip():
    room_p = {
        "name": "Alice",
        "budget": 80,
        "squad": [{"name": "Virat Kohli", "role": "Batsman", "team": "RCB", "buy_price": 20}],
        "user": "alice",
        "pin": "99",
    }
    p = participant_from_room(room_p)
    assert p.budget == 80 and p.squad[0].price_paid == 20
    back = participant_to_room(p, user="alice", pin="99")
    assert back["squad"][0]["buy_price"] == 20
    assert back["name"] == "Alice"


def test_pool_import_and_engine_uses_it(repo, tmp_path):
    doc = {"users": {}, "rooms": {}}
    code = repo.create_room(doc, "alice", "WC", "FIFA World Cup 2026", admin_participating=False)
    room = doc["rooms"][code]
    text = "Player,Role,Team\nMessi,FWD,Argentina\nNeuer,GK,Germany\n"
    added = apply_pool_import(room, parse_squad_csv(text))
    assert added == 2
    eng = engine_from_room(room, data_dir=str(tmp_path))
    assert len(eng.players) == 2
    assert any(p.name == "Messi" for p in eng.players.values())


def test_pool_import_extend_dedupes(repo):
    room = {"tournament_type": "FIFA World Cup 2026", "player_pool": []}
    apply_pool_import(room, parse_squad_csv("Player\nMessi\n"))
    added = apply_pool_import(room, parse_squad_csv("Player\nMessi\nRonaldo\n"), extend=True)
    assert added == 1  # Messi already present
    assert len(room["player_pool"]) == 2


def test_roster_import_assigns_and_deducts_budget():
    room = {"tournament_type": "T20 World Cup", "participants": []}
    text = "Participant,Player,Role,Team,Price\nAlice,Buttler,WK-Batsman,England,60\n"
    apply_roster_import(room, parse_squad_csv(text), budget=100)
    part = room["participants"][0]
    assert part["name"] == "Alice"
    assert part["budget"] == 40
    assert part["squad"][0]["buy_price"] == 60


def test_engine_save_round_trip_through_room(tmp_path):
    room = {
        "tournament_type": "FIFA World Cup 2026",
        "player_pool": [
            {"name": "Messi", "role": "FWD", "team": "Argentina", "base_price": 0},
            {"name": "Neuer", "role": "GK", "team": "Germany", "base_price": 0},
        ],
        "participants": [
            {"name": "Alice", "budget": 100, "squad": [], "user": "alice", "pin": "1"},
            {"name": "Bob", "budget": 100, "squad": [], "user": "bob", "pin": "2"},
        ],
    }
    eng = engine_from_room(room, data_dir=str(tmp_path))
    eng.start_team_auction("Argentina", now=1000.0)
    eng.place_bid("Alice", 10, now=1001.0)
    eng.resolve(now=1001.0 + 999)  # sell Messi to Alice
    save_engine_to_room(eng, room)

    # Round-trip: rebuild and verify persisted state.
    eng2 = engine_from_room(room, data_dir=str(tmp_path))
    alice = eng2.participants["Alice"]
    assert alice.budget == 90
    assert alice.squad[0].name == "Messi"
    # user/pin preserved through the save
    assert next(p for p in room["participants"] if p["name"] == "Alice")["pin"] == "1"
