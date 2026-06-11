"""Announcements feed — a clean, shared news feed of every completed purchase,
trade and release in the room, with All/Buys/Trades/Releases filter tabs."""

from __future__ import annotations

import asyncio

import reflex as rx

from .state import AppState, aload, repo

_EMPTY = {"kind": "", "ts": "", "actor": "", "player": "", "amount": "", "detail": "",
          "mode": "", "sub": "", "from_name": "", "from_gave": "", "to_name": "",
          "to_gave": "", "loan": "no"}


def _names_cash(players, cash) -> str:
    parts = [p for p in (players or []) if p]
    if cash:
        parts.append(f"{cash}M cash")
    return "  +  ".join(parts) if parts else "—"


def build_feed(room: dict) -> list[dict[str, str]]:
    """Newest-first feed items from the room's transaction log.

    Every item carries the full field set (empty strings where unused) so the
    UI can switch on ``kind`` without missing-key crashes."""
    from platform_core import bidding_ops as bo
    pool_info: dict[str, tuple[str, str]] = {}
    try:
        for p in bo._pool(room):   # room pool, falling back to the bundled pool
            pool_info[p.get("name", "").lower()] = (p.get("role", ""), p.get("team", ""))
    except Exception:
        pass

    def role_team(player: str, t: dict) -> str:
        role = t.get("role") or pool_info.get(player.lower(), ("", ""))[0]
        team = t.get("player_team") or pool_info.get(player.lower(), ("", ""))[1]
        return " · ".join(x for x in (role, team) if x)

    items: list[dict[str, str]] = []
    for t in reversed(room.get("transactions", []) or []):
        kind = t.get("type", "")
        it = dict(_EMPTY)
        it["ts"] = t.get("ts", "")
        if kind == "market_buy":
            it.update(kind="buy", actor=t.get("participant", "?"),
                      player=t.get("player", "?"), amount=f"{t.get('amount', 0)}M",
                      detail=role_team(t.get("player", ""), t))
        elif kind == "trade":
            it.update(kind="trade",
                      from_name=t.get("from", "?"),
                      from_gave=_names_cash(t.get("give_players"), t.get("give_cash", 0)),
                      to_name=t.get("to", "?"),
                      to_gave=_names_cash(t.get("get_players"), t.get("get_cash", 0)),
                      loan="yes" if t.get("is_loan") else "no")
        elif kind in ("release", "half_release"):
            raw_refund = t.get("refund", 0)
            buy = int(t.get("buy_price", 0) or 0)
            legacy_refunded = raw_refund is True and not buy
            refund = 0 if raw_refund is False else (buy if raw_refund is True else int(raw_refund or 0))
            if t.get("auto"):
                mode = "auto-released at squad lock (no refund)"
            elif t.get("ko"):
                mode = f"knocked-out nation — half price, {refund}M back"
            elif legacy_refunded:
                mode = "released with refund"
            elif refund and buy and refund >= buy:
                mode = f"full price refunded, {refund}M back"
            elif refund:
                mode = f"paid release, {refund}M back"
            else:
                mode = "free release"
            sub = role_team(t.get("player", ""), t)
            if buy:
                sub = (sub + " · " if sub else "") + f"originally bought for {buy}M"
            it.update(kind="release", actor=t.get("participant", "?"),
                      player=t.get("player", "?"), mode=mode, sub=sub)
        else:
            continue
        items.append(it)
    # Transactions are appended chronologically, but sort by timestamp too so
    # backfilled/imported records still read newest-first (no-ts legacy records
    # keep their reversed append order at the end).
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items


class AnnounceState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    tab: str = "all"
    items: list[dict[str, str]] = []
    recent: list[dict[str, str]] = []     # compact preview for the Trade page
    n_all: str = "0"
    n_buys: str = "0"
    n_trades: str = "0"
    n_releases: str = "0"
    _raw: list[dict] = []

    @rx.event
    async def on_load_announcements(self):
        app = await self.get_state(AppState)
        code = ""
        for _ in range(60):
            code = (self.router._page.params.get("room", "") or "").upper()
            if code and (app.auth_user or app.is_hydrated):
                break
            await asyncio.sleep(0.05)
        if not code:
            return
        doc = await aload()
        room = doc.get("rooms", {}).get(code)
        spectator = app.grant_spectator_if_valid(
            code, room, self.router._page.params.get("spectate", "") or "")
        if not app.auth_user and not spectator:
            return rx.redirect("/")
        if room is None:
            return rx.redirect("/rooms") if app.auth_user else rx.redirect("/")
        self.room_code = code
        self.room_name = room.get("name", "")
        self.is_admin = (not spectator) and room.get("admin") == app.auth_user
        self._raw = build_feed(room)
        self._apply()

    def _apply(self):
        raw = self._raw
        self.n_all = str(len(raw))
        self.n_buys = str(sum(1 for i in raw if i["kind"] == "buy"))
        self.n_trades = str(sum(1 for i in raw if i["kind"] == "trade"))
        self.n_releases = str(sum(1 for i in raw if i["kind"] == "release"))
        want = {"all": None, "buys": "buy", "trades": "trade", "releases": "release"}[self.tab]
        self.items = [i for i in raw if want is None or i["kind"] == want][:120]
        self.recent = raw[:8]

    @rx.event
    def set_tab(self, tab: str):
        self.tab = tab
        self._apply()
