"""Schedule view (World Cup fixtures grouped by gameweek)."""

from __future__ import annotations

import reflex as rx

from platform_core.config_layer import load_schedule

from .state import AppState, repo

_CACHE: dict[str, list[dict]] = {}


def _schedule(tournament: str) -> list[dict]:
    if tournament not in _CACHE:
        _CACHE[tournament] = load_schedule(tournament)
    return _CACHE[tournament]


class ScheduleState(rx.State):
    room_code: str = ""
    room_name: str = ""
    tournament: str = ""
    is_admin: bool = False
    has_schedule: bool = False
    gw_options: list[str] = []
    selected_gw: str = ""
    gw_name: str = ""
    matches: list[dict[str, str]] = []

    @rx.event
    async def on_load_schedule(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        room = doc.get("rooms", {}).get(code)
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.tournament = room.get("tournament_type", "")
        self.is_admin = room.get("admin") == app.auth_user
        sched = _schedule(self.tournament)
        self.has_schedule = bool(sched)
        self.gw_options = [g["gw"] for g in sched]
        if sched and (not self.selected_gw or self.selected_gw not in self.gw_options):
            self.selected_gw = sched[0]["gw"]
        self._compute()

    def _compute(self):
        sched = _schedule(self.tournament)
        g = next((x for x in sched if x["gw"] == self.selected_gw), None)
        self.gw_name = g["name"] if g else ""
        self.matches = g["matches"] if g else []

    @rx.event
    def select_gw(self, gw: str):
        self.selected_gw = gw
        self._compute()
