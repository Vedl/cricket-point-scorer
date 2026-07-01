"""Reflex state for trading + open market (Phase 9)."""

from __future__ import annotations

import asyncio
import reflex as rx

from datetime import datetime

from platform_core import market_ops as mo
from platform_core import season_ops as so
from season_engine.trading import TradeError

from .state import AppState, aload, repo


def _trade_card(t: dict) -> dict:
    """Structured view of a trade for the UI's two-panel proposal cards."""
    return {
        "id": t.get("id", ""),
        "from": t.get("from", "?"),
        "to": t.get("to", "?"),
        "give": ", ".join(t.get("give_players") or []) or "—",
        "give_cash": str(t.get("give_cash", 0) or 0),
        "get": ", ".join(t.get("get_players") or []) or "—",
        "get_cash": str(t.get("get_cash", 0) or 0),
        "loan": "yes" if t.get("is_loan") else "",
        "loan_gw": str(t.get("loan_return_gw", "") or ""),
    }


class TradeState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    is_spectator: bool = False
    me: str = ""

    my_players: list[str] = []
    other_teams: list[str] = []
    counterparty: str = ""
    their_players: list[str] = []

    give_player: str = ""          # picker selection (feeds "+ Add")
    get_player: str = ""
    give_players: list[str] = []   # the actual multi-player legs of the proposal
    get_players: list[str] = []
    give_cash: str = "0"
    get_cash: str = "0"
    
    is_loan: bool = False
    loan_return_gw: str = ""

    incoming: list[dict[str, str]] = []
    outgoing: list[dict[str, str]] = []
    awaiting: list[dict[str, str]] = []   # admin approval queue

    release_sel: str = ""
    available: list[dict[str, str]] = []
    bid_player: str = ""
    bid_amount: str = ""

    txns: list[dict[str, str]] = []
    msg: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_trade(self):
        app = await self.get_state(AppState)
        for _ in range(60):
            if (self.router._page.params.get("room", "") or "") and (app.auth_user or app.is_hydrated):
                break
            await asyncio.sleep(0.05)
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = await aload()
        room = doc.get("rooms", {}).get(code)
        if not code:
            return
        spectator = app.grant_spectator_if_valid(
            code, room, self.router._page.params.get("spectate", "") or "")
        if not app.auth_user and not spectator:
            return rx.redirect("/")
        if room is None:
            return rx.redirect("/rooms") if app.auth_user else rx.redirect("/")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = (not spectator) and room.get("admin") == app.auth_user
        self.me = "" if spectator else next(
            (p["name"] for p in room.get("participants", []) if p.get("user") == app.auth_user), "")
        # A logged-in member/admin is never a spectator, regardless of any stale token.
        self.is_spectator = spectator and not self.is_admin and self.me == ""
        self.msg = ""
        # Pre-fill from a "🤝 Trade" click on another team's squad: ?with=TEAM&want=PLAYER
        params = self.router._page.params
        with_team = params.get("with", "")
        want = params.get("want", "")
        by = mo.participants_by_name(room)
        if with_team and with_team in by and with_team != self.me:
            self.counterparty = with_team
            if want and any(e["name"] == want for e in (by[with_team].get("squad") or [])):
                self.get_player = want
                self.msg = f"Proposing a trade with {with_team} for {want} — add what you'll give."
        self._refresh(room)

    def _refresh(self, room: dict):
        by = mo.participants_by_name(room)
        mine = by.get(self.me, {})
        ko = set(room.get("knocked_out_countries", []) or [])

        def _tradable(p: dict) -> list[str]:
            # Loaned-in players and knocked-out nations' players can't be traded.
            return [e["name"] for e in p.get("squad", [])
                    if e.get("acquired_via") != "loan" and (e.get("team") or "") not in ko]

        self.my_players = _tradable(mine)
        self.other_teams = [n for n in by if n != self.me]
        if self.counterparty and self.counterparty in by:
            self.their_players = _tradable(by[self.counterparty])
        else:
            self.their_players = []
        self.incoming = [_trade_card(t) for t in mo.incoming_trades(room, self.me)]
        self.outgoing = [_trade_card(t) for t in mo.outgoing_trades(room, self.me)]
        self.awaiting = [_trade_card(t) for t in mo.trades_awaiting_admin(room)] \
            if self.is_admin else []
        self.available = [{"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                          for p in mo.available_players(room)]
        self.txns = [{"text": self._txn_text(t), "ts": t.get("ts", "")} for t in reversed(mo.transactions(room)[-15:])]

    @staticmethod
    def _txn_text(t: dict) -> str:
        if t["type"] == "trade":
            return (f"🔄 {t.get('from', '?')} ↔ {t.get('to', '?')}: "
                    f"[{', '.join(t.get('give_players') or []) or '—'}]"
                    f"/+{t.get('give_cash', 0)}M for "
                    f"[{', '.join(t.get('get_players') or []) or '—'}]"
                    f"/+{t.get('get_cash', 0)}M")
        if t["type"] == "release":
            return f"🗑️ {t['participant']} released {t['player']}" + (" (refunded)" if t.get("refund") else "")
        if t["type"] == "half_release":
            r = t.get("refund", 0)
            tail = f"for +{r}M (half price)" if r else "for free"
            return f"🗑️ {t['participant']} released {t['player']} {tail}"
        if t["type"] == "market_buy":
            return f"🛒 {t['participant']} won {t['player']} for {t['amount']}M"
        return str(t)

    @rx.event
    def pick_counterparty(self, name: str):
        self.counterparty = name
        self.get_players = []      # their players belong to the old counterparty
        self.get_player = ""
        _, _, room = self._load()
        if room:
            self._refresh(room)

    # --- multi-player legs --------------------------------------------------- #
    @rx.event
    def add_give(self):
        if self.give_player and self.give_player not in self.give_players:
            self.give_players = self.give_players + [self.give_player]
        self.give_player = ""

    @rx.event
    def remove_give(self, name: str):
        self.give_players = [p for p in self.give_players if p != name]

    @rx.event
    def add_get(self):
        if self.get_player and self.get_player not in self.get_players:
            self.get_players = self.get_players + [self.get_player]
        self.get_player = ""

    @rx.event
    def remove_get(self, name: str):
        self.get_players = [p for p in self.get_players if p != name]

    def _save_refresh(self, doc, room, ok_msg):
        repo.save(doc)
        self._refresh(room)
        self.msg = ok_msg

    @rx.event
    def propose(self):
        self.msg = ""
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if not room:
            return
        if not so.trading_open(room, datetime.now()):
            self.msg = "⚠️ Trading is frozen — it opens once the admin sets a bidding deadline."
            return
        # The added lists, plus whatever is still selected in a picker (so a simple
        # one-for-one trade doesn't require pressing "+ Add").
        gp = list(self.give_players)
        if self.give_player and self.give_player not in gp:
            gp.append(self.give_player)
        rp = list(self.get_players)
        if self.get_player and self.get_player not in rp:
            rp.append(self.get_player)


        loan_gw = ""
        if self.is_loan:
            cur_gw = int(room.get("current_gameweek", 1) or 1)
            loan_gw = str(cur_gw + 1)
            
        try:
            mo.propose_trade(room, self.me, self.counterparty, gp, rp,
                             int(self.give_cash or 0), int(self.get_cash or 0),
                             is_loan=self.is_loan, loan_return_gw=loan_gw)
        except (TradeError, ValueError) as exc:
            self.msg = f"⚠️ {exc}"
            return
        self.give_players = []
        self.get_players = []
        self.give_player = self.get_player = ""
        self.give_cash = self.get_cash = "0"
        self.is_loan = False
        self._save_refresh(doc, room, "✅ Proposal sent.")

    @rx.event
    def accept(self, trade_id: str):
        self.msg = ""
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if not room:
            return
        try:
            mo.accept_trade(room, trade_id)
        except TradeError as exc:
            self.msg = f"⚠️ {exc}"
            return
        self._save_refresh(doc, room, "✅ Accepted — sent to the admin for approval.")

    @rx.event
    def admin_approve(self, trade_id: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            mo.admin_approve_trade(room, trade_id)
        except TradeError as exc:
            self.msg = f"⚠️ {exc}"
            return
        self._save_refresh(doc, room, "✅ Trade approved and applied.")
        # Push: the trade is now applied — tell the room.
        _t = next((x for x in room.get("pending_trades", []) if x.get("id") == trade_id), None)
        if _t:
            from fantasy_auction import notify
            notify.trade_done(room, _t.get("from", ""), _t.get("to", ""), code)

    @rx.event
    def admin_reject(self, trade_id: str):
        code, doc, room = self._load()
        if room:
            mo.admin_reject_trade(room, trade_id)
            self._save_refresh(doc, room, "Trade rejected by admin.")

    @rx.event
    def reject(self, trade_id: str):
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if room:
            mo.reject_trade(room, trade_id)
            self._save_refresh(doc, room, "Proposal rejected.")

    @rx.event
    def do_release(self):
        self.msg = ""
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if not room or not self.release_sel:
            return
        released_player = self.release_sel
        try:
            mo.release(room, self.me, self.release_sel, refund=False)
        except TradeError as exc:
            self.msg = f"⚠️ {exc}"
            return
        self.release_sel = ""
        self._save_refresh(doc, room, "🗑️ Player released to the market.")
        from fantasy_auction import notify
        notify.released(room, self.me, released_player, code)

    @rx.event
    def place_bid(self):
        self.msg = ""
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if not room:
            return
        try:
            mo.place_market_bid(room, self.me, self.bid_player, int(self.bid_amount or 0))
        except (TradeError, ValueError) as exc:
            self.msg = f"⚠️ {exc}"
            return
        self._save_refresh(doc, room, f"✅ Bid placed on {self.bid_player}.")

    @rx.event
    def resolve(self, player_name: str):
        if self.is_spectator:
            return
        code, doc, room = self._load()
        if not room:
            return
        rec = mo.resolve_market(room, player_name)
        self._save_refresh(doc, room,
                           f"🛒 {rec['participant']} won {player_name}." if rec else "No valid bids.")
        from fantasy_auction import notify
        notify.market_bought(room, rec, code)
