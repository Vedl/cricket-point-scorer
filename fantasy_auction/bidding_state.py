"""Open-bidding state — deadline-driven, frozen until the admin sets a deadline."""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime, timedelta

import reflex as rx

from platform_core import bidding_ops as bo
from platform_core import season_ops as so
from platform_core.textutil import fold
from season_engine.open_bidding import BidError, MIN_BID, raise_only_next

from .state import AppState, aload, repo
from .liveness import client_connected

_WINDOW_LABEL = {
    "frozen": "🔒 Frozen — waiting for the admin to set a deadline",
    "open": "🟢 Open — bid on new players or raise",
    "no_new": "🟡 Closing soon — raise existing bids only (no new players)",
    "raise_only": "🟠 Final window — raise existing bids in +5M steps only",
    "closed": "🔴 Closed — bids being awarded",
}


# Process-wide guard against an "expired-bid thundering herd": every connected
# client's live_loop ticks independently, and when a popular bid expires they would
# ALL do the expensive full-document load + process + save at the same instant — a
# write storm that spikes memory/CPU on the tiny free VM exactly when an auction is
# busiest. We coalesce that heavy work to at most once per room per cooldown window;
# other coroutines skip it (the awarded result is visible to them on the next read).
# The check-and-set is atomic under asyncio (no await between get and set).
_last_expire_process: dict[str, float] = {}
_EXPIRE_COOLDOWN = 5.0


def _claim_expire_processing(code: str) -> bool:
    now = _time.monotonic()
    if now - _last_expire_process.get(code, 0.0) >= _EXPIRE_COOLDOWN:
        _last_expire_process[code] = now
        return True
    return False


def _countdown(when, now) -> str:
    # Coerce both sides to naive-local before subtracting. A stored deadline parsed as
    # timezone-AWARE minus a naive datetime.now() raises TypeError ("can't subtract
    # offset-naive and offset-aware datetimes") — the timezone crash that kept blanking
    # the bidding view for some users. Normalising here makes the math impossible to
    # throw regardless of how the timestamp was stored.
    try:
        if getattr(when, "tzinfo", None) is not None:
            when = when.astimezone().replace(tzinfo=None)
        if getattr(now, "tzinfo", None) is not None:
            now = now.astimezone().replace(tzinfo=None)
        secs = int((when - now).total_seconds())
    except Exception:
        return ""
    if secs <= 0:
        return "passed"
    # Emit an aware ISO (local offset) so the client's react-countdown parses an exact
    # instant rather than guessing the browser's timezone.
    return when.astimezone().isoformat()


def _min_next_amount(cur: int, window: str) -> int:
    """Smallest amount that is a valid next bid on a player, given the current window.

    Mirrors ``season_engine.open_bidding`` (min 5M; +5M steps once a bid reaches 50M)
    but folds in the raise-only endgame, where any raise must clear ``cur+5`` AND land
    on a 5M multiple. Used to prefill the Amount box and to power one-tap "Outbid" — so
    a single click always lands a bid the backend will accept."""
    if cur <= 0:
        return MIN_BID
    if window == "raise_only":
        return raise_only_next(cur)
    if cur >= 50:
        return cur + 5
    return cur + 1


