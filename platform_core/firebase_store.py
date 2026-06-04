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
        self._pending: Optional[str] = None
        self._writer_lock = threading.Lock()
        self._writer_cv = threading.Condition(self._writer_lock)
        self._writer_started = False
        self._refreshing = False

    @property
    def db_url(self) -> str:
        base = f"{self.database_url}/auction_data.json"
        return f"{base}?auth={self.secret}" if self.secret else base

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
    def load(self) -> dict:
        """Return the document WITHOUT ever blocking the async event loop after the
        first warm-up.

        The synchronous ``requests`` network call, if run inside a Reflex event
        handler, blocks the asyncio loop; under concurrent clicks that starves the
        websocket heartbeat → the client disconnects, re-hydrates, and the user is
        bounced out of the room. So we serve the in-memory snapshot instantly and
        refresh it on a background thread when stale (stale-while-revalidate). Only
        the very first load (cold cache) blocks, to populate the snapshot. Always
        returns a private deep copy so callers can mutate-then-save safely."""
        if self._cache is not None:
            if (time.monotonic() - self._cache_ts) >= self._cache_ttl and self._pending is None:
                self._schedule_refresh()
            return copy.deepcopy(self._cache)
        # Cold start: populate once (blocking is acceptable here — happens at boot).
        if self.use_remote:
            try:
                resp = requests.get(self.db_url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = self._ensure_schema(self._normalize(resp.json()))
                    self._write_local(data)
                    self._cache = copy.deepcopy(data)
                    self._cache_ts = time.monotonic()
                    self._sync_room_cache(data)
                    return data
            except Exception as exc:  # pragma: no cover - network
                print(f"[FirebaseStore] remote load failed: {exc}")
        local = self._load_local()
        self._cache = copy.deepcopy(local)
        self._cache_ts = time.monotonic()
        self._sync_room_cache(local)
        return local

    def _sync_room_cache(self, data: dict) -> None:
        """Keep the per-room cache coherent whenever the full doc is (re)loaded/saved."""
        now = time.monotonic()
        rooms = data.get("rooms", {})
        if isinstance(rooms, dict):
            for code, room in rooms.items():
                self._room_cache[code] = (copy.deepcopy(room), now)

    def load_room(self, code: str) -> Optional[dict]:
        """Read a SINGLE room node (cheap — ~20-50 KB vs the ~1 MB full doc).

        For hot polling paths (the bidding loop). Serves the per-room cache when
        fresh; otherwise reads just ``/auction_data/rooms/{code}`` from Firebase.
        Never blocks longer than one small request, and returns a private copy."""
        code = (code or "").upper()
        ce = self._room_cache.get(code)
        if ce is not None and (time.monotonic() - ce[1]) < self._cache_ttl:
            return copy.deepcopy(ce[0])
        if self.use_remote:
            try:
                url = f"{self.database_url}/auction_data/rooms/{code}.json"
                if self.secret:
                    url += f"?auth={self.secret}"
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    room = self._normalize(resp.json())
                    if room is not None:
                        self._room_cache[code] = (copy.deepcopy(room), time.monotonic())
                    return room
            except Exception as exc:  # pragma: no cover - network
                print(f"[FirebaseStore] room load failed: {exc}")
            if ce is not None:
                return copy.deepcopy(ce[0])
        # Local fallback (or cold cache without remote).
        return self.load().get("rooms", {}).get(code)

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
            resp = requests.get(self.db_url, timeout=self.timeout)
            # Don't clobber the snapshot if a local write is queued/in-flight.
            if resp.status_code == 200 and self._pending is None:
                data = self._ensure_schema(self._normalize(resp.json()))
                self._cache = copy.deepcopy(data)
                self._cache_ts = time.monotonic()
                self._sync_room_cache(data)
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
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.local_file_path)
        except Exception as exc:  # pragma: no cover
            print(f"[FirebaseStore] local write failed: {exc}")

    def save(self, data: dict) -> None:
        """Persist the whole document: local cache always, Firebase if configured."""
        data = self._ensure_schema(data)
        self._write_local(data)
        # Write-through: refresh the snapshot so the next load reflects this save.
        self._cache = copy.deepcopy(data)
        self._cache_ts = time.monotonic()
        self._sync_room_cache(data)
        if self.use_remote:
            self._queue_remote(json.dumps(data))

    # ------------------------------------------------------------------ #
    # Async write-behind to Firebase (coalesced, non-blocking)
    # ------------------------------------------------------------------ #
    def _queue_remote(self, payload: str) -> None:
        with self._writer_cv:
            self._pending = payload  # keep only the latest — coalesce a burst
            if not self._writer_started:
                self._writer_started = True
                threading.Thread(target=self._writer_loop, name="fb-writer",
                                 daemon=True).start()
            self._writer_cv.notify()

    def _writer_loop(self) -> None:
        while True:
            with self._writer_cv:
                while self._pending is None:
                    self._writer_cv.wait()
                payload = self._pending
                self._pending = None
            try:
                resp = requests.put(
                    self.db_url, data=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                if resp.status_code != 200:  # pragma: no cover
                    print(f"[FirebaseStore] remote save failed: {resp.status_code}")
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
        if self.use_remote:
            try:
                url = f"{self.database_url}/auction_data/rooms/{room_code}.json"
                if self.secret:
                    url += f"?auth={self.secret}"
                requests.put(
                    url,
                    data=json.dumps(room),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
            except Exception as exc:  # pragma: no cover
                print(f"[FirebaseStore] patch_room error: {exc}")
        self._write_local(data)
        self._cache = copy.deepcopy(data)
        self._cache_ts = time.monotonic()
