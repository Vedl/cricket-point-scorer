"""Room hub state — replaces the (removed) in-app live auction.

The live auction now happens off-app (Zoom); the hub shows the participant's own
team (budget, squad, IR) and every other team at a glance, plus IR selection and
half-price releases.
"""

from __future__ import annotations

import reflex as rx

from platform_core import season_ops as so
from platform_core.season_ops import SeasonError

from .state import AppState, repo


class RoomState(rx.State):
    room_code: str = ""
    room_name: str = ""
    tournament: str = ""
    is_admin: bool = False
    my_team: str = ""

    my_budget: int = 0
    my_squad: list[dict[str, str]] = []
    my_ir: str = ""
    teams: list[dict[str, str]] = []
    # detailed squads viewer
    all_team_names: list[str] = []
    view_team_sel: str = ""
    view_squad: list[dict[str, str]] = []
    view_budget: str = "0"
    view_ir: str = ""
    locked_gws: list[str] = []
    view_locked_gw: str = ""
    locked_rows: list[dict[str, str]] = []
    current_gameweek: str = "0"
    gw1_locked: bool = False
    next_deadline: str = ""
    msg: str = ""
    # --- personal dashboard (the "hub") ---
    my_rank: str = "—"
    my_points: str = "0"
    my_bids: list[dict[str, str]] = []          # open bids I'm currently leading
    my_bids_total: str = "0"
    my_wins: list[dict[str, str]] = []          # open-bidding wins since my last visit
    hub_trades: list[dict[str, str]] = []       # trades proposed TO me (pending)

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    async def on_load_hub(self):
        app = await self.get_state(AppState)
        code, doc, room = self._load()
        if not code:
            return  # room param not ready yet — don't bounce
        if room is None:
            # Only treat as a real "missing room" once we're fully hydrated AND the
            # user is known — never evict on a transient hydration/reconnect race.
            if app.is_hydrated and app.auth_user:
                return rx.redirect("/rooms")
            return
        self.room_code = code
        self.room_name = room.get("name", "")
        self.tournament = room.get("tournament_type", "")
        app.active_tournament = self.tournament   # drives per-room theming
        self.is_admin = room.get("admin") == app.auth_user
        self.my_team = next((p["name"] for p in room.get("participants", [])
                             if p.get("user") == app.auth_user), "")
        self.current_gameweek = str(room.get("current_gameweek", 0) or 0)
        self.gw1_locked = bool(room.get("gw1_locked"))
        self._refresh(room)
        if self._compute_dashboard(room):
            repo.save(doc)   # persist "seen" marker only when new wins appeared
        # Click-through from a team card: ?team=NAME preselects that squad.
        team_param = self.router._page.params.get("team", "")
        if team_param and team_param in self.all_team_names:
            self.view_team_sel = team_param
            self._compute_view(room)

    def _compute_dashboard(self, room: dict) -> bool:
        """Populate the personal hub widgets. Returns True if the document was
        mutated (the 'wins seen' marker advanced) and should be saved."""
        from platform_core import market_ops as mo

        me = self.my_team
        # Open bids I'm currently leading.
        ob = room.get("open_bids", {})
        bids = [{"player": n, "amount": str(b.get("high_bid", 0))}
                for n, b in ob.items() if b.get("high_bidder") == me]
        bids.sort(key=lambda x: -int(x["amount"]))
        self.my_bids = bids
        self.my_bids_total = str(sum(int(b["amount"]) for b in bids))

        # Trades proposed to me (I receive give_players, I give get_players).
        self.hub_trades = [
            {"id": t["id"],
             "text": (f"{t['from']} → you receive [{', '.join(t['give_players']) or '—'}]"
                      f"{(' +'+str(t['give_cash'])+'M') if t.get('give_cash') else ''}, "
                      f"give [{', '.join(t['get_players']) or '—'}]"
                      f"{(' +'+str(t['get_cash'])+'M') if t.get('get_cash') else ''}")}
            for t in mo.incoming_trades(room, me)]

        # Current standings rank.
        try:
            standings = so.compute_cumulative_standings(room)
            names = [r["participant"] for r in standings]
            if me in names:
                i = names.index(me)
                self.my_rank = f"{i + 1} / {len(names)}"
                self.my_points = str(standings[i]["points"])
            else:
                self.my_rank, self.my_points = "—", "0"
        except Exception:
            self.my_rank, self.my_points = "—", "0"

        # Open-bidding wins since my last hub visit.
        my_buys = [t for t in room.get("transactions", [])
                   if t.get("type") == "market_buy" and t.get("participant") == me]
        me_p = next((p for p in room.get("participants", []) if p["name"] == me), None)
        seen = (me_p or {}).get("seen_buys", 0)
        self.my_wins = [{"player": t["player"], "amount": str(t.get("amount", 0))}
                        for t in my_buys[seen:]]
        if me_p is not None and len(my_buys) != seen:
            me_p["seen_buys"] = len(my_buys)
            return True
        return False

    def _refresh(self, room: dict):
        by = {p["name"]: p for p in room.get("participants", [])}
        me = by.get(self.my_team, {})
        self.my_budget = me.get("budget", 0)
        self.my_ir = me.get("ir") or ""
        self.my_squad = [
            {"name": e["name"], "role": e.get("role", ""), "team": e.get("team", ""),
             "price": str(e.get("buy_price", 0)),
             "ir": "yes" if e["name"] == me.get("ir") else "no"}
            for e in sorted(me.get("squad", []), key=lambda x: -x.get("buy_price", 0))
        ]
        def _counts(sq):
            c = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
            for e in sq:
                r = (e.get("role") or "").lower()
                if "keeper" in r or r == "gk":
                    c["GK"] += 1
                elif "def" in r or "back" in r:
                    c["DEF"] += 1
                elif "mid" in r:
                    c["MID"] += 1
                else:
                    c["FWD"] += 1
            return c

        self.teams = []
        for p in room.get("participants", []):
            sq = p.get("squad", [])
            c = _counts(sq)
            self.teams.append({
                "name": p["name"], "budget": str(p.get("budget", 0)),
                "squad": str(len(sq)),
                "gk": str(c["GK"]), "def": str(c["DEF"]),
                "mid": str(c["MID"]), "fwd": str(c["FWD"]),
                "status": "out" if p.get("is_eliminated") else "in",
                "is_me": "yes" if p["name"] == self.my_team else "no"})
        # nearest upcoming deadline (the single bidding deadline)
        bd = room.get("bidding_deadline")
        self.next_deadline = bd[:16].replace("T", " ") if bd else ""

        # squads viewer
        self.all_team_names = [p["name"] for p in room.get("participants", [])]
        if not self.view_team_sel or self.view_team_sel not in self.all_team_names:
            self.view_team_sel = self.my_team or (self.all_team_names[0] if self.all_team_names else "")
        self._compute_view(room)
        self.locked_gws = sorted(room.get("gameweek_squads", {}).keys(), key=lambda g: (len(g), g))
        if not self.view_locked_gw and self.locked_gws:
            self.view_locked_gw = self.locked_gws[-1]
        self._compute_locked(room)

    def _compute_view(self, room: dict):
        by = {p["name"]: p for p in room.get("participants", [])}
        p = by.get(self.view_team_sel, {})
        self.view_budget = str(p.get("budget", 0))
        self.view_ir = p.get("ir") or ""
        self.view_squad = [
            {"name": e["name"], "role": e.get("role", ""), "team": e.get("team", ""),
             "price": str(e.get("buy_price", 0)),
             "ir": "yes" if e["name"] == p.get("ir") else "no"}
            for e in sorted(p.get("squad", []), key=lambda x: -x.get("buy_price", 0))
        ]

    def _compute_locked(self, room: dict):
        snap = room.get("gameweek_squads", {}).get(self.view_locked_gw, {})
        team = snap.get(self.view_team_sel) if isinstance(snap, dict) else None
        rows = []
        if isinstance(team, dict):
            ir = team.get("ir")
            for e in team.get("squad", []):
                rows.append({"name": e["name"], "role": e.get("role", ""),
                             "ir": "yes" if e["name"] == ir else "no"})
        self.locked_rows = rows

    @rx.event
    def select_view_team(self, name: str):
        self.view_team_sel = name
        code, doc, room = self._load()
        if room:
            self._compute_view(room)
            self._compute_locked(room)

    @rx.event
    def select_locked_gw(self, gw: str):
        self.view_locked_gw = gw
        code, doc, room = self._load()
        if room:
            self._compute_locked(room)

    @rx.event
    def set_ir(self, player: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            so.set_ir(room, self.my_team, player)
        except SeasonError as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self._refresh(room)
        self.msg = f"🩹 IR set to {player}."

    @rx.event
    def clear_ir(self):
        code, doc, room = self._load()
        if not room:
            return
        so.set_ir(room, self.my_team, None)
        repo.save(doc)
        self._refresh(room)
        self.msg = "IR cleared."

    @rx.event
    def hub_accept_trade(self, trade_id: str):
        from platform_core import market_ops as mo
        from season_engine.trading import TradeError
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            mo.accept_trade(room, trade_id)
        except TradeError as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self._refresh(room)
        self._compute_dashboard(room)
        self.msg = "✅ Trade accepted — sent to the admin for approval."

    @rx.event
    def hub_reject_trade(self, trade_id: str):
        from platform_core import market_ops as mo
        code, doc, room = self._load()
        if not room:
            return
        mo.reject_trade(room, trade_id)
        repo.save(doc)
        self._refresh(room)
        self._compute_dashboard(room)
        self.msg = "Trade rejected."

    @rx.event
    def half_release(self, player: str):
        self.msg = ""
        code, doc, room = self._load()
        if not room:
            return
        try:
            refund = so.half_price_release(room, self.my_team, player)
        except SeasonError as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self._refresh(room)
        self.msg = f"🗑️ Released {player} for +{refund}M (half price)."
