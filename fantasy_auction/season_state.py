"""Reflex state for standings + gameweek management (Phase 8)."""

from __future__ import annotations

import reflex as rx

from platform_core import season_ops as so

from .state import AppState, repo


class SeasonState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    current_gameweek: str = "0"

    cumulative: list[dict[str, str]] = []
    gameweeks: list[str] = []
    selected_gw: str = ""
    gw_standings: list[dict[str, str]] = []

    # admin gameweek tools
    gw_input: str = "1"
    scores_text: str = ""
    msg: str = ""

    # knockout
    eliminated: list[str] = []
    knockout_count: str = "1"

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load_room(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_standings(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code, doc, room = self._load_room()
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.current_gameweek = str(room.get("current_gameweek", 0) or 0)
        self.gameweeks = so.gameweeks_with_scores(room)
        if not self.selected_gw and self.gameweeks:
            self.selected_gw = self.gameweeks[-1]
        self._recompute(room)

    def _recompute(self, room: dict):
        self.eliminated = sorted(so.eliminated_names(room))
        elim = set(self.eliminated)
        self.cumulative = [
            {"participant": r["participant"] + (" ❌" if r["participant"] in elim else ""),
             "points": str(r["points"])}
            for r in so.compute_cumulative_standings(room)
        ]
        if self.selected_gw:
            self.gw_standings = [
                {"participant": r["participant"], "points": str(r["points"]),
                 "warn": "⚠️" if r.get("warnings") else ""}
                for r in so.compute_gameweek_standings(room, self.selected_gw)
            ]
        else:
            self.gw_standings = []

    @rx.event
    def select_gw(self, gw: str):
        self.selected_gw = gw
        _, _, room = self._load_room()
        if room:
            self._recompute(room)

    @rx.event
    def save_scores(self):
        self.msg = ""
        scores, errors = so.parse_scores_text(self.scores_text)
        if errors:
            self.msg = "⚠️ " + " ".join(errors[:3])
            return
        if not scores:
            self.msg = "⚠️ No scores entered."
            return
        code, doc, room = self._load_room()
        if not room:
            return
        so.set_gameweek_scores(room, self.gw_input, scores)
        repo.save(doc)
        self.selected_gw = str(self.gw_input)
        self.gameweeks = so.gameweeks_with_scores(room)
        self._recompute(room)
        self.msg = f"✅ Saved {len(scores)} scores for GW{self.gw_input}."

    @rx.event
    def lock_squads(self):
        code, doc, room = self._load_room()
        if not room:
            return
        so.lock_squads_for_gameweek(room, self.gw_input)
        repo.save(doc)
        self.msg = f"🔒 Locked squads for GW{self.gw_input}."

    @rx.event
    def advance_gw(self):
        code, doc, room = self._load_room()
        if not room:
            return
        gw = so.advance_gameweek(room)
        repo.save(doc)
        self.current_gameweek = str(gw)
        self.msg = f"⏭️ Advanced to GW{gw}."

    @rx.event
    def do_eliminate(self):
        self.msg = ""
        if not self.selected_gw:
            self.msg = "⚠️ Select a gameweek with scores first."
            return
        code, doc, room = self._load_room()
        if not room:
            return
        try:
            count = max(1, int(self.knockout_count or 1))
        except ValueError:
            count = 1
        losers = so.eliminate_for_gameweek(room, self.selected_gw, count)
        repo.save(doc)
        self._recompute(room)
        self.msg = (f"❌ Eliminated: {', '.join(losers)}" if losers
                    else "No active participants to eliminate.")

    @rx.event
    def run_knockout_round(self, keep_top: int):
        """FIFA-style: keep top N, eliminate the rest, free their players to market."""
        self.msg = ""
        if not self.selected_gw:
            self.msg = "⚠️ Select a gameweek with scores first."
            return
        code, doc, room = self._load_room()
        if not room:
            return
        elim, released = so.eliminate_below_position(room, self.selected_gw, int(keep_top))
        repo.save(doc)
        self._recompute(room)
        if elim:
            self.msg = (f"❌ Eliminated {', '.join(elim)} · released {len(released)} "
                        f"players to the open market for the next round.")
        else:
            self.msg = "No teams below the cutoff — nobody eliminated."

    @rx.event
    def reverse_elimination(self):
        code, doc, room = self._load_room()
        if not room:
            return
        restored = so.reverse_last_elimination(room)
        repo.save(doc)
        self._recompute(room)
        self.msg = (f"↩️ Restored: {', '.join(restored)}" if restored
                    else "Nothing to reverse.")
