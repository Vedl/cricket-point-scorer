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
    scoring_done: int = 0          # matches scraped so far
    scoring_total: int = 0         # matches to scrape this run
    scoring_pct: int = 0           # 0-100 for the progress bar
    scoring_status: str = ""       # live "Scraped 3/24…" line
    # Self-healing refresh (see RoomState.watching): repopulate standings after a
    # reconnect / free-tier restart instead of staying blank.
    watching: bool = False
    loop_running: bool = False

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
        # Break as soon as inputs are ready (usually instant). Don't wait on
        # is_hydrated — it's set only after on_load finishes, so waiting on it just
        # burned ~5s per load. See RoomState.on_load_hub for the full explanation.
        code = ""
        for _ in range(60):
            code = (self.router._page.params.get("room", "") or "").upper()
            if code and (app.auth_user or app.is_hydrated):
                break
            await asyncio.sleep(0.05)
        if not app.auth_user and not app.spectating:
            return rx.redirect("/")
        if not code:
            return
        try:
            doc = await aload()
            room = doc.get("rooms", {}).get(code)
            if room is None:
                return rx.redirect("/rooms") if app.auth_user else rx.redirect("/")
            self.room_code = code
            self.room_name = room.get("name", "")
            self.is_admin = room.get("admin") == app.auth_user
            self.current_gameweek = str(room.get("current_gameweek", 0) or 0)
            self.gameweeks = so.gameweeks_with_scores(room)
            if not self.selected_gw and self.gameweeks:
                self.selected_gw = self.gameweeks[-1]
            self._recompute(room)
        except Exception as exc:
            print(f"[on_load_standings] {exc}")
        self.watching = True
        if not self.loop_running:
            return SeasonState.standings_loop

    @rx.event(background=True)
    async def standings_loop(self):
        """Repopulate standings periodically so the table comes back after a reconnect
        or free-tier restart (the page has no other live updater)."""
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
                try:
                    async with self:
                        selected_gw = self.selected_gw
                    room = await asyncio.to_thread(repo.load_room, code)
                    if room is not None:
                        # Compute off the event loop: the Best-11 search is CPU-heavy,
                        # so doing it here (not under `async with self`) keeps a slow
                        # tick from blocking other users or pegging the worker.
                        data = await asyncio.to_thread(
                            self._compute_standings_data, room, selected_gw)
                        async with self:
                            self.current_gameweek = str(room.get("current_gameweek", 0) or 0)
                            self.gameweeks = so.gameweeks_with_scores(room)
                            self._assign_standings(data)
                except Exception as exc:
                    print(f"[standings_loop] tick failed, continuing: {exc}")
                await asyncio.sleep(12)
        finally:
            async with self:
                self.loop_running = False

    @rx.event
    def stop_watching(self):
        self.watching = False

    @staticmethod
    def _compute_standings_data(room: dict, selected_gw: str) -> dict:
        """Pure computation of everything _recompute assigns. No ``self`` access, so
        it can run in a worker thread (asyncio.to_thread) and keep the heavy Best-11
        search off the event loop / state lock — a slow tick must never block other
        users or peg the worker."""
        eliminated = sorted(so.eliminated_names(room))
        elim = set(eliminated)
        cumulative = [
            {"participant": r["participant"] + (" ❌" if r["participant"] in elim else ""),
             "points": str(r["points"])}
            for r in so.compute_cumulative_standings(room)
        ]
        gw_standings: list[dict] = []
        best11_cache: dict = {}
        if selected_gw:
            standings = so.compute_gameweek_standings(room, selected_gw)
            gw_standings = [
                {"participant": r["participant"], "points": str(r["points"]),
                 "warn": "⚠️" if r.get("warnings") else ""}
                for r in standings
            ]
            # Show each Best-11 in formation order: GK, DEF, MID, FWD (cricket:
            # WK, BAT, AR, BWL), highest scorer first within each line.
            pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3,
                         "WK": 0, "BAT": 1, "AR": 2, "BWL": 3}
            best11_cache = {
                r["participant"]: [
                    {"name": p["name"], "role": p.get("category", p.get("role", "")), "score": str(p["score"])}
                    for p in sorted(
                        r.get("best_11", []),
                        key=lambda p: (pos_order.get(p.get("category", ""), 9), -p["score"]),
                    )
                ] for r in standings
            }
        top_scorers = [
            {"player": r["player"], "points": str(r["points"]), "owner": r["owner"]}
            for r in so.top_player_scorers(room, limit=20)
        ]
        locked = room.get("gameweek_squads", {})
        deadlines = [
            {"gw": gw, "when": iso[:16].replace("T", " "),
             "status": "locked" if gw in locked else "scheduled"}
            for gw, iso in sorted(room.get("gameweek_deadlines", {}).items())
        ]
        return {
            "eliminated": eliminated, "cumulative": cumulative,
            "gw_standings": gw_standings, "best11_cache": best11_cache,
            "top_scorers": top_scorers, "deadlines": deadlines,
        }

    def _assign_standings(self, data: dict):
        self.eliminated = data["eliminated"]
        self.cumulative = data["cumulative"]
        self.gw_standings = data["gw_standings"]
        self._gw_best11_cache = data["best11_cache"]
        self.top_scorers = data["top_scorers"]
        self.deadlines = data["deadlines"]

    def _recompute(self, room: dict):
        self._assign_standings(self._compute_standings_data(room, self.selected_gw))

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
            self.scoring_total = len(links)
            self.scoring_done = 0
            self.scoring_pct = 0
            self.scoring_status = f"Starting… 0/{len(links)} matches"
        if not links:
            async with self:
                self.scoring_running = False
                self.scoring_status = ""
                self.msg = "⚠️ Paste at least one WhoScored match link."
            return
        doc = repo.load()
        room = doc.get("rooms", {}).get(code)
        if room is None:
            async with self:
                self.scoring_running = False
                self.scoring_status = ""
            return
        # Scrape one match at a time so the admin sees live progress — 24 matches
        # through the proxy fallback can take many minutes, and a single opaque
        # "Scraping…" spinner gave no sign it was alive.
        is_football = scoring_ops.is_football_room(room)
        countries = scoring_ops.fifa_countries(room) if is_football else []
        totals: dict = {}
        errors: list[str] = []
        for i, url in enumerate(links, start=1):
            try:
                one = await asyncio.to_thread(
                    scoring_ops.score_one_link, url, is_football=is_football, countries=countries)
                scoring_ops.merge_link_totals(totals, one)
            except Exception as exc:  # network / bot-block / parse
                errors.append(f"{url[:60]}…: {exc}")
            async with self:
                self.scoring_done = i
                self.scoring_pct = int(i * 100 / max(1, len(links)))
                self.scoring_status = f"Scraped {i}/{len(links)} matches…"
        if totals:
            so.set_gameweek_scores(room, gw, totals)
            repo.save(doc)
        async with self:
            self.scoring_running = False
            self.scoring_status = ""
            self.scoring_pct = 0
            if totals:
                self.selected_gw = str(gw)
                self.gameweeks = so.gameweeks_with_scores(room)
                self._recompute(room)
                self.msg = (f"✅ Scored {len(totals)} players for GW{gw} from "
                            f"{len(links) - len(errors)}/{len(links)} match(es).")
            else:
                self.msg = "⚠️ No scores scraped — every match link failed."
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
