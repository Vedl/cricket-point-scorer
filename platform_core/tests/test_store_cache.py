"""Egress-control behaviour of FirebaseStore (local mode: no remote calls)."""

import copy
import json
import tempfile
import time

import platform_core.firebase_store as fs
from platform_core.firebase_store import FirebaseStore


def _store():
    return FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"))


class _FakeResp:
    status_code = 200


class _FakeRequests:
    """Captures Firebase REST calls so tests can assert on the payloads."""

    def __init__(self):
        self.calls = []

    def put(self, url, data=None, **kw):
        self.calls.append(("put", url, data))
        return _FakeResp()

    def patch(self, url, data=None, **kw):
        self.calls.append(("patch", url, data))
        return _FakeResp()

    def get(self, url, **kw):  # pragma: no cover - not exercised here
        self.calls.append(("get", url, None))
        return _FakeResp()


def _remote_store(monkeypatch, fake):
    monkeypatch.setattr(fs, "requests", fake)
    return FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"),
                         database_url="https://db.example.com")


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


# --- log pruning -------------------------------------------------------------- #
def test_save_prunes_unbounded_logs_keeping_newest():
    s = _store()
    cap = s._log_cap
    room = {
        "name": "A",
        "transactions": [{"i": i} for i in range(cap + 500)],
        "auction_log": [{"i": i} for i in range(cap + 500)],
        "bid_log": [{"i": i} for i in range(cap + 500)],  # NOT pruned (engine state)
    }
    s.save({"users": {}, "rooms": {"AB": room}})
    loaded = s.load_room("AB")
    assert len(loaded["transactions"]) == cap
    assert loaded["transactions"][-1]["i"] == cap + 499      # newest kept
    assert loaded["transactions"][0]["i"] == 500             # oldest dropped
    assert len(loaded["auction_log"]) == cap
    assert len(loaded["bid_log"]) == cap + 500               # left intact


# --- per-room (diff) remote writes ------------------------------------------- #
def test_flush_remote_full_put_when_no_baseline(monkeypatch):
    fake = _FakeRequests()
    s = _remote_store(monkeypatch, fake)
    assert s.use_remote
    s._last_written = None
    doc = {"users": {}, "rooms": {"AB": {"name": "Alpha"}, "CD": {"name": "Beta"}}, "_v": 1}
    assert s._flush_remote(doc) is True
    method, _url, _data = fake.calls[-1]
    assert method == "put"


def test_flush_remote_patches_only_changed_room(monkeypatch):
    fake = _FakeRequests()
    s = _remote_store(monkeypatch, fake)
    base = {"users": {}, "rooms": {"AB": {"name": "Alpha"}, "CD": {"name": "Beta"}}, "_v": 1}
    s._last_written = copy.deepcopy(base)
    new = copy.deepcopy(base)
    new["rooms"]["AB"]["name"] = "Alpha2"
    new["_v"] = 2
    fake.calls.clear()
    assert s._flush_remote(new) is True
    method, _url, data = fake.calls[-1]
    assert method == "patch"
    body = json.loads(data)
    assert "rooms/AB" in body and "rooms/CD" not in body   # only the changed room
    assert body["rooms/AB"]["name"] == "Alpha2"
    assert body["_v"] == 2


def test_flush_remote_patches_deletion_as_null(monkeypatch):
    fake = _FakeRequests()
    s = _remote_store(monkeypatch, fake)
    base = {"users": {}, "rooms": {"AB": {"name": "Alpha"}, "CD": {"name": "Beta"}}, "_v": 1}
    s._last_written = copy.deepcopy(base)
    new = {"users": {}, "rooms": {"AB": {"name": "Alpha"}}, "_v": 2}  # CD removed
    fake.calls.clear()
    assert s._flush_remote(new) is True
    body = json.loads(fake.calls[-1][2])
    assert body["rooms/CD"] is None
    assert "rooms/AB" not in body                          # AB unchanged → not sent


def test_flush_remote_includes_users_when_changed(monkeypatch):
    fake = _FakeRequests()
    s = _remote_store(monkeypatch, fake)
    base = {"users": {}, "rooms": {"AB": {"name": "Alpha"}}, "_v": 1}
    s._last_written = copy.deepcopy(base)
    new = {"users": {"u": {"x": 1}}, "rooms": {"AB": {"name": "Alpha"}}, "_v": 2}
    fake.calls.clear()
    assert s._flush_remote(new) is True
    body = json.loads(fake.calls[-1][2])
    assert body["users"] == {"u": {"x": 1}}
    assert not any(k.startswith("rooms/") for k in body)   # no room changed


def test_save_write_behind_full_put_then_patch(monkeypatch):
    fake = _FakeRequests()
    s = _remote_store(monkeypatch, fake)

    def _wait(n, timeout=2.0):
        end = time.time() + timeout
        while time.time() < end and len(fake.calls) < n:
            time.sleep(0.01)

    s.save({"users": {}, "rooms": {"AB": {"name": "Alpha"}, "CD": {"name": "Beta"}}})
    _wait(1)
    # Wait for the baseline to be committed before the next save's diff.
    end = time.time() + 2.0
    while time.time() < end and s._last_written is None:
        time.sleep(0.01)

    doc = s.load()
    doc["rooms"]["AB"]["name"] = "Alpha2"
    s.save(doc)
    _wait(2)
    s.flush()

    assert fake.calls[0][0] == "put"                       # cold → full document
    assert fake.calls[1][0] == "patch"                     # then only the diff
    body = json.loads(fake.calls[1][2])
    assert "rooms/AB" in body and "rooms/CD" not in body
