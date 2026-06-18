"""Reflex state for standings + gameweek management (Phase 8)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import reflex as rx

from platform_core import scoring_ops
from platform_core import season_ops as so

from .state import AppState, aload, repo

# "Calculate points" scrapes WhoScored and fits the sklearn keeper model. Run inside
# this long-lived web process that work loads curl_cffi / cloudscraper / tls_client
# (native TLS), pandas and sklearn into the heap AND holds several multi-MB match
# pages — a resident footprint that never returns to the OS on the 512 MB box, so
# after one run every request for every user is slow until a redeploy. We instead run
# it in a short-lived CHILD process (see scripts/score_links_worker.py) that exits
# when done, so the kernel reclaims all of that memory. The web process only handles
# lightweight JSON progress/results.
_SCORE_WORKER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "score_links_worker.py",
)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Standings are identical for every viewer of a room/gameweek, but each client's
# loop recomputed them independently. Cache the computed payload process-wide with
# a short TTL so N concurrent viewers share ONE compute instead of N.
_STANDINGS_CACHE: dict = {}      # (code, selected_gw) -> (monotonic_ts, data, current_gw, gameweeks)
_STANDINGS_TTL = 8.0


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
    scoring_failed: list[str] = [] # match labels WhoScored blocked this run
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
                    key = (code, selected_gw)
                    cached = _STANDINGS_CACHE.get(key)
                    if cached and (time.monotonic() - cached[0]) < _STANDINGS_TTL:
                        _, data, cur_gw, gws = cached
                    else:
                        # load_room is served from the in-memory snapshot (~0.6ms),
                        # so it's cheap enough to call directly without a thread.
                        room = await asyncio.to_thread(repo.load_room, code)
                        if room is None:
                            await asyncio.sleep(12)
                            continue
                        data = await asyncio.to_thread(
                            self._compute_standings_data, room, selected_gw)
                        cur_gw = str(room.get("current_gameweek", 0) or 0)
                        gws = so.gameweeks_with_scores(room)
                        _STANDINGS_CACHE[key] = (time.monotonic(), data, cur_gw, gws)
                        # Drop stale entries so the cache can't grow unbounded.
                        for k in [k for k, v in _STANDINGS_CACHE.items()
                                  if time.monotonic() - v[0] > 60]:
                            _STANDINGS_CACHE.pop(k, None)
                    async with self:
                        self.current_gameweek = cur_gw
                        self.gameweeks = gws
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
            self.scoring_failed = []
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
        # Scrape + score in a SHORT-LIVED CHILD PROCESS (see _SCORE_WORKER note at
        # top of file). The child loads the whole heavy stack (curl_cffi, cloudscraper,
        # tls_client, pandas, the sklearn keeper model) and holds the multi-MB match
        # pages; when it exits, the kernel reclaims all of it — so a scoring run can no
        # longer leave the 512 MB web process bloated and laggy for everyone. It is
        # also network-bound, so the worker scrapes a few matches at once (bounded) and
        # streams per-match progress back as NDJSON, preserving the live progress bar.
        is_football = scoring_ops.is_football_room(room)
        countries = scoring_ops.fifa_countries(room) if is_football else []
        totals: dict = {}
        failed: list[str] = []
        n = len(links)
        payload = json.dumps(
            {"links": links, "is_football": is_football, "countries": countries})
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, _SCORE_WORKER,
                cwd=_REPO_ROOT,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            proc.stdin.write(payload.encode())
            await proc.stdin.drain()
            proc.stdin.close()
            # Stream the worker's NDJSON: progress lines drive the bar, the result line
            # carries the merged totals + the matches WhoScored blocked this run.
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                except ValueError:
                    continue
                if msg.get("t") == "progress":
                    done = int(msg.get("done", 0))
                    async with self:
                        self.scoring_done = done
                        self.scoring_pct = int(done * 100 / max(1, n))
                        self.scoring_status = f"Scraped {done}/{n} matches…"
                elif msg.get("t") == "result":
                    totals = msg.get("totals") or {}
                    failed = list(msg.get("failed") or [])
            await proc.wait()
            if proc.returncode and not totals:
                err = (await proc.stderr.read()).decode(errors="replace")[-400:]
                print(f"[run_whoscored_scoring] worker exit {proc.returncode}: {err}")
        except Exception as exc:
            print(f"[run_whoscored_scoring] worker failed: {exc}")
        if totals:
            so.set_gameweek_scores(room, gw, totals)
            repo.save(doc)
        async with self:
            self.scoring_running = False
            self.scoring_status = ""
            self.scoring_pct = 0
            self.scoring_failed = failed
            ok = n - len(failed)
            if totals:
                self.selected_gw = str(gw)
                self.gameweeks = so.gameweeks_with_scores(room)
                self._recompute(room)
                self.msg = f"✅ Scored {len(totals)} players for GW{gw} from {ok}/{n} match(es)."
            else:
                self.msg = "⚠️ No scores scraped — every match link failed."
            if failed:
                self.msg += (f"  ⚠️ {len(failed)} match(es) blocked by WhoScored — "
                             "listed below. Click Compute again to retry just those "
                             "(already-scraped matches are cached and instant).")

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
