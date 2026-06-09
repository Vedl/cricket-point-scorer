"""Streamlit-free Firebase Realtime Database client.

Ported from the legacy ``backend/storage.py`` (which read config from
``st.secrets``). This version reads config from **environment variables** and has
no Streamlit dependency, so it works inside Reflex or plain scripts:

    FIREBASE_DATABASE_URL   e.g. https://my-app.firebaseio.com   (no trailing /)
    FIREBASE_SECRET         legacy DB secret appended as ?auth=  (optional)
    AUCTION_DATA_FILE       local cache path (default: ./auction_data.json)

Behaviour:
  * If ``FIREBASE_DATABASE_URL`` is set → Firebase is the source of truth (REST),
    with the local file used as a write-through cache.
  * If it is not set → the store degrades to a **local JSON file**, so the rest of
    the app can be developed and unit-tested without any Firebase project.

The document shape is the legacy one: ``{"users": {...}, "rooms": {...}}``.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from typing import Any, Optional

try:  # requests is optional in pure-local mode
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

DEFAULT_DATA_FILE = "auction_data.json"
EMPTY_DOC: dict[str, Any] = {"users": {}, "rooms": {}}

# Append-only logs that otherwise grow forever. They are capped on every save so the
# whole document — and therefore every read, deep-copy and Firebase upload — stays
# bounded. Unbounded growth here is the slow-burn cause of memory creep over a season.
# (bid_log is intentionally NOT pruned: it is auction-engine state, not display history.)
PRUNE_LOG_KEYS = ("transactions", "auction_log")
DEFAULT_LOG_CAP = 1000


def warm_cache(store: Optional["FirebaseStore"] = None) -> dict:
    """Populate the in-memory snapshot before the web server accepts traffic.

    Called from ``hf_start.sh`` on Render so the first websocket hydrate never
    blocks the asyncio loop on a cold Firebase download."""
    store = store or FirebaseStore()
    return store.load()


class FirebaseStore:
    def __init__(
        self,
        local_file_path: Optional[str] = None,
        database_url: Optional[str] = None,
        secret: Optional[str] = None,
        timeout: int = 15,
    ):
        self.local_file_path = (
            local_file_path
            or os.environ.get("AUCTION_DATA_FILE")
            or DEFAULT_DATA_FILE
        )
        self.database_url = (
            database_url if database_url is not None
            else os.environ.get("FIREBASE_DATABASE_URL", "")
        ).rstrip("/")
        self.secret = (
            secret
            if secret is not None
            else os.environ.get("FIREBASE_SECRET")
            or os.environ.get("FIREBASE_SECRET_KEY", "")  # legacy env name
        )
        self.timeout = timeout
        self.use_remote = bool(self.database_url) and requests is not None
        # Short in-memory snapshot cache. Rapid page navigations (and concurrent
        # on_load handlers on a single backend worker) would otherwise each fire a
        # Firebase read; under load some time out and fall back to a stale local
        # file, making a live room look "missing" and bouncing the user out. A few
        # seconds of caching keeps reads consistent and cheap (Blaze-friendly).
        self._cache: Optional[dict] = None
        self._cache_ts: float = 0.0
        # TTL is the max staleness served from memory. Longer = far fewer Firebase
        # downloads (egress $$). Writes are write-through so a process always sees its
        # OWN changes instantly regardless of TTL; the TTL only delays seeing another
        # writer's changes. 20s keeps egress low while staying fresh enough.
        self._cache_ttl: float = float(os.environ.get("STORE_CACHE_TTL", "20"))
        # Per-room snapshot cache for hot polling paths (load_room) — reads ONE room
        # node (~20-50 KB) instead of the whole ~1 MB document.
        self._room_cache: dict[str, tuple] = {}
        # Async write-behind: events update the local cache instantly and return;
        # the (full-document) Firebase PUT is flushed on a background thread and
        # coalesced, so a burst of actions never blocks the UI on the network.
        # ``_pending`` holds the latest full document waiting to be flushed (a burst of
        # saves coalesces into the newest one). ``_last_written`` is our snapshot of what
        # Firebase currently holds, used to send only the rooms that actually changed.
        self._pending: Optional[dict] = None
        self._last_written: Optional[dict] = None
        self._writer_lock = threading.Lock()
        self._writer_cv = threading.Condition(self._writer_lock)
        self._writer_started = False
        self._refreshing = False
        try:
            self._log_cap = max(50, int(os.environ.get("STORE_LOG_CAP", str(DEFAULT_LOG_CAP))))
        except (TypeError, ValueError):
            self._log_cap = DEFAULT_LOG_CAP

    @property
    def db_url(self) -> str:
        base = f"{self.database_url}/auction_data.json"
        return f"{base}?auth={self.secret}" if self.secret else base

    @property
    def version_url(self) -> str:
        """URL of the document's root version stamp ONLY (a single integer, ~13 bytes).

        Reading this instead of the whole document is the core egress saver: a refresh
        first asks "has anything changed?" by downloading ~13 bytes, and only pays for
        the full ~700 KB download when the answer is yes."""
        base = f"{self.database_url}/auction_data/_v.json"
        return f"{base}?auth={self.secret}" if self.secret else base

    def _fetch_version(self) -> Optional[int]:
        """Return the remote root ``_v`` stamp, or None if unavailable/legacy doc."""
        try:
            resp = requests.get(self.version_url, timeout=self.timeout)
            if resp.status_code == 200:
                v = resp.json()
                if isinstance(v, bool):  # JSON true/false would coerce to 1/0
                    return None
                if isinstance(v, (int, float)):
                    return int(v)
        except Exception as exc:  # pragma: no cover - network
            print(f"[FirebaseStore] version probe failed: {exc}")
        return None

    # ------------------------------------------------------------------ #
    # Normalisation (Firebase turns dicts with numeric keys into sparse lists)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(data: Any) -> Any:
        if data is None:
            return {}
        if isinstance(data, dict):
            return {k: FirebaseStore._normalize(v) for k, v in data.items()}
        if isinstance(data, list):
            # A sparse list (contains None) is Firebase's encoding of a dict whose
            # keys looked numeric — convert it back to a dict.
            if any(item is None for item in data):
                return {
                    str(i): FirebaseStore._normalize(item)
                    for i, item in enumerate(data)
                    if item is not None
                }
            return [
                FirebaseStore._normalize(item)
                if isinstance(item, (dict, list))
                else item
                for item in data
            ]
        return data

    @staticmethod
    def _ensure_schema(data: dict) -> dict:
        data.setdefault("users", {})
        data.setdefault("rooms", {})
        for room in data["rooms"].values():
            if isinstance(room, dict):
                parts = room.get("participants")
                if isinstance(parts, list):
                    for p in parts:
                        if isinstance(p, dict) and not isinstance(p.get("squad"), list):
                            p["squad"] = []
        return data

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    def _snapshot(self) -> dict:
        """Return the SHARED in-memory document snapshot WITHOUT copying it.

        Handles cache freshness (stale-while-revalidate) but does NOT deep-copy, so
        it is cheap enough to call on hot paths. Callers MUST treat the result as
        read-only and never mutate it — use :meth:`load` / :meth:`load_room` to get a
        private, mutable copy.

        The synchronous ``requests`` network call, if run inside a Reflex event
        handler, blocks the asyncio loop; under concurrent clicks that starves the
        websocket heartbeat → the client disconnects, re-hydrates, and the user is
        bounced out of the room. So we serve the in-memory snapshot instantly and
        refresh it on a background thread when stale. Only the very first load (cold
        cache) blocks, to populate the snapshot."""
        st = os.stat(self.local_file_path) if os.path.exists(self.local_file_path) else None
        mtime = st.st_mtime if st else 0.0
        ino = st.st_ino if st else 0

        if self._cache is not None:
            if mtime <= getattr(self, "_cache_file_mtime", 0.0) and ino == getattr(self, "_cache_file_ino", 0):
                if (time.monotonic() - self._cache_ts) >= self._cache_ttl and self._pending is None:
                    self._schedule_refresh()
                return self._cache
            # Another worker wrote to the file! We must reload the local file.

        # Cold start (or another worker wrote to the file).
        if self._cache is None and self.use_remote and not os.path.exists(self.local_file_path):
            # Only block on Firebase if we have literally no local file.
            try:
                resp = requests.get(self.db_url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = self._ensure_schema(self._normalize(resp.json()))
                    self._write_local(data)
                    self._cache = data
                    self._cache_ts = time.monotonic()
                    st = os.stat(self.local_file_path) if os.path.exists(self.local_file_path) else None
                    self._cache_file_mtime = st.st_mtime if st else 0.0
                    self._cache_file_ino = st.st_ino if st else 0
                    return self._cache
            except Exception as exc:  # pragma: no cover - network
                print(f"[FirebaseStore] remote load failed: {exc}")

        local = self._load_local()
        self._cache = local
        self._cache_ts = time.monotonic()
        st = os.stat(self.local_file_path) if os.path.exists(self.local_file_path) else None
        self._cache_file_mtime = st.st_mtime if st else 0.0
        self._cache_file_ino = st.st_ino if st else 0
        return self._cache

    def load(self) -> dict:
        """Return a PRIVATE deep copy of the full document (safe to mutate-then-save).

        Most callers go through ``load`` to read-modify-write the whole document.
        The deep copy isolates the caller's mutations from the shared snapshot until
        they call :meth:`save`."""
        return copy.deepcopy(self._snapshot())

    def load_room(self, code: str) -> Optional[dict]:
        """Return a private deep copy of ONE room — the cheap hot-path read.

        Polling paths (the per-client bidding ``live_loop``, page on-loads) only ever
        need a single room, so we deep-copy just that ~20-50 KB node instead of the
        whole ~1 MB+ document. Going through ``_snapshot()`` also keeps the cache fresh
        (stale-while-revalidate). On a 512 MB single-CPU box this is the difference
        between the event loop keeping up and OOM/heartbeat starvation: it avoids
        copying every other room, N times every few seconds, for every connected tab.
        Returns an independent copy so callers can mutate it safely."""
        room = self._snapshot().get("rooms", {}).get((code or "").upper())
        return copy.deepcopy(room) if isinstance(room, dict) else None

    def _schedule_refresh(self) -> None:
        """Kick off a single background refresh of the snapshot from Firebase."""
        if not self.use_remote:
            return
        with self._writer_lock:
            if self._refreshing:
                return
            self._refreshing = True
        threading.Thread(target=self._refresh_once, name="fb-refresh", daemon=True).start()

    def _refresh_once(self) -> None:
        try:
            # Cheap change-probe FIRST: download only the ~13-byte root version stamp.
            # If it matches what we already hold, the document is unchanged and we skip
            # the expensive full GET entirely — this is what slashes Firebase egress
            # (most refresh ticks find nothing changed). Only fall through to the full
            # download when the version moved forward or the doc is legacy (no _v).
            cached_v = self._cache.get("_v", 0) if self._cache else 0
            if cached_v:
                remote_v = self._fetch_version()
                if remote_v is not None and remote_v <= cached_v:
                    # Unchanged (==) or stale/in-flight remote (<): nothing to pull.
                    self._cache_ts = time.monotonic()
                    return
            if self._pending is not None:
                return  # a local write is queued — don't overwrite it with a read
            resp = requests.get(self.db_url, timeout=self.timeout)
            # Don't clobber the snapshot if a local write is queued/in-flight.
            if resp.status_code == 200 and self._pending is None:
                data = self._ensure_schema(self._normalize(resp.json()))
                
                # Prevent clobbering local data with stale Firebase data due to multi-worker race conditions
                local_v = self._cache.get("_v", 0) if self._cache else 0
                remote_v = data.get("_v", 0)
                if remote_v < local_v:
                    return  # Firebase returned stale data (a PUT from another worker is likely in flight)

                self._cache = data
                self._cache_ts = time.monotonic()
                self._write_local(data)
        except Exception as exc:  # pragma: no cover - network
            print(f"[FirebaseStore] background refresh failed: {exc}")
        finally:
            self._refreshing = False

    def _load_local(self) -> dict:
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, "r") as f:
                    return self._ensure_schema(json.load(f))
            except Exception as exc:  # pragma: no cover
                print(f"[FirebaseStore] local load failed: {exc}")
        return json.loads(json.dumps(EMPTY_DOC))  # fresh deep copy

    def _write_local(self, data: dict) -> None:
        try:
            tmp = self.local_file_path + ".tmp"
            with open(tmp, "w") as f:
                f.write(json.dumps(data, indent=2))
            # Atomic publish via rename. We deliberately DON'T fsync here: this file
            # is only a warm-restart cache (Firebase is the source of truth), and a
            # synchronous fsync of the whole ~1 MB+ document on every save would stall
            # the asyncio event loop inside the calling event handler (place_bid, admin
            # ops…), causing the hangs we're fixing. os.replace still gives atomicity.
            os.replace(tmp, self.local_file_path)
            st = os.stat(self.local_file_path)
            self._cache_file_mtime = st.st_mtime
            self._cache_file_ino = st.st_ino
        except Exception as exc:  # pragma: no cover
            print(f"[FirebaseStore] local write failed: {exc}")

    def _prune(self, data: dict) -> dict:
        """Cap append-only logs per room so the document can't grow without bound."""
        cap = self._log_cap
        for room in data.get("rooms", {}).values():
            if not isinstance(room, dict):
                continue
            for key in PRUNE_LOG_KEYS:
                seq = room.get(key)
                if isinstance(seq, list) and len(seq) > cap:
                    room[key] = seq[-cap:]  # keep the most recent entries
        return data

    def save(self, data: dict) -> None:
        """Persist the whole document: local cache always, Firebase if configured."""
        data = self._ensure_schema(data)
        self._prune(data)
        data["_v"] = int(time.time() * 1000)  # Add timestamp to prevent stale remote clobbering
        self._write_local(data)
        # Write-through: refresh the snapshot so the next load reflects this save.
        # Deep-copy so the caller (who still holds ``data``) can keep mutating its
        # object without corrupting the shared cache.
        self._cache = copy.deepcopy(data)
        self._cache_ts = time.monotonic()
        if self.use_remote:
            # Hand the isolated cache copy to the writer (caller may keep mutating ``data``).
            self._queue_remote(self._cache)

    # ------------------------------------------------------------------ #
    # Async write-behind to Firebase (coalesced, non-blocking, per-room)
    # ------------------------------------------------------------------ #
    def _queue_remote(self, doc: dict) -> None:
        with self._writer_cv:
            self._pending = doc  # keep only the latest — coalesce a burst
            if not self._writer_started:
                self._writer_started = True
                threading.Thread(target=self._writer_loop, name="fb-writer",
                                 daemon=True).start()
            self._writer_cv.notify()

    @staticmethod
    def _canon(obj: Any) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))

    def _flush_remote(self, doc: dict) -> bool:
        """Push ``doc`` to Firebase, sending only what changed since the last write.

        With a known baseline we issue a single multi-location PATCH containing just the
        rooms that changed (``rooms/<code>``), deletions (``rooms/<code>: null``) and the
        users node if it changed — instead of re-uploading the whole ~1 MB+ document on
        every bid. Falls back to a full PUT when there is no baseline (cold start /
        after a restart) or when essentially everything changed."""
        baseline = self._last_written
        if baseline is None:
            resp = requests.put(self.db_url, data=json.dumps(doc),
                                headers={"Content-Type": "application/json"},
                                timeout=self.timeout)
            return resp.status_code == 200

        old_rooms = baseline.get("rooms", {})
        new_rooms = doc.get("rooms", {})
        update: dict[str, Any] = {}
        for code, room in new_rooms.items():
            if code not in old_rooms or self._canon(old_rooms[code]) != self._canon(room):
                update[f"rooms/{code}"] = room
        for code in old_rooms:
            if code not in new_rooms:
                update[f"rooms/{code}"] = None  # Firebase deletes keys written as null
        if self._canon(baseline.get("users", {})) != self._canon(doc.get("users", {})):
            update["users"] = doc.get("users", {})
        update["_v"] = doc.get("_v", int(time.time() * 1000))

        # Top-level keys are only users/rooms/_v, all covered above, so a multi-location
        # PATCH keeps Firebase exactly in sync with our document while sending only the
        # rooms that actually changed.
        resp = requests.patch(self.db_url, data=json.dumps(update),
                              headers={"Content-Type": "application/json"},
                              timeout=self.timeout)
        return resp.status_code == 200

    def _writer_loop(self) -> None:
        while True:
            with self._writer_cv:
                while self._pending is None:
                    self._writer_cv.wait()
                doc = self._pending
                self._pending = None
            try:
                if self._flush_remote(doc):
                    # Only advance the baseline on success, so a failed write is
                    # automatically re-included in the next save's diff.
                    self._last_written = doc
                else:  # pragma: no cover - network
                    print("[FirebaseStore] remote save failed")
            except Exception as exc:  # pragma: no cover
                print(f"[FirebaseStore] remote save error: {exc}")

    def flush(self, timeout: float = 5.0) -> None:
        """Block until any pending remote write has been sent (for shutdown/tests)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._writer_cv:
                if self._pending is None:
                    return
            time.sleep(0.02)

    def patch_room(self, room_code: str, room: dict) -> None:
        """Write a single room node (cheaper Firebase PATCH; full local rewrite)."""
        data = self.load()
        data.setdefault("rooms", {})[room_code] = room
        # Bump the root version stamp so the cheap _v probe (other workers' refresh)
        # still detects this change even though we only PUT one room node — keeps the
        # egress optimisation correct under a hypothetical multi-worker deploy.
        new_v = int(time.time() * 1000)
        data["_v"] = new_v
        if self.use_remote:
            try:
                base = f"{self.database_url}/auction_data/rooms/{room_code}.json"
                requests.put(
                    base + (f"?auth={self.secret}" if self.secret else ""),
                    data=json.dumps(room),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                # Patch the root _v in the same shape save() uses, so probes compare like-for-like.
                root = f"{self.database_url}/auction_data.json"
                requests.patch(
                    root + (f"?auth={self.secret}" if self.secret else ""),
                    data=json.dumps({"_v": new_v}),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
            except Exception as exc:  # pragma: no cover
                print(f"[FirebaseStore] patch_room error: {exc}")
        self._write_local(data)
        self._cache = copy.deepcopy(data)
        self._cache_ts = time.monotonic()
