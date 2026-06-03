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

import json
import os
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
        """Load the document. Remote first (if configured), else local file."""
        if self.use_remote:
            try:
                resp = requests.get(self.db_url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = self._ensure_schema(self._normalize(resp.json()))
                    self._write_local(data)
                    return data
            except Exception as exc:  # pragma: no cover - network
                print(f"[FirebaseStore] remote load failed: {exc}")
        return self._load_local()

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
        if self.use_remote:
            try:
                resp = requests.put(
                    self.db_url,
                    data=json.dumps(data),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                if resp.status_code != 200:  # pragma: no cover
                    print(f"[FirebaseStore] remote save failed: {resp.status_code}")
            except Exception as exc:  # pragma: no cover
                print(f"[FirebaseStore] remote save error: {exc}")

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
