"""In-process shared auction state — the real-time backbone (PLAN.md §6.4).

The platform is self-hosted as a single backend process (spec §1.4), so every
connected WebSocket client is served by *this* Python process. That means a
module-level singleton is automatically shared across all clients: when one client
places a bid, the shared engine mutates and every other client's lightweight poll
loop sees it on the next tick (sub-second), with **no Firebase round-trip per
tick**.

Firebase's role is durability only: the room is loaded once on first access and
written back (in a daemon thread, non-blocking) after each mutation, so state
survives a restart.

Concurrency: one ``asyncio.Lock`` per room serialises mutations. Reads (the display
snapshot) are lock-free — dict access is atomic enough under the GIL for a view.
"""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from typing import Callable, Optional

from auction_engine import AuctionEngine
from platform_core.repository import (
    Repository,
    engine_from_room,
    save_engine_to_room,
)

repo = Repository()


class _Room:
    __slots__ = ("room", "engine", "lock")

    def __init__(self, room: dict, engine: AuctionEngine):
        self.room = room
        self.engine = engine
        self.lock = asyncio.Lock()


class RoomHub:
    _rooms: dict[str, _Room] = {}
    _guard = threading.Lock()  # protects _rooms dict mutation

    # ------------------------------------------------------------------ #
    @classmethod
    def _ensure(cls, code: str) -> Optional[_Room]:
        code = (code or "").upper()
        with cls._guard:
            entry = cls._rooms.get(code)
        if entry is not None:
            return entry
        doc = repo.load()
        room = doc.get("rooms", {}).get(code)
        if room is None:
            return None
        entry = _Room(room, engine_from_room(room))
        with cls._guard:
            cls._rooms[code] = entry
        return entry

    @classmethod
    def lock(cls, code: str) -> asyncio.Lock:
        entry = cls._ensure(code)
        if entry is None:
            # Lock on a transient so callers don't crash on bad codes.
            return asyncio.Lock()
        return entry.lock

    @classmethod
    def engine(cls, code: str) -> Optional[AuctionEngine]:
        entry = cls._ensure(code)
        return entry.engine if entry else None

    @classmethod
    def room(cls, code: str) -> Optional[dict]:
        entry = cls._ensure(code)
        return entry.room if entry else None

    @classmethod
    def reload_from_firebase(cls, code: str) -> None:
        """Drop the in-memory copy and re-read from Firebase (admin recovery)."""
        code = (code or "").upper()
        with cls._guard:
            cls._rooms.pop(code, None)
        cls._ensure(code)

    # ------------------------------------------------------------------ #
    @classmethod
    def persist(cls, code: str) -> None:
        """Write the room back to Firebase without blocking the event loop."""
        code = (code or "").upper()
        entry = cls._rooms.get(code)
        if entry is None:
            return
        save_engine_to_room(entry.engine, entry.room)
        snapshot = copy.deepcopy(entry.room)

        def _write():
            try:
                repo.store.patch_room(code, snapshot)
            except Exception as exc:  # pragma: no cover - network
                print(f"[RoomHub] persist failed for {code}: {exc}")

        threading.Thread(target=_write, daemon=True).start()

    @classmethod
    async def mutate(cls, code: str, fn: Callable[[AuctionEngine], object]):
        """Run ``fn(engine)`` under the room lock, then persist. Returns fn result.

        Exceptions from ``fn`` propagate (callers surface them as messages).
        """
        entry = cls._ensure(code)
        if entry is None:
            raise KeyError(f"Unknown room {code!r}")
        async with entry.lock:
            result = fn(entry.engine)
            cls.persist(code)
            return result
