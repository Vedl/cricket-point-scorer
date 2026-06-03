"""Reflex state for the admin panel (admin micro-features)."""

from __future__ import annotations

import reflex as rx

from platform_core import admin_ops as ao

from .state import AppState, repo


class AdminState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    teams: list[str] = []
    loans: list[dict[str, str]] = []

    # force add
    fa_team: str = ""
    fa_player: str = ""
    fa_role: str = ""
    fa_team_name: str = ""
    fa_price: str = "0"
    # force release
    fr_team: str = ""
    fr_player: str = ""
    fr_refund: bool = False
    # budget / pin
    bud_team: str = ""
    bud_delta: str = "0"
    pin_team: str = ""
    pin_value: str = ""
    # loans
    loan_from: str = ""
    loan_to: str = ""
    loan_player: str = ""
    loan_gw: str = ""
    # backup
    export_text: str = ""
    import_text: str = ""

    msg: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_admin(self):
        app = await self.get_state(AppState)
        if not app.auth_user:
            return rx.redirect("/")
        code, doc, room = self._load()
        if room is None:
            return rx.redirect("/rooms")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.msg = ""
        self._refresh(room)

    def _refresh(self, room):
        self.teams = [p["name"] for p in room.get("participants", [])]
        self.loans = [{"id": l["id"],
                       "text": f"{l['player']}: {l['from']} → {l['to']}"
                               + (f" (ret GW{l['return_gameweek']})" if l.get("return_gameweek") else "")}
                      for l in room.get("active_loans", [])]

    def _do(self, fn, ok):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            fn(room, doc)
        except ao.AdminError as exc:
            self.msg = f"⚠️ {exc}"
            return
        except ValueError:
            self.msg = "⚠️ Enter valid numbers."
            return
        repo.save(doc)
        self._refresh(room)
        self.msg = ok

    @rx.event
    def force_add(self):
        self._do(lambda room, doc: ao.force_add_player(
            room, self.fa_team, self.fa_player, self.fa_role, self.fa_team_name,
            int(self.fa_price or 0)), f"✅ Added {self.fa_player} to {self.fa_team}.")

    @rx.event
    def force_release(self):
        self._do(lambda room, doc: ao.force_release(
            room, self.fr_team, self.fr_player, refund=self.fr_refund),
            f"✅ Released {self.fr_player} from {self.fr_team}.")

    @rx.event
    def adjust_budget(self):
        self._do(lambda room, doc: ao.adjust_budget(room, self.bud_team, int(self.bud_delta)),
                 f"✅ Adjusted {self.bud_team}'s budget.")

    @rx.event
    def reset_pin(self):
        self._do(lambda room, doc: ao.reset_pin(room, self.pin_team, self.pin_value),
                 f"✅ Reset PIN for {self.pin_team}.")

    @rx.event
    def make_loan(self):
        self._do(lambda room, doc: ao.loan_player(
            room, self.loan_from, self.loan_to, self.loan_player, self.loan_gw),
            f"✅ Loaned {self.loan_player}.")

    @rx.event
    def undo_loan(self, loan_id: str):
        self._do(lambda room, doc: ao.reverse_loan(room, loan_id), "✅ Loan reversed.")

    @rx.event
    def reset_room(self):
        self._do(lambda room, doc: ao.reset_room(room), "♻️ Room reset (teams kept).")

    @rx.event
    def export_room(self):
        code, doc, room = self._load()
        if room:
            self.export_text = ao.export_room(room)
            self.msg = "📦 Exported below."

    @rx.event
    def import_room(self):
        self._do(lambda room, doc: ao.import_room(doc, self.room_code, self.import_text),
                 "📥 Room imported.")

    @rx.event
    def delete_room(self):
        code, doc, room = self._load()
        if not room:
            return
        ao.delete_room(doc, code)
        repo.save(doc)
        return rx.redirect("/rooms")
