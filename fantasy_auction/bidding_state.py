"""Open-bidding state — deadline-driven, frozen until the admin sets a deadline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import reflex as rx

from platform_core import bidding_ops as bo
from platform_core import season_ops as so
from season_engine.open_bidding import BidError

from .state import AppState, repo

_WINDOW_LABEL = {
    "frozen": "🔒 Frozen — waiting for the admin to set a deadline",
    "open": "🟢 Open — bid on new players or raise",
    "no_new": "🟡 Closing soon — raise existing bids only (no new players)",
    "raise_only": "🟠 Final window — raise existing bids in +5M steps only",
    "closed": "🔴 Closed — bids being awarded",
}


def _countdown(when, now) -> str:
    secs = int((when - now).total_seconds())
    if secs <= 0:
        return "passed"
    return when.isoformat()


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
    window: str = "frozen"
    window_label: str = ""
    deadline_str: str = ""
    milestones: list[dict[str, str]] = []
    all_available_players: list[dict[str, str]] = []
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
        awarded = bo.process_expired(room, datetime.now())
        if awarded:
            repo.save(doc)
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
        self.all_available_players = [
            {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")} 
            for p in bo.available_players(room, limit=1000)
        ]
        now = datetime.now()
        
        self.active = []
        for b in bo.active(room):
            expires_iso = b.get("expires", "")
            time_left = ""
            if expires_iso:
                try:
                    time_left = _countdown(datetime.fromisoformat(expires_iso), now)
                except Exception:
                    pass
            self.active.append({
                "player": b["player"], "team": b["team"], "role": b.get("role", ""), "high_bid": str(b["high_bid"]),
                "high_bidder": b["high_bidder"], "expires": expires_iso, "time_left": time_left,
                "mine": "yes" if b["high_bidder"] == self.my_team else "no"
            })
        self.window = bo.window_state(room, now)
        self.window_label = _WINDOW_LABEL.get(self.window, "")
        dl = bo.bidding_deadline(room)
        self.deadline_str = dl.strftime("%a %d %b, %H:%M") if dl else ""
        if dl:
            self.milestones = [
                {"label": "🆕 New-player bids close", "left": _countdown(dl - timedelta(minutes=60), now)},
                {"label": "5️⃣ +5M-only window starts", "left": _countdown(dl - timedelta(minutes=30), now)},
                {"label": "🔨 Bidding closes (bids award)", "left": _countdown(dl, now)},
                {"label": "🔒 Trading closes → squads lock + new GW", "left": _countdown(dl + timedelta(minutes=30), now)},
            ]
        else:
            self.milestones = []

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
            bo.place(room, self.my_team, self.bid_player, int(self.bid_amount or 0), datetime.now())
        except (BidError, ValueError) as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self.bid_amount = ""
        self._refresh(room)
        self.msg = f"✅ Bid placed on {self.bid_player}."

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
                # Cheap per-room read (~20-50 KB), served from the 20s cache most
                # ticks, instead of the ~1 MB full doc — and NO write here (the
                # server-side scheduler thread owns deadline processing/locking).
                # This keeps Firebase egress tiny even if a tab is left open.
                room = repo.load_room(code)
                if room is not None:
                    now = datetime.now()
                    now_iso = now.isoformat()
                    has_expired = any(now_iso >= b.get("expires", now_iso) for b in room.get("open_bids", {}).values())
                    if has_expired:
                        _, doc, full_room = self._load()
                        if full_room:
                            if bo.process_expired(full_room, now):
                                repo.save(doc)
                            room = full_room
                            
                    async with self:
                        self._refresh(room)
                await asyncio.sleep(6)
        finally:
            async with self:
                self.loop_running = False

    @rx.event
    def stop_watching(self):
        self.watching = False
