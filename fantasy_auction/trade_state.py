"""Reflex state for trading + open market (Phase 9)."""

from __future__ import annotations

import asyncio
import reflex as rx

from datetime import datetime

from platform_core import market_ops as mo
from platform_core import season_ops as so
from season_engine.trading import TradeError

from .state import AppState, repo


def _summary(t: dict, *, incoming: bool) -> str:
    gp = ", ".join(t["give_players"]) or "—"
    rp = ", ".join(t["get_players"]) or "—"
    loan_sfx = f" (Loan till GW{t.get('loan_return_gw', '?')})" if t.get("is_loan") else ""
    if incoming:
        return (f"{t['from']} sends [{gp}] +{t['give_cash']}M  ↔  wants your "
                f"[{rp}] +{t['get_cash']}M{loan_sfx}")
    return (f"To {t['to']}: you send [{gp}] +{t['give_cash']}M  for [{rp}] +{t['get_cash']}M{loan_sfx}")


class TradeState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    me: str = ""

    my_players: list[str] = []
    other_teams: list[str] = []
    counterparty: str = ""
    their_players: list[str] = []

    give_player: str = ""
    get_player: str = ""
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
        for _ in range(100):
            if app.is_hydrated:
                break
            await asyncio.sleep(0.05)
        code, doc, room = self._load()
        if not code:
            return
        if room is None:
            if app.auth_user:
                return rx.redirect("/rooms")
            return
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = room.get("admin") == app.auth_user
        self.me = next((p["name"] for p in room.get("participants", [])
                        if p.get("user") == app.auth_user), "")
        self.msg = ""
        # Pre-fill from a "🤝 Trade" click on another team's squad: ?with=TEAM&want=PLAYER
        params = self.router._page.params
        with_team = params.get("with", "")
        want = params.get("want", "")
        by = mo.participants_by_name(room)
        if with_team and with_team in by and with_team != self.me:
            self.counterparty = with_team
            if want and any(e["name"] == want for e in by[with_team].get("squad", [])):
                self.get_player = want
                self.msg = f"Proposing a trade with {with_team} for {want} — add what you'll give."
        self._refresh(room)

    def _refresh(self, room: dict):
        by = mo.participants_by_name(room)
        mine = by.get(self.me, {})
        self.my_players = [e["name"] for e in mine.get("squad", [])]
        self.other_teams = [n for n in by if n != self.me]
        if self.counterparty and self.counterparty in by:
            self.their_players = [e["name"] for e in by[self.counterparty].get("squad", [])]
        else:
            self.their_players = []
        self.incoming = [{"id": t["id"], "text": _summary(t, incoming=True)}
                         for t in mo.incoming_trades(room, self.me)]
        self.outgoing = [{"id": t["id"], "text": _summary(t, incoming=False)}
                         for t in mo.outgoing_trades(room, self.me)]
        self.awaiting = [{"id": t["id"],
                          "text": f"{t['from']} ↔ {t['to']}: "
                                  f"[{', '.join(t['give_players']) or '—'}]+{t['give_cash']}M "
                                  f"for [{', '.join(t['get_players']) or '—'}]+{t['get_cash']}M" +
                                  (f" (Loan till GW{t.get('loan_return_gw', '?')})" if t.get("is_loan") else "")}
                         for t in mo.trades_awaiting_admin(room)] if self.is_admin else []
        self.available = [{"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                          for p in mo.available_players(room)]
        self.txns = [{"text": self._txn_text(t), "ts": t.get("ts", "")} for t in reversed(mo.transactions(room)[-15:])]

    @staticmethod
    def _txn_text(t: dict) -> str:
        if t["type"] == "trade":
            return (f"🔄 {t['from']} ↔ {t['to']}: [{', '.join(t['give_players']) or '—'}]"
                    f"/+{t['give_cash']}M for [{', '.join(t['get_players']) or '—'}]/+{t['get_cash']}M")
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
        _, _, room = self._load()
        if room:
            self._refresh(room)

    def _save_refresh(self, doc, room, ok_msg):
        repo.save(doc)
        self._refresh(room)
        self.msg = ok_msg

    @rx.event
    def propose(self):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        if not so.trading_open(room, datetime.now()):
            self.msg = "⚠️ Trading is frozen — it opens once the admin sets a bidding deadline."
            return
        gp = [self.give_player] if self.give_player else []
        rp = [self.get_player] if self.get_player else []
        
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
        self._save_refresh(doc, room, "✅ Proposal sent.")

    @rx.event
    def accept(self, trade_id: str):
        self.msg = ""
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

    @rx.event
    def admin_reject(self, trade_id: str):
        code, doc, room = self._load()
        if room:
            mo.admin_reject_trade(room, trade_id)
            self._save_refresh(doc, room, "Trade rejected by admin.")

    @rx.event
    def reject(self, trade_id: str):
        code, doc, room = self._load()
        if room:
            mo.reject_trade(room, trade_id)
            self._save_refresh(doc, room, "Proposal rejected.")

    @rx.event
    def do_release(self):
        self.msg = ""
        code, doc, room = self._load()
        if not room or not self.release_sel:
            return
        try:
            mo.release(room, self.me, self.release_sel, refund=False)
        except TradeError as exc:
            self.msg = f"⚠️ {exc}"
            return
        self.release_sel = ""
        self._save_refresh(doc, room, "🗑️ Player released to the market.")

    @rx.event
    def place_bid(self):
        self.msg = ""
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
        code, doc, room = self._load()
        if not room:
            return
        rec = mo.resolve_market(room, player_name)
        self._save_refresh(doc, room,
                           f"🛒 {rec['participant']} won {player_name}." if rec else "No valid bids.")
