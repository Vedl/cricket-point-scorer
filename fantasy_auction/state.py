"""Reflex application state for auth + room setup (Phases 2 & 4 entry).

State classes are thin: they call the pure ``platform_core`` repository/auth/CSV
helpers, persist via the Firebase-backed store, and expose display vars. No
business rules live here.
"""

from __future__ import annotations

import os

import reflex as rx


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency) so the backend picks up
    Firebase config regardless of how it's launched."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

from platform_core.auth import AuthError, log_in, sign_up
from platform_core.config_layer import TOURNAMENTS
from platform_core.csv_import import parse_squad_csv
from platform_core.repository import (
    Repository,
    RepositoryError,
    apply_pool_import,
    apply_roster_import,
)

# One repository for the process; the store reads Firebase config from env and
# falls back to a local JSON file when unset (see PLAN.md §6.6).
repo = Repository()


class AppState(rx.State):
    # --- session (persisted across reloads) ---
    auth_user: str = rx.LocalStorage("")

    # --- auth form ---
    username: str = ""
    password: str = ""
    confirm: str = ""
    auth_error: str = ""

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
    setup_msg: str = ""
    upload_msg: str = ""
    pool_count: int = 0

    tournaments: list[str] = list(TOURNAMENTS)

    # ------------------------------------------------------------------ #
    # Computed
    # ------------------------------------------------------------------ #
    @rx.var
    def logged_in(self) -> bool:
        return self.auth_user != ""

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
        self.auth_user = user
        self._clear_auth_form()
        return rx.redirect("/rooms")

    @rx.event
    def handle_logout(self):
        self.auth_user = ""
        return rx.redirect("/")

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
    def load_rooms(self):
        if not self.auth_user:
            return rx.redirect("/")
        doc = repo.load()
        user = doc.get("users", {}).get(self.auth_user, {})
        codes = list(
            dict.fromkeys(user.get("rooms_created", []) + user.get("rooms_joined", []))
        )
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
            repo.claim_team(
                doc, self.join_code, self.auth_user, self.join_team, self.join_pin
            )
        except RepositoryError as exc:
            self.join_error = str(exc)
            return
        repo.save(doc)
        code = self.join_code.strip().upper()
        self.join_code = self.join_team = self.join_pin = ""
        return rx.redirect(f"/room?room={code}")

    # ------------------------------------------------------------------ #
    # Room setup (admin)
    # ------------------------------------------------------------------ #
    def _room_code_from_url(self) -> str:
        return (self.router._page.params.get("room", "") or "").upper()

    @rx.event
    def load_setup(self):
        if not self.auth_user:
            return rx.redirect("/")
        code = self._room_code_from_url()
        doc = repo.load()
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
                "squad": str(len(p.get("squad", []))),
            }
            for p in room.get("participants", [])
        ]

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
        self.upload_msg = ""
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
            self.pool_count = len(room.get("player_pool", []))
            self.upload_msg = f"✅ Added {added} players to the pool ({self.pool_count} total)."
        else:
            n = apply_roster_import(room, result)
            self._refresh_teams(room)
            self.upload_msg = f"✅ Imported {n} roster assignments."
        if result.warnings:
            self.upload_msg += f"  ({len(result.warnings)} warning(s) ignored.)"
        repo.save(doc)

    @rx.event
    def go_to_room(self):
        return rx.redirect(f"/room?room={self.room_code}")
