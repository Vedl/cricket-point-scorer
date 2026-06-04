"""Server-wide gameweek-deadline scheduler.

A single background **daemon thread** (guarded process-wide) scans every room once
a minute and auto-locks squads + advances the gameweek for any deadline that has
passed. It is started at import time and again (idempotently) from page on_load, so
it keeps running even when no browser session is connected — unlike a Reflex
client-bound background task, which is cancelled when its client disconnects.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime

import reflex as rx

from platform_core import season_ops as so

from .state import repo

_started = False
_guard = threading.Lock()


def _tick() -> None:
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


def _interval() -> int:
    # Each tick reads the full document once (download egress). Deadlines are set
    # hours ahead, so checking every ~2 min is plenty and keeps egress modest.
    try:
        return max(30, int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "120")))
    except ValueError:
        return 120


def _loop() -> None:
    while True:
        try:
            _tick()
        except Exception as exc:  # pragma: no cover - background resilience
            print(f"[scheduler] {exc}")
        time.sleep(_interval())


def start_scheduler() -> None:
    """Idempotently start the single background scheduler thread."""
    global _started
    with _guard:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="gw-scheduler", daemon=True).start()


# Start as soon as the backend imports the app — no client connection required.
start_scheduler()


class SchedulerState(rx.State):
    @rx.event
    def ensure_running(self):
        # Belt-and-suspenders: make sure the daemon is alive (no-op if already).
        start_scheduler()
