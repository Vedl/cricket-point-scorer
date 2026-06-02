"""Reflex state for the live auction room (Phase 3).

Thin wrapper over the shared :class:`RoomHub` + the pure ``auction_engine``:
  * a background ``live_loop`` polls the in-memory hub ~3x/sec, refreshes this
    session's display vars (so Reflex pushes deltas over the websocket), and
    drives timer resolution (auto-sell / auto-pass);
  * action handlers (bid, opt-out, admin start/pause/force/undo) mutate the hub
    engine under its async lock and let the loop broadcast the result.
"""

from __future__ import annotations

import asyncio
import time

import reflex as rx

from auction_engine import AuctionError, min_next_bid
from auction_engine.models import STATUS_IDLE, STATUS_PAUSED, STATUS_RUNNING

from .room_hub import RoomHub
from .state import AppState


def _build_view(engine, my_team: str, room: dict | None = None) -> dict:
    """Pure read of the engine into JSON-serialisable display data."""
    st = engine.state
    players = engine.players
    now = time.time()

    lobby = []
    if room is not None:
        for p in room.get("participants", []):
            lobby.append(
                {
                    "name": p["name"],
                    "claimed_by": p.get("user") or "",
                    "claimed": "yes" if p.get("user") else "no",
                    "squad": str(len(p.get("squad", []))),
                    "budget": str(p.get("budget", 0)),
                }
            )
    members_count = len(room.get("members", [])) if room else 0
    pool_count = len(engine.players)

    cur_id = st.current_player_id
    cur = players.get(cur_id) if cur_id else None

    participants = []
    for p in engine.participants.values():
        if p.id == st.current_bidder_id:
            status = "holding"
        elif p.id in st.opted_out:
            status = "out"
        else:
            status = "active"
        participants.append(
            {
                "name": p.name,
                "budget": str(p.budget),
                "squad": str(p.squad_size),
                "status": status,
                "is_me": "yes" if p.id == my_team else "no",
            }
        )

    log = []
    for e in engine.bid_log[-14:]:
        if e.kind == "bid":
            log.append({"text": f"💰 {e.participant_id} bid {e.amount}M on {e.player_name}"})
        elif e.kind == "sold":
            log.append({"text": f"🔨 SOLD {e.player_name} → {e.participant_id} for {e.amount}M"})
        elif e.kind == "unsold":
            log.append({"text": f"⏭️ UNSOLD {e.player_name}"})
    log.reverse()

    return {
        "status": st.status,
        "current_player": cur.name if cur else "",
        "current_role": cur.role if cur else "",
        "current_team": st.current_team or "",
        "current_bid": st.current_bid,
        "current_bidder": st.current_bidder_id or "",
        "time_left": int(engine.time_remaining(now)),
        "timer_total": engine.config.timer_seconds,
        "participants": participants,
        "log": log,
        "queue_count": len(st.queue),
        "can_undo": engine.can_undo,
        "min_bid": min_next_bid(st.current_bid, engine.config.starting_min_bid),
        "lobby": lobby,
        "members_count": members_count,
        "pool_count": pool_count,
    }


