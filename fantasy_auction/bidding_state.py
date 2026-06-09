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

    def _refresh(self, room: dict, *, full: bool = True):
        """Recompute view state from ``room``.

        ``full`` rebuilds the big autocomplete datalist (up to 1000 players). The
        per-client ``live_loop`` ticks every few seconds for every connected tab, so
        it passes ``full=False``: rebuilding and diffing a 1000-row list on every tick
        across all clients was a major CPU drain on the single-CPU free VM (it starved
        the event loop → hangs). The datalist only changes when players are acquired/
        released, so it's refreshed on load and on user actions (search/bid) instead."""
        by = {p["name"]: p for p in room.get("participants", [])}
        new_my_budget = by.get(self.my_team, {}).get("budget", 0)
        if self.my_budget != new_my_budget:
            self.my_budget = new_my_budget

        new_available = [
            {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
            for p in bo.available_players(room, search=self.search, limit=50)
        ]
        if self.available != new_available:
            self.available = new_available

        if full:
            new_all_available = [
                {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                for p in bo.available_players(room, limit=1000)
            ]
            if self.all_available_players != new_all_available:
                self.all_available_players = new_all_available

        now = datetime.now()
        
        new_active = []
        for b in bo.active(room):
            expires_iso = b.get("expires", "")
            time_left = ""
            if expires_iso:
                try:
                    time_left = _countdown(datetime.fromisoformat(expires_iso), now)
                except Exception:
                    pass
            new_active.append({
                "player": b["player"], "team": b["team"], "role": b.get("role", ""), "high_bid": str(b["high_bid"]),
                "high_bidder": b["high_bidder"], "expires": expires_iso, "time_left": time_left,
                "mine": "yes" if b["high_bidder"] == self.my_team else "no"
            })
        if self.active != new_active:
            self.active = new_active
            
        new_window = bo.window_state(room, now)
        if self.window != new_window:
            self.window = new_window
            self.window_label = _WINDOW_LABEL.get(self.window, "")
            
        dl = bo.bidding_deadline(room)
        new_deadline_str = dl.strftime("%a %d %b, %H:%M") if dl else ""
        if self.deadline_str != new_deadline_str:
            self.deadline_str = new_deadline_str
            
        if dl:
            new_milestones = [
                {"label": "🆕 New-player bids close", "left": _countdown(dl - timedelta(minutes=60), now)},
                {"label": "5️⃣ +5M-only window starts", "left": _countdown(dl - timedelta(minutes=30), now)},
                {"label": "🔨 Bidding closes (bids award)", "left": _countdown(dl, now)},
                {"label": "🔒 Trading closes → squads lock + new GW", "left": _countdown(dl + timedelta(minutes=30), now)},
            ]
        else:
            new_milestones = []
            
        if self.milestones != new_milestones:
            self.milestones = new_milestones

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
                        # Skip the heavy 1000-row datalist rebuild on every tick.
                        self._refresh(room, full=False)
                await asyncio.sleep(6)
        finally:
            async with self:
                self.loop_running = False

    @rx.event
    def stop_watching(self):
        self.watching = False
