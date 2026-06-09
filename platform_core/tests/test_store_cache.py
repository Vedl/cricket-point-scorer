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


# --------------------------------------------------------------------------- #
# The version-probe egress saver (remote mode, network mocked)
# --------------------------------------------------------------------------- #
class _ProbeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _ProbeRequests:
    """Records every GET and answers the _v probe vs the full-doc download."""

    def __init__(self, version=None, full_doc=None):
        self.version = version
        self.full_doc = full_doc
        self.get_urls: list[str] = []

    def get(self, url, timeout=None, **kw):
        self.get_urls.append(url)
        if "/_v.json" in url:
            return _ProbeResp(200, self.version)
        return _ProbeResp(200, self.full_doc)

    def put(self, *a, **kw):
        return _ProbeResp(200, None)

    @property
    def version_probes(self):
        return [u for u in self.get_urls if "/_v.json" in u]

    @property
    def full_downloads(self):
        return [u for u in self.get_urls if "/_v.json" not in u]


def _probe_store(monkeypatch, fake, *, cached_v):
    monkeypatch.setattr(fs, "requests", fake)
    s = FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"),
                      database_url="https://fake.firebaseio.com")
    assert s.use_remote is True
    s._cache = {"users": {}, "rooms": {"AB": {"name": "v1"}}, "_v": cached_v}
    s._cache_ts = 0.0  # force "stale" so a refresh is warranted
    return s


def test_refresh_probes_version_and_skips_full_download_when_unchanged(monkeypatch):
    fake = _ProbeRequests(version=100, full_doc={"_v": 999, "rooms": {"AB": {"name": "SHOULD_NOT_LOAD"}}})
    s = _probe_store(monkeypatch, fake, cached_v=100)
    s._refresh_once()
    # Only the tiny probe was fetched; the ~700 KB document was NOT downloaded.
    assert len(fake.version_probes) == 1
    assert fake.full_downloads == []
    assert s._cache["rooms"]["AB"]["name"] == "v1"  # cache untouched


def test_refresh_downloads_full_doc_only_when_version_advances(monkeypatch):
    fake = _ProbeRequests(version=200, full_doc={"_v": 200, "users": {}, "rooms": {"AB": {"name": "v2"}}})
    s = _probe_store(monkeypatch, fake, cached_v=100)
    s._refresh_once()
    assert len(fake.version_probes) == 1
    assert len(fake.full_downloads) == 1            # paid for the download exactly once
    assert s._cache["rooms"]["AB"]["name"] == "v2"  # snapshot updated


def test_refresh_does_not_clobber_with_stale_remote(monkeypatch):
    # Remote is BEHIND our cache (another worker's write in flight). Must not download.
    fake = _ProbeRequests(version=100, full_doc={"_v": 100, "rooms": {"AB": {"name": "OLD"}}})
    s = _probe_store(monkeypatch, fake, cached_v=500)
    s._refresh_once()
    assert fake.full_downloads == []
    assert s._cache["rooms"]["AB"]["name"] == "v1"


def test_refresh_falls_back_to_full_download_for_legacy_doc_without_version(monkeypatch):
    # Cache has no _v (legacy) -> can't probe -> must download to stay correct.
    fake = _ProbeRequests(version=None, full_doc={"users": {}, "rooms": {"AB": {"name": "v3"}}})
    monkeypatch.setattr(fs, "requests", fake)
    s = FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"),
                      database_url="https://fake.firebaseio.com")
    s._cache = {"users": {}, "rooms": {"AB": {"name": "v1"}}}  # no _v
    s._cache_ts = 0.0
    s._refresh_once()
    assert len(fake.full_downloads) == 1
    assert s._cache["rooms"]["AB"]["name"] == "v3"


def test_fetch_version_parses_int_and_rejects_garbage(monkeypatch):
    s = FirebaseStore(local_file_path=tempfile.mktemp(suffix=".json"),
                      database_url="https://fake.firebaseio.com")
    monkeypatch.setattr(fs, "requests", _ProbeRequests(version=1780925643871))
    assert s._fetch_version() == 1780925643871
    monkeypatch.setattr(fs, "requests", _ProbeRequests(version="not-a-number"))
    assert s._fetch_version() is None
    monkeypatch.setattr(fs, "requests", _ProbeRequests(version=True))
    assert s._fetch_version() is None  # JSON booleans must not coerce to 1
