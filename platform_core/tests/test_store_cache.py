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


def test_snapshot_does_not_copy_on_repeated_reads():
    # _snapshot must return the SHARED object (no per-call deep copy) so hot paths
    # don't pay to copy the whole document every few seconds per connected client.
    s = _store()
    s.save({"users": {}, "rooms": {"AB": {"name": "Alpha", "participants": []}}})
    assert s._snapshot() is s._snapshot()


def test_load_returns_independent_copy():
    s = _store()
    s.save({"users": {}, "rooms": {"AB": {"name": "Alpha", "participants": []}}})
    doc = s.load()
    assert doc is not s._snapshot()              # a private copy, safe to mutate
    doc["rooms"]["AB"]["name"] = "mutated"
    assert s.load()["rooms"]["AB"]["name"] == "Alpha"


def test_load_room_copies_only_one_room_not_the_whole_document(monkeypatch):
    # Regression guard for the crash/hang fix: the hot polling path must deep-copy a
    # SINGLE room node, never the entire multi-room document. If someone reroutes
    # load_room back through load() (full-doc deepcopy), this fails.
    import platform_core.firebase_store as fs

    s = _store()
    s.save({"users": {}, "rooms": {
        "AB": {"name": "Alpha", "participants": []},
        "CD": {"name": "Beta", "participants": []}}})

    copied = []
    real_deepcopy = fs.copy.deepcopy
    monkeypatch.setattr(fs.copy, "deepcopy", lambda x, *a, **k: (copied.append(x), real_deepcopy(x, *a, **k))[1])

    room = s.load_room("AB")
    assert room["name"] == "Alpha"
    # Exactly one deep copy, of the single room dict — never the full document.
    assert len(copied) == 1
    assert "rooms" not in copied[0]          # not the whole doc
    assert copied[0].get("name") == "Alpha"  # just the requested room
