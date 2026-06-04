"""Egress-control behaviour of FirebaseStore (local mode: no remote calls)."""

import tempfile

from platform_core.firebase_store import FirebaseStore


def _store():
    return FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"))


def test_load_room_returns_single_room_and_is_coherent_with_save():
    s = _store()
    s.save({"users": {}, "rooms": {
        "AB": {"name": "Alpha", "participants": []},
        "CD": {"name": "Beta", "participants": []}}})
    assert s.load_room("AB")["name"] == "Alpha"
    assert s.load_room("cd")["name"] == "Beta"          # case-insensitive
    assert s.load_room("ZZ") is None                    # unknown room


def test_save_updates_both_full_and_room_caches():
    s = _store()
    s.save({"users": {}, "rooms": {"AB": {"name": "v1"}}})
    assert s.load_room("AB")["name"] == "v1"
    doc = s.load()
    doc["rooms"]["AB"]["name"] = "v2"
    s.save(doc)
    assert s.load_room("AB")["name"] == "v2"            # per-room cache refreshed
    assert s.load()["rooms"]["AB"]["name"] == "v2"


def test_room_read_does_not_mutate_cache():
    s = _store()
    s.save({"users": {}, "rooms": {"AB": {"name": "v1", "participants": []}}})
    r = s.load_room("AB")
    r["participants"].append({"name": "hacker"})        # mutate the returned copy
    assert s.load_room("AB")["participants"] == []      # cache untouched


def test_default_cache_ttl_is_long_enough_to_cut_egress():
    # The whole point of the cost fix: TTL must be well above the bidding loop period.
    assert _store()._cache_ttl >= 10
