"""Server-wide gameweek-deadline scheduler.

A single background loop (guarded process-wide) scans every room once a minute and
auto-locks squads + advances the gameweek for any deadline that has passed.
Started lazily from page on_load; the guard ensures only one loop runs.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime

import reflex as rx

from platform_core import season_ops as so

from .state import repo

_started = {"v": False}
_guard = threading.Lock()


class SchedulerState(rx.State):
    @rx.event(background=True)
    async def ensure_running(self):
        with _guard:
            if _started["v"]:
                return
            _started["v"] = True
        while True:
            try:
                doc = repo.load()
                changed = False
                now = datetime.now()
                for room in doc.get("rooms", {}).values():
                    if not isinstance(room, dict):
                        continue
                    if so.process_room_deadline(room, now):
                        changed = True
                    if so.process_due_deadlines(room, now):
                        changed = True
                if changed:
                    repo.save(doc)
            except Exception as exc:  # pragma: no cover - background resilience
                print(f"[scheduler] {exc}")
            await asyncio.sleep(60)
