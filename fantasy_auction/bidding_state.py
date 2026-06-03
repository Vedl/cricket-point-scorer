"""Open-bidding state — 24h standing-bid market on unowned players."""

from __future__ import annotations

import asyncio
import time

import reflex as rx

from platform_core import bidding_ops as bo
from season_engine.open_bidding import BidError

from .state import AppState, repo


def _fmt_remaining(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class BiddingState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    my_team: str = ""
    my_budget: int = 0

    search: str = ""
    available: list[dict[str, str]] = []
    active: list[dict[str, str]] = []
    bid_player: str = ""
    bid_amount: str = ""
    msg: str = ""

    watching: bool = False
    loop_running: bool = False

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_bidding(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code, doc, room = self._load()
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.my_team = next((p["name"] for p in room.get("participants", [])
                             if p.get("user") == app.auth_user), "")
        self.msg = ""
        self._refresh(room)
        self.watching = True
        if not self.loop_running:
            return BiddingState.live_loop

    def _refresh(self, room: dict):
        by = {p["name"]: p for p in room.get("participants", [])}
        self.my_budget = by.get(self.my_team, {}).get("budget", 0)
        self.available = [
            {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
            for p in bo.available_players(room, search=self.search, limit=50)
        ]
        self.active = [
            {"player": b["player"], "team": b["team"], "high_bid": str(b["high_bid"]),
             "high_bidder": b["high_bidder"], "remaining": _fmt_remaining(b["remaining"]),
             "mine": "yes" if b["high_bidder"] == self.my_team else "no"}
            for b in bo.active(room, time.time())
        ]

    @rx.event
    def do_search(self):
        code, doc, room = self._load()
        if room:
            self._refresh(room)

    @rx.event
    def place_bid(self):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            bo.place(room, self.my_team, self.bid_player, int(self.bid_amount or 0), time.time())
        except (BidError, ValueError) as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self.bid_amount = ""
        self._refresh(room)
        self.msg = f"✅ Bid placed on {self.bid_player} — stands for 24h unless outbid."

    @rx.event
    def pick(self, player: str):
        self.bid_player = player

    @rx.event(background=True)
    async def live_loop(self):
        async with self:
            if self.loop_running:
                return
            self.loop_running = True
        try:
            while True:
                async with self:
                    if not self.watching or not self.room_code:
                        return
                    code = self.room_code
                # resolve due bids + refresh (outside state lock for the network bit)
                doc = repo.load()
                room = doc.get("rooms", {}).get(code)
                if room is not None:
                    awarded = bo.resolve(room, time.time())
                    if awarded:
                        repo.save(doc)
                    async with self:
                        self._refresh(room)
                await asyncio.sleep(2.0)
        finally:
            async with self:
                self.loop_running = False

    @rx.event
    def stop_watching(self):
        self.watching = False
