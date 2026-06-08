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
    squads_search: str = ""
    squads_search_results: list[dict[str, str]] = []
    locked_gws: list[str] = []
    view_locked_gw: str = ""
    locked_rows: list[dict[str, str]] = []
    confirm_release_player: str = ""
    current_gameweek: str = "0"
    gw1_locked: bool = False
    next_deadline: str = ""
    msg: str = ""
    rename_input: str = ""
    rename_error: str = ""
    squad_sort_by: str = "Price"
    # --- personal dashboard (the "hub") ---
    my_rank: str = "—"
    my_points: str = "0"
    my_bids: list[dict[str, str]] = []          # open bids I'm currently leading
    my_bids_total: str = "0"
    my_wins: list[dict[str, str]] = []          # open-bidding wins since my last visit
    hub_trades: list[dict[str, str]] = []       # trades proposed TO me (pending)

    @rx.event
    def select_sort_by(self, val: str):
        self.squad_sort_by = val
        code, doc, room = self._load()
        if room:
            self._refresh(room)
            self._compute_view(room)

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    @rx.event
    def handle_rename(self):
        code, doc, room = self._load()
        if not room:
            return
        from platform_core.admin_ops import rename_team, AdminError
        try:
            rename_team(room, self.my_team, self.rename_input)
            repo.save(doc)
            self.rename_error = ""
            self.my_team = self.rename_input.strip()
            self._refresh(room)
            return rx.window_alert(f"Team successfully renamed to {self.my_team}!")
        except AdminError as e:
            self.rename_error = str(e)
        except Exception as e:
            self.rename_error = "An error occurred."

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
        
        from platform_core.season_ops import _is_football
        is_fb = _is_football(room)
        
        def get_pos_weight(role_str):
            r = (role_str or "").lower()
            if is_fb:
                if "keeper" in r or r == "gk": return 1
                if "def" in r or "back" in r: return 2
                if "mid" in r: return 3
                return 4
            else:
                if "keep" in r or "wk" in r: return 1
                if "bat" in r: return 2
                if "all" in r or "ar" in r: return 3
                if "bowl" in r: return 4
                return 5

        squad_data = me.get("squad", [])
        if isinstance(squad_data, dict):
            squad_data = list(squad_data.values())

        def safe_price(p):
            try:
                return float(p.get("buy_price", 0))
            except (ValueError, TypeError):
                return 0

        if self.squad_sort_by == "Position":
            sorted_squad = sorted(squad_data, key=lambda x: (get_pos_weight(x.get("role")), -safe_price(x)))
        else:
            sorted_squad = sorted(squad_data, key=lambda x: -safe_price(x))

        self.my_squad = [
            {"name": e.get("name", "Unknown"), "role": e.get("role", ""), "team": e.get("team", ""),
             "price": str(e.get("buy_price", 0)),
             "ir": "yes" if e.get("name") == me.get("ir") else "no"}
            for e in sorted_squad
        ]
        p1_lbl, p2_lbl, p3_lbl, p4_lbl = ("GK", "DEF", "MID", "FWD") if is_fb else ("BAT", "BOWL", "AR", "WK")

        def _counts(sq):
            c = {"p1": 0, "p2": 0, "p3": 0, "p4": 0}
            for e in sq:
                r = (e.get("role") or "").lower()
                if is_fb:
                    if "keeper" in r or r == "gk": c["p1"] += 1
                    elif "def" in r or "back" in r: c["p2"] += 1
                    elif "mid" in r: c["p3"] += 1
                    else: c["p4"] += 1
                else:
                    if "keep" in r or "wk" in r: c["p4"] += 1
                    elif "all" in r or "ar" in r: c["p3"] += 1
                    elif "bowl" in r: c["p2"] += 1
                    else: c["p1"] += 1
            return c

        self.teams = []
        for p in room.get("participants", []):
            sq = p.get("squad", [])
            c = _counts(sq)
            self.teams.append({
                "name": p["name"], "budget": str(p.get("budget", 0)),
                "squad": str(len(sq)),
                "p1_lbl": p1_lbl, "p2_lbl": p2_lbl, "p3_lbl": p3_lbl, "p4_lbl": p4_lbl,
                "p1": str(c["p1"]), "p2": str(c["p2"]),
                "p3": str(c["p3"]), "p4": str(c["p4"]),
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
        
        from platform_core.season_ops import _is_football
        is_fb = _is_football(room)
        
        def get_pos_weight(role_str):
            r = (role_str or "").lower()
            if is_fb:
                if "keeper" in r or r == "gk": return 1
                if "def" in r or "back" in r: return 2
                if "mid" in r: return 3
                return 4
            else:
                if "keep" in r or "wk" in r: return 1
                if "bat" in r: return 2
                if "all" in r or "ar" in r: return 3
                if "bowl" in r: return 4
                return 5

        squad_data = p.get("squad", [])
        if isinstance(squad_data, dict):
            squad_data = list(squad_data.values())

        def safe_price_view(pl):
            try:
                return float(pl.get("buy_price", 0))
            except (ValueError, TypeError):
                return 0

        if self.squad_sort_by == "Position":
            sorted_squad = sorted(squad_data, key=lambda x: (get_pos_weight(x.get("role")), -safe_price_view(x)))
        else:
            sorted_squad = sorted(squad_data, key=lambda x: -safe_price_view(x))

        self.view_squad = [
            {"name": e.get("name", "Unknown"), "role": e.get("role", ""), "team": e.get("team", ""),
             "price": str(e.get("buy_price", 0)),
             "ir": "yes" if e.get("name") == p.get("ir") else "no"}
            for e in sorted_squad
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
    def do_squads_search(self):
        code, doc, room = self._load()
        if not room: return
        query = self.squads_search.lower().strip()
        results = []
        if query:
            for p in room.get("participants", []):
                for e in p.get("squad", []):
                    if query in e.get("name", "").lower():
                        results.append({
                            "name": e["name"],
                            "role": e.get("role", ""),
                            "team": p["name"],
                            "price": str(e.get("buy_price", 0)),
                            "ir": "yes" if e["name"] == p.get("ir") else "no"
                        })
        self.squads_search_results = results

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
    def set_confirm_release_player(self, player: str):
        self.confirm_release_player = player

    @rx.event
    def half_release(self, player: str):
        self.confirm_release_player = ""
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
