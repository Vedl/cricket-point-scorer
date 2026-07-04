"""Reflex application state for auth + room setup (Phases 2 & 4 entry).

State classes are thin: they call the pure ``platform_core`` repository/auth/CSV
helpers, persist via the Firebase-backed store, and expose display vars. No
business rules live here.
"""

from __future__ import annotations

import asyncio
import os

import reflex as rx


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency) so the backend picks up
    Firebase config regardless of how it's launched."""
    paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        "/etc/secrets/firebase",
        "/etc/secrets/.env",
    ]
    for path in paths:
        if not os.path.exists(path):
            continue
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()


def _set_timezone() -> None:
    """Run the whole backend on the league's timezone (default IST) so naive
    deadline inputs, ``datetime.now()`` comparisons and countdowns all agree.
    Without this the cloud host runs in UTC and auto-locks fire hours off."""
    import time
    os.environ.setdefault("TZ", os.environ.get("APP_TZ", "Asia/Kolkata"))
    try:
        time.tzset()
    except AttributeError:  # pragma: no cover - non-Unix
        pass


_set_timezone()

from platform_core.auth import AuthError, log_in, reset_password, sign_up
from platform_core.config_layer import TOURNAMENTS, load_player_pool
from platform_core.csv_import import parse_squad_csv
from platform_core.csv_review import build_review
from platform_core.repository import (
    Repository,
    RepositoryError,
    apply_pool_import,
    apply_reviewed_roster,
)

# One repository for the process; the store reads Firebase config from env and
# falls back to a local JSON file when unset (see PLAN.md §6.6).
repo = Repository()
# Cache warm happens in hf_start.sh (before reflex binds its port), not at import
# time — see firebase_store.warm_cache().


async def aload() -> dict:
    """Non-blocking ``repo.load()`` for async event handlers.

    A synchronous Firebase/JSON read inside a Reflex handler blocks the asyncio
    loop and can drop the websocket heartbeat, leaving users on "connecting…"."""
    return await asyncio.to_thread(repo.load)


