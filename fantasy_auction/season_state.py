"""Reflex state for standings + gameweek management (Phase 8)."""

from __future__ import annotations

import asyncio

import reflex as rx

from platform_core import scoring_ops
from platform_core import season_ops as so

from .state import AppState, aload, repo


class SeasonState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    current_gameweek: str = "0"

    cumulative: list[dict[str, str]] = []
    gameweeks: list[str] = []
    selected_gw: str = ""
    gw_standings: list[dict[str, str]] = []
    _gw_best11_cache: dict = {}
    
    # best 11 modal
    show_best11_modal: bool = False
    best11_team_name: str = ""
    best11_players: list[dict[str, str]] = []
    best11_total: str = ""

    # admin gameweek tools
    gw_input: str = "1"
    gw_options: list[str] = [str(i) for i in range(1, 16)]   # dropdown: GW 1..15
    scores_text: str = ""
    msg: str = ""

    # knockout
    eliminated: list[str] = []
    knockout_count: str = "1"

    # top scorers + deadlines
    top_scorers: list[dict[str, str]] = []
    deadline_gw: str = "1"
    deadline_value: str = ""        # ISO-ish datetime-local string
    deadlines: list[dict[str, str]] = []
    bidding_deadline_value: str = ""
    bidding_deadline_str: str = ""
    # WhoScored auto-scoring
    score_links: str = ""
    scoring_running: bool = False

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
        for _ in range(100):
            if app.is_hydrated:
                break
            await asyncio.sleep(0.05)
        if not app.auth_user:
            return rx.redirect("/")
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = await aload()
        room = doc.get("rooms", {}).get(code)
        if not code:
            return
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
            standings = so.compute_gameweek_standings(room, self.selected_gw)
            self.gw_standings = [
                {"participant": r["participant"], "points": str(r["points"]),
                 "warn": "⚠️" if r.get("warnings") else ""}
                for r in standings
            ]
            self._gw_best11_cache = {
                r["participant"]: [
                    {"name": p["name"], "role": p.get("category", p.get("role", "")), "score": str(p["score"])}
                    for p in r.get("best_11", [])
                ] for r in standings
            }
        else:
            self.gw_standings = []
        self.top_scorers = [
            {"player": r["player"], "points": str(r["points"]), "owner": r["owner"]}
            for r in so.top_player_scorers(room, limit=20)
        ]
        locked = room.get("gameweek_squads", {})
        self.deadlines = [
            {"gw": gw, "when": iso[:16].replace("T", " "),
             "status": "locked" if gw in locked else "scheduled"}
            for gw, iso in sorted(room.get("gameweek_deadlines", {}).items())
        ]

    @rx.event
    def select_gw(self, gw: str):
        self.selected_gw = gw
        _, _, room = self._load_room()
        if room:
            self._recompute(room)

    @rx.event
    def open_best11(self, team_name: str):
        self.best11_team_name = team_name
        self.best11_players = self._gw_best11_cache.get(team_name, [])
        for row in self.gw_standings:
            if row["participant"] == team_name:
                self.best11_total = row["points"]
                break
        self.show_best11_modal = True

    @rx.event
    def close_best11(self):
        self.show_best11_modal = False

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
    def save_bidding_deadline(self):
        self.msg = ""
        if not self.bidding_deadline_value:
            self.msg = "⚠️ Pick a date & time for the bidding deadline."
            return
        code, doc, room = self._load_room()
        if not room:
            return
        so.set_bidding_deadline(room, self.bidding_deadline_value)
        repo.save(doc)
        self.bidding_deadline_str = self.bidding_deadline_value.replace("T", " ")
        self.msg = ("⏰ Deadline set. Bidding opens now; new players until −1h, raise-only "
                    "(+5M) in the final 30m, bids award at the deadline, trading until +30m, "
                    "then squads auto-lock and the next gameweek starts.")

    @rx.event(background=True)
    async def run_whoscored_scoring(self):
        async with self:
            if self.scoring_running:
                return
            self.scoring_running = True
            self.msg = ""
            gw = self.gw_input
            links = scoring_ops.parse_links(self.score_links)
            code = self.room_code
        if not links:
            async with self:
                self.scoring_running = False
                self.msg = "⚠️ Paste at least one WhoScored match link."
            return
        doc = repo.load()
        room = doc.get("rooms", {}).get(code)
        if room is None:
            async with self:
                self.scoring_running = False
            return
        totals, errors = await asyncio.to_thread(
            scoring_ops.score_gameweek_from_links, room, gw, links)
        if totals:
            repo.save(doc)
        async with self:
            self.scoring_running = False
            if totals:
                self.selected_gw = str(gw)
                self.gameweeks = so.gameweeks_with_scores(room)
                self._recompute(room)
                self.msg = (f"✅ Scored {len(totals)} players for GW{gw} from "
                            f"{len(links)} match(es).")
            if errors:
                self.msg += "  ⚠️ " + " | ".join(errors[:2])

    @rx.event
    def save_deadline(self):
        self.msg = ""
        if not self.deadline_value:
            self.msg = "⚠️ Pick a date & time."
            return
        code, doc, room = self._load_room()
        if not room:
            return
        so.set_deadline(room, self.deadline_gw, self.deadline_value)
        repo.save(doc)
        self._recompute(room)
        self.msg = (f"⏰ GW{self.deadline_gw} deadline set — squads auto-lock & the next "
                    f"gameweek starts then.")

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
