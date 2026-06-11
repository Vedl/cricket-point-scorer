"""Reflex state for the admin panel (admin micro-features)."""

from __future__ import annotations

import asyncio
import os
import secrets

import reflex as rx

from platform_core import admin_ops as ao

from .state import AppState, aload, repo


class AdminState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    teams: list[str] = []
    loans: list[dict[str, str]] = []

    # force add (with pool suggestions)
    fa_team: str = ""
    fa_player: str = ""
    fa_role: str = ""
    fa_team_name: str = ""
    fa_price: str = "0"
    fa_suggestions: list[dict[str, str]] = []
    _pool: list[dict] = []
    # force release (players of the selected team)
    fr_team: str = ""
    fr_player: str = ""
    fr_refund: bool = False
    fr_team_players: list[str] = []
    # releasing a LOANED player needs a second click to confirm (player name held here)
    fr_loan_confirm: str = ""
    # budget / pin
    boost_amount: str = ""
    rename_old: str = ""
    rename_new: str = ""
    
    # Reverse Release
    rev_participant: str = ""
    rev_player: str = ""
    rev_buy: str = ""
    rev_refund: str = ""
    
    # Edit Budget
    edit_participant: str = ""
    edit_delta: str = ""
    bud_team: str = ""
    bud_delta: str = "0"
    pin_team: str = ""
    pin_value: str = ""
    # loans
    loan_from: str = ""
    loan_to: str = ""
    loan_player: str = ""
    loan_gw: str = ""
    # country knockouts (WC): block bids + enable allowance-free half-price releases
    ko_country: str = ""
    ko_countries: list[str] = []          # currently knocked out
    ko_options: list[str] = []            # all nations in the pool
    # backup
    export_text: str = ""
    import_text: str = ""
    # PIN distribution
    pin_summary: list[dict[str, str]] = []
    show_pins: bool = False
    manual_boost_applied: bool = False
    # spectator (read-only guest) link
    spectator_link: str = ""

    @rx.var
    def pin_clipboard_text(self) -> str:
        return "\n".join(f"{p['name']} → PIN {p['pin']}" for p in self.pin_summary)

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
        for _ in range(60):  # break as soon as auth is ready; don't wait on is_hydrated
            if app.auth_user:
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
        self.msg = ""
        self.spectator_link = self._spectator_url(code, room.get("spectator_token", ""))
        self._refresh(room)

    def _spectator_url(self, code: str, token: str) -> str:
        if not token:
            return ""
        base = (os.environ.get("DEPLOY_URL") or os.environ.get("API_URL") or "").rstrip("/")
        return f"{base}/room?room={code}&spectate={token}"

    @rx.event
    def create_spectator_link(self):
        """Create the read-only spectator link (reuses the existing token if present)."""
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        token = room.get("spectator_token") or secrets.token_urlsafe(9)
        room["spectator_token"] = token
        repo.save(doc)
        self.spectator_link = self._spectator_url(code, token)
        self.msg = "✅ Spectator link ready — anyone with it can watch this room read-only."

    @rx.event
    def regenerate_spectator_link(self):
        """Issue a fresh token; any previously shared link stops working."""
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        token = secrets.token_urlsafe(9)
        room["spectator_token"] = token
        repo.save(doc)
        self.spectator_link = self._spectator_url(code, token)
        self.msg = "✅ New spectator link generated — the old link no longer works."

    @rx.event
    def disable_spectator_link(self):
        """Revoke spectator access entirely."""
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        room["spectator_token"] = ""
        repo.save(doc)
        self.spectator_link = ""
        self.msg = "Spectator link disabled — existing spectators lose access."

    def _refresh(self, room):
        self.teams = [p["name"] for p in room.get("participants", [])]
        if room.get("player_pool"):
            self._pool = [{"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                          for p in room["player_pool"]]
        else:
            from platform_core.config_layer import load_player_pool
            self._pool = [{"name": p.name, "role": p.role, "team": p.team}
                          for p in load_player_pool(room.get("tournament_type", "T20 World Cup"))]
        self._refresh_fr_players(room)
        from platform_core import season_ops as so
        self.ko_countries = sorted(so.knocked_out_countries(room))
        self.ko_options = sorted({(p.get("team") or "") for p in self._pool} - {""})
        self.loans = [{"id": l["id"],
                       "text": f"{l['player']}: {l['from']} → {l['to']}"
                               + (f" (ret GW{l['return_gameweek']})" if l.get("return_gameweek") else "")}
                      for l in room.get("active_loans", [])]
        self.manual_boost_applied = bool(room.get("manual_boost_applied", False))

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

    def _refresh_fr_players(self, room):
        by = {p["name"]: p for p in room.get("participants", [])}
        p = by.get(self.fr_team, {})
        self.fr_team_players = [e["name"] for e in p.get("squad", [])]

    @rx.event
    def pick_fr_team(self, name: str):
        self.fr_team = name
        self.fr_player = ""
        self.fr_loan_confirm = ""
        code, doc, room = self._load()
        if room:
            self._refresh_fr_players(room)

    @rx.event
    def fa_type(self, value: str):
        from platform_core.textutil import fold
        self.fa_player = value
        v = fold(value)
        if len(v) < 2:
            self.fa_suggestions = []
            return
        out = []
        for p in self._pool:
            if v in fold(p["name"]):
                out.append(p)
                if len(out) >= 8:
                    break
        self.fa_suggestions = out

    @rx.event
    def mark_country_ko(self):
        """Mark the selected nation as knocked out of the World Cup."""
        from platform_core import season_ops as so
        self.msg = ""
        country = (self.ko_country or "").strip()
        if not country:
            self.msg = "⚠️ Pick a country first."
            return
        code, doc, room = self._load()
        if not room:
            return
        cancelled = so.mark_country_knocked_out(room, country, True)
        repo.save(doc)
        self._refresh(room)
        self.ko_country = ""
        self.msg = (f"🚫 {country} marked knocked out — their players can't be bid on; "
                    f"owners can release them at half price without using their paid release."
                    + (f" Cancelled open bids: {', '.join(cancelled)}." if cancelled else ""))

    @rx.event
    def unmark_country_ko(self, country: str):
        from platform_core import season_ops as so
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        so.mark_country_knocked_out(room, country, False)
        repo.save(doc)
        self._refresh(room)
        self.msg = f"✅ {country} restored — bidding on their players is allowed again."

    @rx.event
    def pick_fa(self, name: str, role: str, team: str):
        self.fa_player = name
        self.fa_role = role
        self.fa_team_name = team
        self.fa_suggestions = []

    @rx.event
    def force_add(self):
        self._do(lambda room, doc: ao.force_add_player(
            room, self.fa_team, self.fa_player, self.fa_role, self.fa_team_name,
            int(self.fa_price or 0)), f"✅ Added {self.fa_player} to {self.fa_team}.")

    def _confirm_loaned_release(self, room) -> bool:
        """If the selected player is on loan to fr_team, require a second click.
        Returns True when the release may proceed."""
        by = {p["name"]: p for p in room.get("participants", [])}
        entry = next((e for e in by.get(self.fr_team, {}).get("squad", [])
                      if e.get("name", "").lower() == (self.fr_player or "").lower()), None)
        if entry is None or entry.get("acquired_via") != "loan":
            self.fr_loan_confirm = ""
            return True
        if self.fr_loan_confirm == self.fr_player:
            self.fr_loan_confirm = ""
            return True
        loan = next((l for l in room.get("active_loans", [])
                     if l.get("player", "").lower() == self.fr_player.lower()
                     and l.get("to") == self.fr_team), None)
        owner = f" (on loan from {loan['from']})" if loan else " (on loan)"
        self.fr_loan_confirm = self.fr_player
        self.msg = (f"⚠️ {self.fr_player} is a LOANED player{owner} — releasing them from "
                    f"{self.fr_team} also breaks the loan. Click release again to confirm.")
        return False

    def _force_release(self, *, refund: bool, ok_msg: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        if not self._confirm_loaned_release(room):
            return
        try:
            ao.force_release(room, self.fr_team, self.fr_player, refund=refund)
        except ao.AdminError as exc:
            self.msg = f"⚠️ {exc}"
            return
        # Drop the loan record too — the entry is gone from the borrower's squad,
        # so an auto-return later would otherwise duplicate the player.
        room["active_loans"] = [l for l in room.get("active_loans", [])
                                if not (l.get("player", "").lower() == self.fr_player.lower()
                                        and l.get("to") == self.fr_team)]
        repo.save(doc)
        self._refresh(room)
        self.msg = ok_msg

    @rx.event
    def force_release(self):
        self._force_release(refund=self.fr_refund,
                            ok_msg=f"✅ Released {self.fr_player} from {self.fr_team}.")

    @rx.event
    def release_full_price(self):
        """Release the selected player and refund the team the FULL price they paid."""
        self._force_release(refund=True,
                            ok_msg=f"✅ Released {self.fr_player} for full price — "
                                   f"refund credited to {self.fr_team}.")

    @rx.event
    def adjust_budget(self):
        self._do(lambda room, doc: ao.adjust_budget(room, self.bud_team, int(self.bud_delta)),
                 f"✅ Adjusted {self.bud_team}'s budget.")

    @rx.event
    def reset_pin(self):
        self._do(lambda room, doc: ao.reset_pin(room, self.pin_team, self.pin_value),
                 f"✅ Reset PIN for {self.pin_team}.")

    @rx.event
    def distribute_pins(self):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        self.pin_summary = ao.distribute_pins(room)
        repo.save(doc)
        self._refresh(room)
        self.show_pins = True
        self.msg = f"✅ PINs generated for all unclaimed teams."

    @rx.event
    def hide_pins(self):
        self.show_pins = False

    @rx.event
    def make_loan(self):
        self._do(lambda room, doc: ao.loan_player(
            room, self.loan_from, self.loan_to, self.loan_player, self.loan_gw),
            f"✅ Loaned {self.loan_player}.")

    @rx.event
    def undo_loan(self, loan_id: str):
        self._do(lambda room, doc: ao.reverse_loan(room, loan_id), "✅ Loan reversed.")

    @rx.event
    def boost_all(self):
        self._do(lambda room, doc: ao.boost_all(room, 100),
                 "💸 +100M added to every team's budget.")

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

    @rx.var(cache=True)
    def rev_player_options(self) -> list[str]:
        code, doc, room = self._load()
        if not room or not self.rev_participant:
            return []
        opts = []
        for t in room.get("transactions", []):
            if t.get("type") in ("release", "half_release") and t.get("participant") == self.rev_participant:
                opts.append(t["player"])
        return list(dict.fromkeys(opts))

    @rx.event
    def pick_rev_player(self, player_name: str):
        self.rev_player = player_name
        code, doc, room = self._load()
        if not room:
            return
            
        refund = 0
        buy_price = 0
        for t in reversed(room.get("transactions", [])):
            if t.get("type") in ("release", "half_release") and t.get("participant") == self.rev_participant and t.get("player") == player_name:
                refund = t.get("refund", 0)
                # Releases now record the price paid — use it directly when present.
                buy_price = t.get("buy_price", 0)
                break

        if buy_price == 0:
            for t in room.get("transactions", []):
                if t.get("type") in ("market_buy", "auction_buy", "trade") and t.get("player") == player_name and t.get("participant", t.get("to")) == self.rev_participant:
                    buy_price = t.get("amount", t.get("price", 0))
                
        if buy_price == 0:
            for log in room.get("auction_log", []):
                if log.get("player") == player_name and log.get("buyer") == self.rev_participant:
                    buy_price = log.get("price", 0)
                    
        self.rev_refund = str(refund)
        self.rev_buy = str(buy_price)

    @rx.event
    def do_reverse_release(self):
        self._do(lambda room, doc: ao.reverse_release(
            room, self.rev_participant, self.rev_player,
            int(self.rev_buy or 0), int(self.rev_refund or 0)
        ), "⏪ Release reversed.")

    @rx.event
    def do_edit_budget(self):
        self._do(lambda room, doc: ao.adjust_budget(
            room, self.edit_participant, int(self.edit_delta or 0)
        ), "💰 Budget adjusted.")
