"""Schedule view + automated gameweek scoring from fixtures."""

from __future__ import annotations

import asyncio

import reflex as rx

from platform_core import scoring_ops
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
    matches: list[dict[str, str]] = []     # {teams,date,time,venue,url,idx}
    scoring_running: bool = False
    msg: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_schedule(self):
        app = await self.get_state(AppState)
        for _ in range(100):
            if app.is_hydrated:
                break
            await asyncio.sleep(0.05)
        if not app.auth_user:
            return rx.redirect("/")
        code, doc, room = self._load()
        if not code:
            return
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
        self._compute(room)

    def _compute(self, room):
        sched = _schedule(self.tournament)
        g = next((x for x in sched if x["gw"] == self.selected_gw), None)
        self.gw_name = g["name"] if g else ""
        urls_raw = room.get("fixture_urls", {}).get(self.selected_gw, {}) if room else {}
        urls = {str(i): v for i, v in enumerate(urls_raw)} if isinstance(urls_raw, list) else urls_raw
        self.matches = [
            {"teams": mt["teams"], "date": mt["date"], "time": mt["time"], "venue": mt["venue"],
             "idx": str(i), "url": urls.get(str(i), "")}
            for i, mt in enumerate(g["matches"])
        ] if g else []

    @rx.event
    def select_gw(self, gw: str):
        self.selected_gw = gw
        _, _, room = self._load()
        self._compute(room)

    @rx.event
    def set_fixture_url(self, idx: str, url: str):
        code, doc, room = self._load()
        if not room:
            return
        room.setdefault("fixture_urls", {}).setdefault(self.selected_gw, {})[idx] = url.strip()
        repo.save(doc)
        self._compute(room)

    @rx.event(background=True)
    async def auto_score(self):
        async with self:
            if self.scoring_running:
                return
            self.scoring_running = True
            self.msg = ""
            code = self.room_code
            gw = self.selected_gw
        doc = repo.load()
        room = doc.get("rooms", {}).get(code)
        if room is None:
            async with self:
                self.scoring_running = False
            return
        urls_raw = room.get("fixture_urls", {}).get(gw, {})
        links = [u for u in urls_raw if u] if isinstance(urls_raw, list) else [u for u in urls_raw.values() if u]
        if not links:
            async with self:
                self.scoring_running = False
                self.msg = "⚠️ Add a WhoScored link to each fixture first (admin)."
            return
        totals, errors = await asyncio.to_thread(
            scoring_ops.score_gameweek_from_links, room, gw, links)
        if totals:
            repo.save(doc)
        async with self:
            self.scoring_running = False
            if totals:
                self.msg = (f"✅ Auto-scored GW{gw}: {len(totals)} players/keepers from "
                            f"{len(links)} match(es). Standings updated.")
            else:
                self.msg = "⚠️ No scores — " + (" | ".join(errors[:2]) if errors else "check the links.")
            if errors and totals:
                self.msg += f"  ({len(errors)} match(es) failed.)"