class AppState(rx.State):
    # --- session (persisted across reloads) ---
    auth_user: str = rx.LocalStorage("")
    # The active room's tournament — drives per-room theming across pages.
    active_tournament: str = rx.LocalStorage("")

    # --- spectator session (read-only guests invited via an admin link) ---
    # A spectator opens /room?room=CODE&spectate=TOKEN; the token is validated against
    # the room and remembered so they can browse every view tab read-only. Logged-in
    # members/admins are never spectators.
    spectator_token: str = rx.LocalStorage("")
    spectator_room: str = rx.LocalStorage("")
    spectating: bool = rx.LocalStorage(False)

    # --- auth form ---
    username: str = ""
    password: str = ""
    confirm: str = ""
    auth_error: str = ""

    # --- reset password form ---
    reset_username: str = ""
    reset_room_code: str = ""
    reset_new_pw: str = ""
    reset_confirm: str = ""
    reset_msg: str = ""

    # --- create room form ---
    new_room_name: str = ""
    new_tournament: str = TOURNAMENTS[0]
    admin_participating: bool = False
    create_error: str = ""

    # --- join form ---
    join_code: str = ""
    join_team: str = ""
    join_pin: str = ""
    join_error: str = ""

    # --- dashboard ---
    my_rooms: list[dict[str, str]] = []

    # --- room setup (admin) ---
    room_code: str = ""
    room_name: str = ""
    room_tournament: str = ""
    is_admin: bool = False
    teams: list[dict[str, str]] = []
    new_team_name: str = ""
    new_team_pin: str = ""
    claim_choice: str = ""
    setup_msg: str = ""
    upload_msg: str = ""
    pool_count: int = 0
    # CSV review / staging (candidates parallel-indexed with import_rows)
    import_rows: list[dict[str, str]] = []
    import_candidates: list[list[str]] = []
    import_budgets: list[dict[str, str]] = []
    import_unmatched: int = 0

    tournaments: list[str] = list(TOURNAMENTS)

    # ------------------------------------------------------------------ #
    # Computed
    # ------------------------------------------------------------------ #
    @rx.var
    def logged_in(self) -> bool:
        return self.auth_user != ""

    # ------------------------------------------------------------------ #
    # Spectator access (read-only guests)
    # ------------------------------------------------------------------ #
    def grant_spectator_if_valid(self, code: str, room: Optional[dict], spectate_param: str) -> bool:
        """Return True if this session is a valid read-only spectator for ``code``.

        Honours a ``?spectate=TOKEN`` URL param (granting + persisting the token) and a
        previously granted token kept in LocalStorage. Revoking the room's token (admin)
        invalidates any stored spectator session. Mutates the persisted spectator vars
        as a side effect, so call it from an event handler (e.g. a page on_load)."""
        code = (code or "").upper()
        room = room or {}
        # A logged-in member or admin of this room is ALWAYS a full participant —
        # never a spectator — even if a stale spectator token lingers in LocalStorage
        # (e.g. they once opened a spectator link). Clear any stale session and bail.
        if self.auth_user:
            is_member = (room.get("admin") == self.auth_user or
                         any(p.get("user") == self.auth_user
                             for p in room.get("participants", [])))
            if is_member:
                if self.spectator_room == code:
                    self.spectator_token = ""
                    self.spectator_room = ""
                    self.spectating = False
                return False
        tok = room.get("spectator_token") or ""
        if not tok:
            if self.spectator_room == code:           # token was revoked → drop session
                self.spectator_token = ""
                self.spectating = False
            return False
        if spectate_param and spectate_param == tok:  # arriving via a fresh invite link
            # Guarded: this runs on every live-loop tick for spectators, and
            # re-assigning a LocalStorage var marks it dirty (a delta per tick).
            if self.spectator_token != tok:
                self.spectator_token = tok
            if self.spectator_room != code:
                self.spectator_room = code
            if not self.spectating:
                self.spectating = True
            return True
        ok = self.spectator_token == tok and self.spectator_room == code
        if ok and not self.spectating:
            self.spectating = True
        return ok

    @rx.event
    def exit_spectator(self):
        self.spectator_token = ""
        self.spectator_room = ""
        self.spectating = False
        return rx.redirect("/")

    # Generic explicit setter (replaces the deprecated implicit `set_*` setters).
    # Bind with e.g. on_change=AppState.set_field("username").
    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    @rx.event
    def handle_signup(self):
        self.auth_error = ""
        doc = repo.load()
        try:
            sign_up(doc, self.username, self.password, self.confirm)
        except AuthError as exc:
            self.auth_error = str(exc)
            return
        repo.save(doc)
        self.auth_user = self.username.strip()
        self._clear_auth_form()
        return rx.redirect("/rooms")

    @rx.event
    def handle_login(self):
        self.auth_error = ""
        doc = repo.load()
        try:
            user = log_in(doc, self.username, self.password)
        except AuthError as exc:
            self.auth_error = str(exc)
            return
        repo.save(doc)   # persist any transparent legacy→PBKDF2 hash upgrade
        self.auth_user = user
        self._clear_auth_form()
        return rx.redirect("/rooms")

    @rx.event
    def handle_logout(self):
        self.auth_user = ""
        self.logged_in = False
        return rx.redirect("/")

    @rx.event
    async def force_refresh(self):
        path = self.router.page.path
        if "/bidding" in path:
            from fantasy_auction.bidding_state import BiddingState
            b = await self.get_state(BiddingState)
            await b.on_load_bidding()
        elif "/trade" in path:
            from fantasy_auction.trade_state import TradeState
            t = await self.get_state(TradeState)
            await t.on_load_trade()
            from fantasy_auction.announce_state import AnnounceState
            an = await self.get_state(AnnounceState)
            await an.on_load_announcements()
        elif "/announcements" in path:
            from fantasy_auction.announce_state import AnnounceState
            an = await self.get_state(AnnounceState)
            await an.on_load_announcements()
        elif "/schedule" in path:
            from fantasy_auction.schedule_state import ScheduleState
            sc = await self.get_state(ScheduleState)
            await sc.on_load_schedule()
        elif "/standings" in path:
            from fantasy_auction.season_state import SeasonState
            s = await self.get_state(SeasonState)
            await s.on_load_standings()
            from fantasy_auction.room_state import RoomState
            rs = await self.get_state(RoomState)
            await rs.on_load_hub()
        elif "/admin" in path:
            from fantasy_auction.admin_state import AdminState
            a = await self.get_state(AdminState)
            await a.on_load_admin()
            from fantasy_auction.season_state import SeasonState
            s = await self.get_state(SeasonState)
            await s.on_load_standings()
            from fantasy_auction.room_state import RoomState
            rs = await self.get_state(RoomState)
            await rs.on_load_hub()
        elif "/room" in path or "/squads" in path:
            from fantasy_auction.room_state import RoomState
            rs = await self.get_state(RoomState)
            await rs.on_load_hub()
        elif "/rooms" in path:
            await self.load_rooms()
        elif "/setup" in path:
            await self.load_setup()

    @rx.event
    def handle_reset_password(self):
        self.reset_msg = ""
        if self.reset_new_pw != self.reset_confirm:
            self.reset_msg = "Passwords do not match."
            return
        doc = repo.load()
        try:
            reset_password(doc, self.reset_username, self.reset_room_code, self.reset_new_pw)
        except AuthError as exc:
            self.reset_msg = str(exc)
            return
        repo.save(doc)
        self.reset_msg = "✅ Password reset! You can now log in."
        self.reset_username = self.reset_room_code = ""
        self.reset_new_pw = self.reset_confirm = ""

    def _clear_auth_form(self):
        self.username = self.password = self.confirm = ""

    @rx.event
    def require_login(self):
        """on_load guard for protected pages."""
        if not self.auth_user:
            return rx.redirect("/")

    @rx.event
    def redirect_if_logged_in(self):
        """on_load for the index page — skip the login screen if already in."""
        if self.auth_user:
            return rx.redirect("/rooms")

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #
    @rx.event
    async def load_rooms(self):
        for _ in range(60):  # break as soon as auth is ready; don't wait on is_hydrated
            if self.auth_user:
                break
            await asyncio.sleep(0.05)
        if not self.auth_user:
            return rx.redirect("/")
        doc = await aload()
        user = doc.get("users", {}).get(self.auth_user, {})
        codes = list(
            dict.fromkeys(user.get("rooms_created", []) + user.get("rooms_joined", []))
        )
        # Also surface any room this user actually belongs to (admin or a claimed team)
        # even if their reverse index (rooms_created/rooms_joined) drifted out of sync —
        # otherwise a real member silently can't see their room. The whole doc is already
        # loaded, so this scan costs no extra Firebase egress.
        for rcode, room in (doc.get("rooms", {}) or {}).items():
            if not isinstance(room, dict):
                continue
            if (room.get("admin") == self.auth_user
                    or any(p.get("user") == self.auth_user
                           for p in room.get("participants", []))):
                if rcode not in codes:
                    codes.append(rcode)
        rooms: list[dict[str, str]] = []
        for code in codes:
            room = doc.get("rooms", {}).get(code)
            if room:
                rooms.append(
                    {
                        "code": code,
                        "name": room.get("name", ""),
                        "tournament": room.get("tournament_type", ""),
                        "role": "Admin" if room.get("admin") == self.auth_user else "Member",
                        "teams": str(len(room.get("participants", []))),
                    }
                )
        self.my_rooms = rooms

    @rx.event
    def handle_create_room(self):
        self.create_error = ""
        doc = repo.load()
        try:
            code = repo.create_room(
                doc,
                self.auth_user,
                self.new_room_name,
                self.new_tournament,
                self.admin_participating,
            )
        except RepositoryError as exc:
            self.create_error = str(exc)
            return
        repo.save(doc)
        self.new_room_name = ""
        return rx.redirect(f"/setup?room={code}")

    @rx.event
    def handle_join(self):
        self.join_error = ""
        doc = repo.load()
        try:
            repo.claim_team(doc, self.join_code, self.auth_user, self.join_pin)
        except RepositoryError as exc:
            self.join_error = str(exc)
            return
        repo.save(doc)
        code = self.join_code.strip().upper()
        self.join_code = self.join_pin = ""
        return rx.redirect(f"/room?room={code}")

    # ------------------------------------------------------------------ #
    # Room setup (admin)
    # ------------------------------------------------------------------ #
    def _room_code_from_url(self) -> str:
        return (self.router._page.params.get("room", "") or "").upper()

    @rx.event
    async def load_setup(self):
        for _ in range(60):  # break as soon as auth is ready; don't wait on is_hydrated
            if self.auth_user:
                break
            await asyncio.sleep(0.05)
        if not self.auth_user:
            return rx.redirect("/")
        code = self._room_code_from_url()
        if not code:
            return
        doc = await aload()
        room = doc.get("rooms", {}).get(code)
        if not room:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.room_tournament = room.get("tournament_type", "")
        self.is_admin = room.get("admin") == self.auth_user
        self.setup_msg = ""
        self.upload_msg = ""
        self.pool_count = len(room.get("player_pool", []) or [])
        self._refresh_teams(room)

    def _refresh_teams(self, room: dict):
        self.teams = [
            {
                "name": p["name"],
                "pin": str(p.get("pin") or "—"),
                "claimed": p.get("user") or "unclaimed",
                "budget": str(p.get("budget", 0)),
                "squad": str(len(p.get("squad") or [])),
            }
            for p in room.get("participants", [])
        ]
        self.team_names = [p["name"] for p in room.get("participants", [])]

    team_names: list[str] = []

    @rx.event
    def claim_my_team(self):
        """Admin picks which team (from the CSV) they'll manage all tournament."""
        self.setup_msg = ""
        if not self.claim_choice:
            self.setup_msg = "Pick a team to manage."
            return
        doc = repo.load()
        room = doc.get("rooms", {}).get(self.room_code)
        if room is None:
            return
        for p in room.get("participants", []):
            if p.get("user") == self.auth_user and p["name"] != self.claim_choice:
                p["user"] = None  # release any previously-claimed team
        for p in room.get("participants", []):
            if p["name"] == self.claim_choice:
                p["user"] = self.auth_user
        # Drop the auto-created admin-named placeholder team (e.g. "Admin FC") so it
        # doesn't sit alongside the real CSV team the admin just claimed.
        room["participants"] = [
            p for p in room.get("participants", [])
            if not (p["name"] == self.auth_user and p["name"] != self.claim_choice
                    and not p.get("squad"))
        ]
        repo.save(doc)
        self._refresh_teams(room)
        self.setup_msg = f"✅ You'll manage '{self.claim_choice}' all tournament."

    @rx.event
    def handle_add_team(self):
        self.setup_msg = ""
        doc = repo.load()
        room = doc.get("rooms", {}).get(self.room_code)
        if not room:
            self.setup_msg = "Room not found."
            return
        try:
            repo.add_team(room, self.new_team_name, self.new_team_pin)
        except RepositoryError as exc:
            self.setup_msg = str(exc)
            return
        repo.save(doc)
        self.new_team_name = self.new_team_pin = ""
        self._refresh_teams(room)

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Parse the CSV and build a review table (no commit yet)."""
        self.upload_msg = ""
        self.import_rows = []
        self.import_budgets = []
        if not files:
            self.upload_msg = "No file selected."
            return
        raw = await files[0].read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
        result = parse_squad_csv(text)
        if not result.ok:
            self.upload_msg = "❌ " + " ".join(result.errors[:4])
            return

        doc = repo.load()
        room = doc.get("rooms", {}).get(self.room_code)
        if room is None:
            self.upload_msg = "Room not found."
            return

        if result.kind == "pool":
            added = apply_pool_import(room, result, extend=True)
            repo.save(doc)
            self.pool_count = len(room.get("player_pool", []))
            self.upload_msg = f"✅ Added {added} players to the pool ({self.pool_count} total)."
            return

        # Roster: fuzzy-match each written name to the pool for admin review.
        if room.get("player_pool"):
            pool_names = [p["name"] for p in room["player_pool"]]
        else:
            pool_names = [p.name for p in load_player_pool(room.get("tournament_type", "T20 World Cup"))]
        reviewed = build_review(result.assignments, pool_names)
        self.import_rows = [
            {"participant": r["participant"], "written": r["written"], "matched": r["matched"],
             "status": r["status"], "price": str(r["price"])}
            for r in reviewed
        ]
        self.import_candidates = [r["candidates"] for r in reviewed]
        self.import_budgets = [{"participant": k, "budget": str(v)} for k, v in result.budgets.items()]
        self.import_unmatched = sum(1 for r in reviewed if r["status"] == "unmatched")
        self.upload_msg = (f"Loaded {len(reviewed)} signings for review. Confirm the matches "
                           f"below, then commit. ({self.import_unmatched} need attention.)")

    @rx.event
    def set_match(self, index: int, value: str):
        rows = [dict(r) for r in self.import_rows]
        if 0 <= index < len(rows):
            rows[index]["matched"] = value
            rows[index]["status"] = "confirmed"
            self.import_rows = rows

    @rx.event
    def confirm_import(self):
        if not self.import_rows:
            self.upload_msg = "Nothing to import."
            return
        doc = repo.load()
        room = doc.get("rooms", {}).get(self.room_code)
        if room is None:
            self.upload_msg = "Room not found."
            return
        rows = [{"participant": r["participant"], "matched": r["matched"],
                 "price": int(r["price"])} for r in self.import_rows]
        budgets = {b["participant"]: int(b["budget"]) for b in self.import_budgets}
        n = apply_reviewed_roster(room, rows, budgets)
        repo.save(doc)
        self._refresh_teams(room)
        self.pool_count = len(room.get("player_pool", []) or [])
        self.import_rows = []
        self.import_candidates = []
        self.import_budgets = []
        self.upload_msg = f"✅ Committed {n} signings with confirmed names + CSV budgets."

    @rx.event
    def cancel_import(self):
        self.import_rows = []
        self.import_candidates = []
        self.import_budgets = []
        self.upload_msg = "Import cancelled."

    @rx.event
    def go_to_room(self):
        return rx.redirect(f"/room?room={self.room_code}")
