"""WhoScored match points calculator — available to every logged-in participant."""

from __future__ import annotations

import asyncio

import reflex as rx

from scoring import whoscored_points

from .state import AppState


class WhoScoredState(rx.State):
    url: str = ""
    running: bool = False
    error: str = ""
    results: list[dict[str, str]] = []
    count: int = 0
    room_code: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    @rx.event
    async def guard(self):
        app = await self.get_state(AppState)
        for _ in range(100):
            if app.is_hydrated:
                break
            await asyncio.sleep(0.05)
        if not app.auth_user:
            return rx.redirect("/")
        self.room_code = (self.router._page.params.get("room", "") or "").upper()

    @rx.event(background=True)
    async def run(self):
        async with self:
            if self.running:
                return
            self.running = True
            self.error = ""
            self.results = []
            self.count = 0
            url = self.url.strip()
        if not url:
            async with self:
                self.running = False
                self.error = "Paste a WhoScored match link first."
            return
        try:
            rows = await asyncio.to_thread(whoscored_points, url)
            err = None
        except Exception as exc:  # network / parse / bot-block
            rows, err = None, str(exc)
        async with self:
            self.running = False
            if rows is None:
                self.error = f"Couldn't read that match (WhoScored may be blocking): {err}"
            elif not rows:
                self.error = "No player data found at that link."
            else:
                self.results = [
                    {"player": r["player"], "team": r["team"], "pos": r["pos"],
                     "score": str(r["score"]), "minutes": str(r["minutes"])}
                    for r in rows
                ]
                self.count = len(rows)