class RoomState(rx.State):
    room_code: str = ""
    room_name: str = ""
    tournament: str = ""
    is_admin: bool = False
    my_team: str = ""           # participant id (== team name) claimed by this user

    # live display (refreshed by the loop)
    status: str = STATUS_IDLE
    current_player: str = ""
    current_role: str = ""
    current_team: str = ""
    current_bid: int = 0
    current_bidder: str = ""
    time_left: int = 0
    timer_total: int = 60
    participants: list[dict[str, str]] = []
    log: list[dict[str, str]] = []
    queue_count: int = 0
    can_undo: bool = False
    min_bid: int = 5
    timer_pct: str = "100%"
    lobby: list[dict[str, str]] = []
    members_count: int = 0
    pool_count: int = 0

    # admin: team selection to start an auction
    teams_available: list[dict[str, str]] = []
    selected_team: str = ""

    # bidding form
    bid_amount: str = ""
    bid_as: str = ""            # who the bid is placed as (admin can choose)

    message: str = ""

    watching: bool = False
    loop_running: bool = False

    # ------------------------------------------------------------------ #
    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    @rx.var
    def can_bid(self) -> bool:
        return self.bid_as != "" and self.status == STATUS_RUNNING and self.current_player != ""

    @rx.var
    def is_running(self) -> bool:
        return self.status == STATUS_RUNNING

    @rx.var
    def is_paused(self) -> bool:
        return self.status == STATUS_PAUSED

    @rx.var
    def is_idle(self) -> bool:
        return self.status == STATUS_IDLE

    @rx.var
    def team_names(self) -> list[str]:
        return [p["name"] for p in self.participants]

    @rx.var
    def available_team_names(self) -> list[str]:
        return [t["team"] for t in self.teams_available]

    @rx.var
    def opted_out_names(self) -> list[str]:
        return [p["name"] for p in self.participants if p["status"] == "out"]

    # ------------------------------------------------------------------ #
    @rx.event
    async def on_load_room(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code = (self.router._page.params.get("room", "") or "").upper()
        room = RoomHub.room(code)
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.tournament = room.get("tournament_type", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.my_team = next(
            (p["name"] for p in room.get("participants", []) if p.get("user") == app.auth_user),
            "",
        )
        self.bid_as = self.my_team
        self.message = ""
        self._refresh_teams_available(code, room)
        self.watching = True
        if not self.loop_running:
            return RoomState.live_loop

    def _refresh_teams_available(self, code: str, room: dict):
        engine = RoomHub.engine(code)
        if engine is None:
            return
        drafted = engine._drafted_player_ids()
        counts: dict[str, int] = {}
        for pl in engine.players.values():
            if pl.id not in drafted:
                counts[pl.team] = counts.get(pl.team, 0) + 1
        self.teams_available = [
            {"team": t, "count": str(n)} for t, n in sorted(counts.items()) if n > 0
        ]
        if self.teams_available and not self.selected_team:
            self.selected_team = self.teams_available[0]["team"]

    # ------------------------------------------------------------------ #
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
                    my_team = self.my_team
                # Resolve timer expiry under the hub lock (idempotent across clients).
                engine = RoomHub.engine(code)
                if engine is not None:
                    if engine.pending_resolution(time.time()):
                        async with RoomHub.lock(code):
                            if engine.pending_resolution(time.time()):
                                engine.resolve(time.time())
                                RoomHub.persist(code)
                    view = _build_view(engine, my_team, RoomHub.room(code))
                    async with self:
                        self._apply_view(view)
                await asyncio.sleep(0.35)
        finally:
            async with self:
                self.loop_running = False

    def _apply_view(self, v: dict):
        self.status = v["status"]
        self.current_player = v["current_player"]
        self.current_role = v["current_role"]
        self.current_team = v["current_team"]
        self.current_bid = v["current_bid"]
        self.current_bidder = v["current_bidder"]
        self.time_left = v["time_left"]
        self.timer_total = v["timer_total"]
        self.participants = v["participants"]
        self.log = v["log"]
        self.queue_count = v["queue_count"]
        self.can_undo = v["can_undo"]
        self.min_bid = v["min_bid"]
        total = max(1, v["timer_total"])
        self.timer_pct = f"{max(0, min(100, int(v['time_left'] * 100 / total)))}%"
        self.lobby = v["lobby"]
        self.members_count = v["members_count"]
        self.pool_count = v["pool_count"]

    @rx.event
    def stop_watching(self):
        self.watching = False

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    async def _do(self, fn):
        """Run a hub mutation, capturing AuctionError into self.message."""
        try:
            await RoomHub.mutate(self.room_code, fn)
            self.message = ""
        except AuctionError as exc:
            self.message = f"⚠️ {exc}"
        except Exception as exc:  # pragma: no cover
            self.message = f"⚠️ {exc}"

    @rx.event
    async def start_team(self):
        team = self.selected_team
        await self._do(lambda e: e.start_team_auction(team, now=time.time()))
        self._refresh_teams_available(self.room_code, RoomHub.room(self.room_code))

    @rx.event
    async def place_bid(self):
        if not self.bid_as:
            self.message = "⚠️ No team selected to bid as."
            return
        try:
            amount = int(self.bid_amount)
        except (ValueError, TypeError):
            self.message = "⚠️ Enter a whole-number bid."
            return
        bidder = self.bid_as
        await self._do(lambda e: e.place_bid(bidder, amount, now=time.time()))
        self.bid_amount = ""

    @rx.event
    async def quick_bid(self):
        """Bid the minimum next increment as the current team."""
        bidder = self.bid_as
        await self._do(lambda e: e.place_bid(bidder, e_min(e), now=time.time()))

    @rx.event
    async def opt_out(self):
        bidder = self.bid_as
        await self._do(lambda e: e.opt_out(bidder))

    @rx.event
    async def revive(self, name: str):
        await self._do(lambda e: e.revive(name))

    @rx.event
    async def admin_force_sell(self):
        await self._do(lambda e: e.force_sell(now=time.time()))

    @rx.event
    async def admin_force_unsold(self):
        await self._do(lambda e: e.force_unsold(now=time.time()))

    @rx.event
    async def admin_pause(self):
        await self._do(lambda e: e.pause())

    @rx.event
    async def admin_resume(self):
        await self._do(lambda e: e.resume(now=time.time()))

    @rx.event
    async def admin_undo(self):
        await self._do(lambda e: e.undo())


def e_min(engine) -> int:
    """Minimum next bid for the engine's current state."""
    from auction_engine import min_next_bid

    return min_next_bid(engine.state.current_bid, engine.config.starting_min_bid)