class BiddingState(rx.State):
    room_code: str = ""
    room_name: str = ""
    is_admin: bool = False
    is_spectator: bool = False
    my_team: str = ""
    my_budget: int = 0

    search: str = ""
    available: list[dict[str, str]] = []
    active: list[dict[str, str]] = []
    bid_player: str = ""
    bid_amount: str = ""
    # Folded name of the player the Amount box was last auto-prefilled for. Guards the
    # prefill so re-searching the SAME player doesn't clobber a manual amount edit.
    _prefill_for: str = ""
    window: str = "frozen"
    window_label: str = ""
    deadline_str: str = ""
    milestones: list[dict[str, str]] = []
    # Backend-only cache of every unowned pool player (never synced to the client;
    # it feeds the search-as-you-type filtering without a Firebase read).
    _pool_cache: list[dict] = []
    # search-as-you-type dropdown + combinable filters
    suggestions: list[dict[str, str]] = []
    country_sel: str = "All countries"
    role_sel: str = "All positions"
    countries: list[str] = ["All countries"]
    roles: list[str] = ["All positions"]
    msg: str = ""

    watching: bool = False
    loop_running: bool = False
    # Consecutive ticks our own client was absent from Reflex's live-socket map.
    # Backend var (leading underscore) so it never goes over the wire. Two strikes
    # → live_loop self-terminates instead of forever emitting deltas to a
    # disconnected client.
    _liveness_misses: int = 0

    @rx.var
    def bidding_open(self) -> bool:
        """True when bids can currently be placed/raised — gates the Outbid button."""
        return self.window in ("open", "no_new", "raise_only")

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    def _load(self):
        code = (self.router._page.params.get("room", "") or "").upper()
        doc = repo.load()
        return code, doc, doc.get("rooms", {}).get(code)

    def _resolve_identity(self, app, room: dict, code: str, spectate_param: str = "") -> None:
        """(Re)compute member identity from the (possibly late-hydrated) auth user.

        Called on load AND every live_loop tick. Only ever UPGRADES: once a real
        team/admin is resolved it's sticky, so a reconnect that briefly reads an empty
        ``auth_user`` can't demote a member to the read-only spectator view."""
        user = app.auth_user
        if user:
            if room.get("admin") == user:
                self.is_admin = True
            team = next((p["name"] for p in room.get("participants", [])
                         if p.get("user") == user), "")
            if team:
                self.my_team = team
        if self.is_admin or self.my_team:
            self.is_spectator = False
            return
        self.is_spectator = app.grant_spectator_if_valid(code, room, spectate_param)

    @rx.event
    async def on_load_bidding(self):
        app = await self.get_state(AppState)
        # Break as soon as inputs are ready (usually instant). Don't wait on
        # is_hydrated — it's set only after on_load finishes, so a foreground handler
        # can never observe it flip; the old loop just burned ~5s on every load.
        code = ""
        for _ in range(60):
            code = (self.router._page.params.get("room", "") or "").upper()
            if code:
                break
            await asyncio.sleep(0.05)
        if not code:
            return
        # Give the persisted auth user a moment to hydrate before member-vs-spectator
        # is decided. is_hydrated can flip BEFORE this LocalStorage value arrives on
        # mobile/PWA, which was demoting real members to the read-only view. live_loop
        # re-resolves every tick too, so a late arrival self-heals with no reload.
        for _ in range(20):  # ~1s grace; a genuine spectator never has auth_user
            if app.auth_user:
                break
            await asyncio.sleep(0.05)
        doc = await aload()
        room = doc.get("rooms", {}).get(code)
        spectate_param = self.router._page.params.get("spectate", "") or ""
        spectator = app.grant_spectator_if_valid(code, room, spectate_param)
        if not app.auth_user and not spectator:
            return rx.redirect("/")
        if room is None:
            return rx.redirect("/rooms") if app.auth_user else rx.redirect("/")
        self.room_code = code
        self.room_name = room.get("name", "")
        self._resolve_identity(app, room, code, spectate_param)
        self.msg = ""
        # Awarding + the first refresh are guarded so a single malformed bid/date can't
        # abort the whole load (Reflex discards a handler's state update on exception,
        # which would leave the participant staring at an empty page). Worst case the
        # first paint is sparse and the resilient live_loop fills it in seconds later.
        try:
            awarded = bo.process_expired(room, datetime.now())
            if awarded:
                repo.save(doc)
                from fantasy_auction import notify
                notify.signed_many(room, awarded, self.room_code)
        except Exception as exc:
            print(f"[on_load_bidding] award skipped: {exc}")
        try:
            self._refresh(room)
        except Exception as exc:
            print(f"[on_load_bidding] initial refresh failed: {exc}")
        self.watching = True
        if not self.loop_running:
            return BiddingState.live_loop

    def _refresh(self, room: dict, *, full: bool = True):
        """Recompute view state from ``room``.

        ``full`` rebuilds the backend-only pool cache (every unowned player) that
        feeds search-as-you-type + the filter dropdowns. The per-client ``live_loop``
        ticks every few seconds for every connected tab, so it passes ``full=False``:
        rebuilding a 1000+-row list on every tick across all clients was a major CPU
        drain on the single-CPU free VM. The pool only changes when players are
        acquired/released, so it's refreshed on load and on user actions instead."""
        by = {p["name"]: p for p in room.get("participants", [])}
        new_my_budget = by.get(self.my_team, {}).get("budget", 0)
        if self.my_budget != new_my_budget:
            self.my_budget = new_my_budget

        new_available = [
            {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
            for p in bo.available_players(room, search=self.search,
                                          country=self._country, role=self._role, limit=50)
        ]
        if self.available != new_available:
            self.available = new_available

        if full:
            self._pool_cache = [
                {"name": p["name"], "role": p.get("role", ""), "team": p.get("team", "")}
                for p in bo.available_players(room, limit=5000)
            ]
            new_countries = ["All countries"] + sorted(
                {p["team"] for p in self._pool_cache if p["team"]})
            if self.countries != new_countries:
                self.countries = new_countries
            new_roles = ["All positions"] + sorted(
                {p["role"] for p in self._pool_cache if p["role"]})
            if self.roles != new_roles:
                self.roles = new_roles

        now = datetime.now()
        new_window = bo.window_state(room, now)

        new_active = []
        for b in bo.active(room):
            expires_iso = b.get("expires", "")
            time_left = ""
            if expires_iso:
                try:
                    exp_dt = datetime.fromisoformat(expires_iso)
                    if exp_dt.tzinfo is not None:
                        exp_dt = exp_dt.astimezone().replace(tzinfo=None)
                    time_left = _countdown(exp_dt, now)
                except Exception:
                    pass
            high_bid = int(b.get("high_bid", 0))
            new_active.append({
                "player": b.get("player", "Unknown"), "team": b.get("team", ""), "role": b.get("role", ""), "high_bid": str(high_bid),
                "high_bidder": b.get("high_bidder", ""), "expires": expires_iso, "time_left": time_left,
                "mine": "yes" if b.get("high_bidder") == self.my_team else "no",
                # Amount a one-tap Outbid would place — the min valid raise for this window.
                "min_next": str(_min_next_amount(high_bid, new_window)),
            })
        if self.active != new_active:
            self.active = new_active

        if self.window != new_window:
            self.window = new_window
            self.window_label = _WINDOW_LABEL.get(self.window, "")
            
        dl = bo.bidding_deadline(room)
        new_deadline_str = dl.strftime("%a %d %b, %H:%M") if dl else ""
        if self.deadline_str != new_deadline_str:
            self.deadline_str = new_deadline_str
            
        if dl:
            new_milestones = [
                {"label": "🆕 New-player bids close", "left": _countdown(dl - timedelta(minutes=60), now)},
                {"label": "5️⃣ +5M-only window starts", "left": _countdown(dl - timedelta(minutes=30), now)},
                {"label": "🔨 Bidding closes (bids award)", "left": _countdown(dl, now)},
                {"label": "🔒 Trading closes → squads lock + new GW", "left": _countdown(dl + timedelta(minutes=30), now)},
            ]
        else:
            new_milestones = []
            
        if self.milestones != new_milestones:
            self.milestones = new_milestones

    # --- search-as-you-type + filters (in-memory over the cached pool) ------- #
    @property
    def _country(self) -> str:
        return "" if self.country_sel in ("", "All countries") else self.country_sel

    @property
    def _role(self) -> str:
        return "" if self.role_sel in ("", "All positions") else self.role_sel

    def _apply_filters(self):
        """Filter the cached unowned-pool list — no Firebase read per keystroke."""
        s = fold(self.search)
        out = []
        for p in self._pool_cache:
            if self._country and p["team"] != self._country:
                continue
            if self._role and p["role"] != self._role:
                continue
            if s and s not in fold(p["name"]) and s not in fold(p["team"]):
                continue
            out.append(p)
            if len(out) >= 50:
                break
        self.available = out
        if s and len(s) >= 2:
            sugg = [p for p in self._pool_cache if s in fold(p["name"])][:8]
            # hide the dropdown once the box holds an exact player name
            if len(sugg) == 1 and fold(sugg[0]["name"]) == s:
                sugg = []
            self.suggestions = sugg
        else:
            self.suggestions = []

    def _maybe_prefill(self, player_exact: str):
        """Prefill the Amount box with the minimum valid next bid for a fully-resolved
        player — its current-bid + increment if it's already in Active bids, else 5M.

        Only fires when the target player *changes*, so a manual amount edit for the same
        player isn't overwritten as the user keeps typing/refiltering."""
        f = fold(player_exact)
        if f == self._prefill_for:
            return
        self._prefill_for = f
        match = next((b for b in self.active if fold(b["player"]) == f), None)
        cur = int(match["high_bid"]) if match else 0
        self.bid_amount = str(_min_next_amount(cur, self.window))

    @rx.event
    def set_search(self, value: str):
        self.search = value
        self._apply_filters()
        # When the box resolves to an exact player, seed a sensible Amount: the going
        # price + increment if they're already being bid on, otherwise the 5M minimum.
        f = fold(value)
        if f and (any(fold(b["player"]) == f for b in self.active)
                  or any(fold(p["name"]) == f for p in self._pool_cache)):
            self._maybe_prefill(value)
        else:
            self._prefill_for = ""

    @rx.event
    def set_country(self, value: str):
        self.country_sel = value
        self._apply_filters()

    @rx.event
    def set_role(self, value: str):
        self.role_sel = value
        self._apply_filters()

    @rx.event
    def pick(self, player: str):
        """Choose a player (from the dropdown or a row's Bid button)."""
        self.search = player
        self.bid_player = player
        self.suggestions = []
        self._apply_filters()
        self._maybe_prefill(player)

    @rx.event
    def do_search(self):
        code, doc, room = self._load()
        if room:
            self._refresh(room)

    def _do_place(self, target: str, amount_str: str):
        """Core bid placement shared by the console 'Place bid' and one-tap 'Outbid'.

        Takes an explicit target + amount so 'Outbid' can bid on an Active-bids row
        without hijacking the search box the user may be typing into."""
        self.msg = ""
        if self.is_spectator:
            return
        target = (target or "").strip()
        if not target:
            self.msg = "⚠️ Pick a player to bid on first."
            return
        code, doc, room = self._load()
        if not room:
            return
        # Who currently leads this player? Capture before placing so we can tell whom
        # (if anyone) this bid outbids.
        _tf = fold(target)
        _prev = next((b for n, b in room.get("open_bids", {}).items() if fold(n) == _tf), None)
        prev_bidder = (_prev or {}).get("high_bidder", "")
        try:
            bo.place(room, self.my_team, target, int(amount_str or 0), datetime.now())
        except (BidError, ValueError) as exc:
            self.msg = f"⚠️ {exc}"
            return
        repo.save(doc)
        self.bid_amount = ""
        self._prefill_for = ""
        self._refresh(room)
        canonical = next((n for n in room.get("open_bids", {}) if fold(n) == fold(target)), target)
        self.msg = f"✅ Bid placed on {canonical}."
        # Push: the previous leader (if any, and not us) was just outbid.
        if prev_bidder and prev_bidder != self.my_team:
            from fantasy_auction import notify
            notify.outbid(room, prev_bidder, canonical, code)

    @rx.event
    def place_bid(self):
        self._do_place(self.search or self.bid_player, self.bid_amount)

    @rx.event
    def outbid(self, player: str):
        """One-tap outbid straight from the Active bids list — places the minimum valid
        raise for the current window, no searching required."""
        if self.is_spectator:
            return
        match = next((b for b in self.active if fold(b["player"]) == fold(player)), None)
        cur = int(match["high_bid"]) if match else 0
        self._do_place(player, str(_min_next_amount(cur, self.window)))

    @rx.event(background=True)
    async def live_loop(self):
        async with self:
            if self.loop_running:
                return
            self.loop_running = True
        try:
            while True:
                async with self:
                    if not self.watching or not self.room_code:
                        return
                    # Self-terminate once our own client is gone, instead of
                    # ticking forever and emitting deltas Reflex discards with a
                    # "disconnected client" warning. Two consecutive misses
                    # (~2 ticks = ~12s at the 6s interval below) before quitting,
                    # so a live client surviving a transient gap is spared.
                    if client_connected(self):
                        self._liveness_misses = 0
                    else:
                        self._liveness_misses += 1
                        if self._liveness_misses >= 2:
                            self.watching = False
                            return
                    code = self.room_code
                # Each tick is wrapped so a single bad read/refresh (a malformed bid,
                # a date edge case, a transient Firebase hiccup) can NEVER kill the
                # loop. Before this, one exception ended the task and that participant
                # was frozen — seeing the page but no further live updates — while
                # others kept updating. That's the "some see it, some don't" symptom.
                try:
                    # Cheap per-room read (~20-50 KB), served from the 20s cache most
                    # ticks, instead of the ~1 MB full doc.
                    room = await asyncio.to_thread(repo.load_room, code)
                    if room is not None:
                        now = datetime.now()
                        now_iso = now.isoformat()
                        has_expired = any(now_iso >= b.get("expires", now_iso) for b in room.get("open_bids", {}).values())
                        # Deadline timeline (award at T, lock+advance+freeze at T+30m)
                        # is driven from here too, so it fires even when the
                        # server-wide scheduler thread is disabled — any connected
                        # client keeps the room on schedule.
                        deadline_due = so.deadline_work_due(room, now)
                        # Only ONE client coroutine does the heavy full-doc award per
                        # cooldown window; the rest keep rendering from the cheap read.
                        if (has_expired or deadline_due) and _claim_expire_processing(code):
                            doc = await aload()
                            full_room = doc.get("rooms", {}).get(code)
                            if full_room:
                                awarded = bo.process_expired(full_room, now)
                                changed = bool(awarded)
                                changed = bool(so.process_room_deadline(full_room, now)) or changed
                                if changed:
                                    repo.save(doc)
                                    # Only the client that claimed processing reaches
                                    # here, so each signing is pushed exactly once.
                                    if awarded:
                                        from fantasy_auction import notify
                                        notify.signed_many(full_room, awarded, code)
                                room = full_room
                        # Timed deadline push alerts (1h/30m/at each milestone), driven
                        # from this loop so they fire from normal app activity — no
                        # external cron needed. Throttled + deduped inside dispatch.
                        try:
                            from platform_core import push
                            await asyncio.to_thread(
                                push.dispatch_due_alerts, code, bo.bidding_deadline(room), now)
                        except Exception as exc:
                            print(f"[bidding live_loop] push dispatch: {exc}")

                        async with self:
                            # Re-resolve identity: a member whose auth_user hydrated late
                            # (mobile/PWA) is promoted out of the read-only view here.
                            # get_state MUST be inside the lock in a background task.
                            app = await self.get_state(AppState)
                            self._resolve_identity(app, room, code)
                            # Skip the heavy 1000-row datalist rebuild on every tick.
                            self._refresh(room, full=False)
                except Exception as exc:  # keep the live updater alive no matter what
                    print(f"[bidding live_loop] tick failed, continuing: {exc}")
                await asyncio.sleep(6)
        finally:
            async with self:
                self.loop_running = False

    @rx.event
    def stop_watching(self):
        self.watching = False
