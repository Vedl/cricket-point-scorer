"""Room hub state — replaces the (removed) in-app live auction.

The live auction now happens off-app (Zoom); the hub shows the participant's own
team (budget, squad, IR) and every other team at a glance, plus IR selection and
half-price releases.
"""

from __future__ import annotations

import reflex as rx

from platform_core import season_ops as so
from platform_core.season_ops import SeasonError

from .state import AppState, repo


class RoomState(rx.State):
    room_code: str = ""
    room_name: str = ""
    tournament: str = ""
    is_admin: bool = False
    my_team: str = ""

    my_budget: int = 0
    my_squad: list[dict[str, str]] = []
    my_ir: str = ""
    teams: list[dict[str, str]] = []
    current_gameweek: str = "0"
    gw1_locked: bool = False
    next_deadline: str = ""
    msg: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_hub(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code, doc, room = self._load()
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.tournament = room.get("tournament_type", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.my_team = next((p["name"] for p in room.get("participants", [])
                             if p.get("user") == app.auth_user), "")
        self.current_gameweek = str(room.get("current_gameweek", 0) or 0)
        self.gw1_locked = bool(room.get("gw1_locked"))
        self._refresh(room)

    def _refresh(self, room: dict):
        by = {p["name"]: p for p in room.get("participants", [])}
        me = by.get(self.my_team, {})
        self.my_budget = me.get("budget", 0)
        self.my_ir = me.get("ir") or ""
        self.my_squad = [
            {"name": e["name"], "role": e.get("role", ""), "team": e.get("team", ""),
             "price": str(e.get("buy_price", 0)),
             "ir": "yes" if e["name"] == me.get("ir") else "no"}
            for e in sorted(me.get("squad", []), key=lambda x: -x.get("buy_price", 0))
        ]
        self.teams = [
            {"name": p["name"], "budget": str(p.get("budget", 0)),
             "squad": str(len(p.get("squad", []))),
             "status": "out" if p.get("is_eliminated") else "in",
             "is_me": "yes" if p["name"] == self.my_team else "no"}
            for p in room.get("participants", [])
        ]
        # nearest upcoming deadline
        ds = sorted(room.get("gameweek_deadlines", {}).items())
        locked = room.get("gameweek_squads", {})
        self.next_deadline = next((f"GW{gw}: {iso[:16].replace('T', ' ')}"
                                   for gw, iso in ds if gw not in locked), "")

    @rx.event
    def set_ir(self, player: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            so.set_ir(room, self.my_team, player)
        except SeasonError as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self._refresh(room)
        self.msg = f"🩹 IR set to {player}."

    @rx.event
    def clear_ir(self):
        code, doc, room = self._load()
        if not room:
            return
        so.set_ir(room, self.my_team, None)
        repo.save(doc)
        self._refresh(room)
        self.msg = "IR cleared."

    @rx.event
    def half_release(self, player: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            refund = so.half_price_release(room, self.my_team, player)
        except SeasonError as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self._refresh(room)
        self.msg = f"🗑️ Released {player} for +{refund}M (half price)."
