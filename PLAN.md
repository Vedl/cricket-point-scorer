# Migration Plan — Fantasy Auction Platform (Streamlit → Reflex)

**Status:** Phase 0 (Audit & Plan). **Awaiting approval before any build work.**
**Date:** 2026-06-02

---

## 0. Critical findings before you read anything else

Two things diverge from the build spec. Both change scope, so they are flagged up front and
expanded in [§6 Ambiguities](#6-ambiguities--decisions-needed-read-before-approving).

### Finding A — There is no `legacy/` directory.
The spec says the working Streamlit app lives in `legacy/`. It does not. The live app is at the
**repo root**: `streamlit_app.py` (5,574 lines) + `backend/storage.py` (Firebase persistence) +
`ui_theme.py` + the scoring/scraper modules + the JSON data files. There is also an unrelated
`api_server.py` (4,689 lines, FastAPI), a `frontend/` (React) and `flutter_frontend/` — these are
**separate companion frontends and a parallel FastAPI experiment**, not the auction app. The auction
that the spec describes is **entirely inside `streamlit_app.py`**. I treated that file + its imports as
the source of truth. (No code was moved; I'll leave the repo layout as-is and build the new app in a
new top-level directory.)

### Finding B — The legacy app is a full season-long fantasy platform; the spec describes only the auction.
The spec's hard requirements, data model, and acceptance criteria are **100% about the live auction**
(the draft). But the actual app does far more: live score scraping, Best-11 scoring, gameweek
processing, a full trading market, loans, knockout elimination, standings, and ~20 admin tools. The
spec's data model (`Event/Player/Participant/RosterEntry/AuctionState/BidLog`) cannot express
trading/scoring/knockouts.

> **DECISION (2026-06-02): full feature parity — auction + season management.** The user chose to port
> the *entire* platform, not just the auction. This plan is therefore written for full parity: the data
> model is expanded beyond the spec's sketch ([§4](#4-target-architecture)) and extra phases are added
> for scoring, trading, knockouts, and standings ([§5](#5-build-phases-commit--green-tests-after-each)).
> The spec's auction requirements remain the *core*; everything else is ported around it.

---

## 1. Feature inventory (everything the legacy app does)

Legend: **[AUCTION]** = in the spec's scope · **[SEASON]** = season-management, beyond the spec's
data model · **[INFRA]** = platform/auth/persistence.

### 1.1 Auth & navigation `streamlit_app.py:442-657, 4318-end`
- **[INFRA]** Username/password register + login (SHA-256 hashed, stored in `auction_data["users"]`). *Spec
  replaces this with room-code + display-name for participants and an env admin key — see §6.2.*
- **[INFRA]** Password reset (verify by a room code you belong to). 
- **[INFRA]** Auto-login from URL query params (`?user=&room=`) — link-based re-entry.
- **[INFRA]** Room selection: create room, join by 6-char code, list "your rooms".
- **[INFRA]** Top-level routing: login → room-selection → in-room app.

### 1.2 Room / event configuration `streamlit_app.py:536-657`
- **[AUCTION]** Create room with: name, **tournament type** (`T20 World Cup`, `IPL 2026`, `FIFA World Cup
  2026`), admin, "admin participates as manager" flag.
- **[AUCTION]** Per-tournament player pool loaded from JSON (`get_tournament_players`).
- **[AUCTION]** Default participant budget = **100** (a one-click "+150M to everyone" admin boost exists).
- **[AUCTION]** Squad cap surfaced in UI as **/30**; Best-11 needs ≥19 for an IR slot (season rule).

### 1.3 Live auction (the core) `streamlit_app.py:663-1226`
**This is the heart of the migration.** Runs in a `@st.fragment(run_every=5)` — the polling hack that
fakes real-time. State lives in `room["live_auction"]`:
`active, current_team, player_queue, current_player, current_player_role, current_bid, current_bidder,
timer_start, timer_duration (60s), opted_out[], auction_started_at`.

- **[AUCTION]** Admin starts auction **by team**: picks a real-world team; that team's undrafted players
  are queued, sorted by role (`WK-Batsman→Batsman→Batting AR→Bowling AR→Bowler`).
- **[AUCTION]** Players auctioned one at a time with a **countdown timer** (default 60s; resets on each
  new bid).
- **[AUCTION]** **Dynamic bid increments:** `<50 → +1`, `50–99 → +5`, `≥100 → +10`. `min_bid =
  max(5, current_bid + increment)`. Bids ≥50 must be multiples of 5; bids >100 multiples of 10.
- **[AUCTION]** **Budget enforcement:** a bid cannot exceed the bidder's remaining budget.
- **[AUCTION]** **Opt out** of bidding on current player; admin can **revive** an opted-out bidder.
- **[AUCTION]** **Auto-sell** when timer hits 0 with a bidder, *or* when all other active bidders opted
  out. **Auto-pass (unsold)** when timer hits 0 with no bidder.
- **[AUCTION]** **Admin overrides:** Pause, Force-Sell, Force-Unsold.
- **[AUCTION]** **On sale:** append `{name, role, team, buy_price}` to winner squad, deduct budget,
  append to `auction_log` (player, buyer, price, time), advance queue, reset per-player state. Empty queue
  → auction ends.
- **[AUCTION]** **On unsold:** append to `room["unsold_players"]`, advance queue.
- **[AUCTION]** Live broadcaster card, timer bar, current-bid/top-bidder metrics, per-team budget &
  squad-count dashboard, real-world squad reference viewer (taken/available).
- **[AUCTION]** Pre-auction "mission control" lobby for members (participant grid, budgets, squad
  manifest) while waiting for admin to start.
- ⚠️ **Bug noted:** the fragment references `market_frozen` (line 993) which is defined only in
  `show_main_app` — relevant only if "Open Bidding" reuses this view. Will not be carried over.

### 1.4 Post-auction "Open Bidding" market `streamlit_app.py` (in `show_main_app`, tab 1)
- **[SEASON]** After the big auction, async/asynchronous bidding on **unsold + released** players via
  `active_bids` (sealed-bid style, not the live timer). Includes IR (Injury Reserve) management.

### 1.5 Trading market `streamlit_app.py` (tab 2)
- **[SEASON]** Player-for-player / player+cash trade **proposals**, incoming/outgoing queues, accept/reject.
- **[SEASON]** **Admin trade approvals**, admin **force-trade** (third party), **loan deals** + reverse-loan.
- **[SEASON]** Global transaction log.

### 1.6 Squads & gameweek management `streamlit_app.py` (tab 3 + control center)
- **[SEASON]** Squad dashboard; rename team; release players (with paid-release flags).
- **[SEASON]** **Gameweek Control Center:** lock market, process loan returns, set deadlines, advance GW,
  revert last GW advance, clean up GW snapshots.
- **[SEASON]** Locked-squads snapshot viewer (public).

### 1.7 Scoring & automation `streamlit_app.py` + `player_score_calculator.py` + `football_score_calculator.py` + scrapers
- **[SEASON]** Schedule-driven and manual-URL score processing (Cricbuzz for cricket; FBref/WhoScored for
  football). Serverless automation hook + status dashboard.
- **[SEASON]** **Best-11 selection** (`get_best_11`, lines 248-433): brute-force optimal 11 under
  role-count constraints. Cricket ranges depend on gameweek (`≤10` uses old ranges); football uses
  GK/DEF/MID/FWD ranges. Hattrick bonus, dual-position players, IR exclusion, greedy fallback.
- **[SEASON]** Processed-gameweeks view; per-GW and cumulative standings; detailed Best-11; Top-3.

### 1.8 Knockout `streamlit_app.py:3574-3870`
- **[SEASON]** Tournament knockout elimination using Best-11 scoring; preview, history, released-player
  handling, reverse-elimination.

### 1.9 Admin tools (data) `streamlit_app.py:2716-3247`
- **[SEASON/INFRA]** **Bulk squad CSV import with staging** — supports a *wide* format (participant
  columns, player/price pairs, budget on row 27) **and** a clean *long* format
  (`Participant,Player,Role,Team,Price`, see `data/gameweek1_auction_squads.csv`). Fuzzy player-name
  matching (`difflib`), auto-creates "shadow" participants, editable staging grid before commit.
  *This is the closest existing thing to the spec's "FIFA WC CSV upload" — see Phase 2.*
- **[INFRA]** Force add/release player, reset paid-release flags, participant PINs, user management
  (delete account / password lookup), backup restore, **danger zone** (reset room data / delete room).

### 1.10 Persistence & theming `backend/storage.py`, `ui_theme.py`, `.streamlit/config.toml`
- **[INFRA]** **Firebase Realtime DB** (REST) as source of truth, with a local `auction_data.json` cache
  and a 15s session-cache TTL; background-thread async writes. Schema: `{users, rooms, setup}`.
- **[INFRA]** Custom premium dark theme (`ui_theme.py`, 1,115 lines): hero header, broadcaster header,
  auction player card, timer bar, status badges, metric rows. Palette `#007BFF / #00CCFF` on navy
  `#00172B`. This is the visual identity to honor in the new dark theme.

### 1.11 Event configs / data files (must be preserved — spec §6)
- `players_database.json` — 306 T20 WC players (`name, role, country`).
- `ipl_2026_squads.json` — IPL 2026 teams → squads (`name, role, ipl_team`).
- `fifa_wc_2026_players.json` — **empty `[]`** (this is exactly why the FIFA CSV-upload path exists).
- Schedules: `t20_wc_schedule.json`, `ipl_2026_schedule.json`, `fifa_wc_2026_schedule.json`.

---

## 2. Auction rules → `auction_engine/` mapping

The engine is **pure Python, no Reflex, no Streamlit, no I/O**. It takes explicit inputs and returns
new state + events. Below: each legacy rule, where it lives today, how it's tangled, and its engine home.

| Rule | Legacy location | Tangling today | New home |
|---|---|---|---|
| Start auction for a team (build queue, role-sort) | `663-810` | reads global `players_db`, mutates `room` dict, `st.rerun()` | `engine.start_team_auction(state, team, players)` |
| Place bid + validate increment | `1016-1071` | `st.number_input` min/max **is** the validation; button writes dict + rerun | `engine.place_bid(state, participant_id, amount)` → raises `BidError` |
| Dynamic increment & min-bid | `1019-1030` | computed inline for the widget | `engine.min_next_bid(current_bid)` / `engine.increment_for(bid)` |
| Budget check | `1028 max_bid_allowed` | enforced only via widget `max_value` | `place_bid` checks `participant.budget_remaining` |
| Squad-composition / cap (≤30) | UI caption `/30` only | not enforced at sale time | `engine` config `max_squad`, enforced in `place_bid`/`sell` |
| Opt out / revive | `1082-1086, 1111-1126` | mutates list + rerun | `engine.opt_out` / `engine.revive` |
| Timer + remaining | `915-921` | `get_ist_time()` vs `timer_start`, recomputed each rerun | engine stores `timer_ends_at`; remaining computed by caller clock |
| Auto-sell / auto-pass conditions | `966-973` | inline booleans each rerun | `engine.resolve_if_expired(state, now)` returns SOLD/UNSOLD/none |
| Execute sale (squad+budget+log+advance) | `1140-1186` | mutates `room`, `time.sleep(3)`, balloons, rerun | `engine.sell_current(state)` → returns `RosterEntry`+`BidLog`+next state |
| Execute unsold (advance) | `1188-1214` | same | `engine.mark_unsold(state)` |
| Force sell / unsold / pause | `1094-1109` | admin buttons set flags | `engine.force_sell/force_unsold/pause/resume` |
| **Undo last action** (spec §3, **new**) | *not in legacy* | — | `engine.undo()` over an append-only action log |

**Extraction principle:** the engine is a state machine over an immutable-ish `AuctionState` +
participants/rosters. Reflex state classes call engine methods, then persist + let the per-client poll
loop broadcast. No `st.session_state`, no reruns, no `time.sleep`, no global `players_db` inside the engine.

**Decisions to confirm (engine constants):** keep legacy values — timer **60s**, increments
`+1/+5/+10` at `<50/50-99/≥100`, `min_bid=max(5, …)`, default budget **100**, squad cap **30**. Squad
*composition* limits during the auction: legacy does **not** enforce role mins/maxes at buy time (those
ranges are a *Best-11 scoring* rule, §1.7). The spec wants squad-composition limits enforced server-side
— so I'll make composition limits **configurable per event** and **off by default for the ported cricket
events** (to preserve legacy behavior), **on** where an event defines them. Flagged in §6.3.

---

## 3. Verified Reflex / SQLModel API (checked against reflex.dev/docs, June 2026)

**Reflex latest stable: 0.9.3 (2026-05-23).** Pin `reflex==0.9.*`.

- **State:** `class S(rx.State):` with base vars as typed class attrs; event handlers are methods
  (optionally `@rx.event`); computed values use **`@rx.var`**; private helpers prefixed `_`.
- **Async / background:** `@rx.event(background=True) async def loop(self): while ...: async with self:
  <mutate>; await asyncio.sleep(...)`. **Must** mutate inside `async with self:` (else
  `ImmutableStateError`). Mutations auto-push deltas over the existing websocket.
- **Real-time broadcast (the #1 requirement):** Reflex state is **per-session**, *not* shared across
  clients. Pattern (Blaze-cost-aware): **one server-side background task per room polls Firebase**
  (~0.5s) into a **shared in-memory snapshot**; each connected client runs a lightweight `on_load`
  background loop that reads that **shared snapshot** (not Firebase directly) and updates its own session
  vars → Reflex pushes the delta to that client. This gives sub-second fan-out **with a single Firebase
  reader per room** instead of N (important on a pay-per-read plan). Writes go to the snapshot
  immediately + Firebase (async). Strictly better than Streamlit's 5s `run_every`. **Top technical risk,
  §6.4** — validate latency empirically in Phase 3.
- **Database: Firebase Realtime DB (§6.6), not SQLModel.** A Streamlit-free `firebase_store.py` does
  REST GET/PUT/PATCH against `FIREBASE_DATABASE_URL` (+ `FIREBASE_SECRET`) read from env. A repository
  layer maps the engines' dicts ↔ the Firebase `{users, rooms}` document. No `rx.Model`/migrations.
- **Upload (Phase 2 CSV):** `rx.upload(id=…, accept={"text/csv":[".csv"]}, on_drop=Handler.upload)`;
  handler `async def upload(self, files: list[rx.UploadFile])`, read via `await file.read()`; trigger
  with `rx.upload_files(upload_id=…)`; clear with `rx.clear_selected_files(id)`.
- **Styling:** Reflex theming + custom CSS; port the `ui_theme.py` palette/identity. Subtle motion via CSS
  transitions / `rx.motion` where available.

---

## 4. Target architecture (full-platform scope)

All business logic is **pure, framework-free, unit-tested**. Reflex only wraps it. The existing scoring
and scraper modules are *already* framework-free Python — they get **ported largely as-is** into
`scoring/`, decoupled from Streamlit (the only Streamlit coupling is `backend/storage.py`, which is
replaced by the DB layer).

```
auction_engine/          # PURE python. Auction state machine. Fully unit-tested.
  models.py  rules.py  engine.py  errors.py     # start/bid/opt-out/sell/unsold/force_*/undo

season_engine/           # PURE python. Everything after the draft. Unit-tested.
  best11.py              # ported get_best_11 (cricket gw-dependent ranges + football ranges, IR, dual-pos)
  scoring.py             # gameweek processing, hattrick bonus, cumulative standings
  trading.py             # proposals, accept/reject, admin force-trade, loans + reverse-loan
  knockout.py            # elimination via Best-11, reverse-elimination
  gameweek.py            # lock market, deadlines, advance/revert GW, snapshots, released/paid-release

scoring/                 # ported as-is from legacy (framework-free already)
  player_score_calculator.py  football_score_calculator.py
  cricbuzz_scraper.py  fbref_adapter.py  whoscored_adapter.py

app/                     # Reflex app
  state/                 # rx.State classes wrapping the engines + the poll/broadcast loop
  pages/                 # admin, lobby, live room, market, trading, squads, standings, knockout, scoring
  components/            # player card, timer bar, bid panel, budget grid, standings table (ported identity)
  firebase_store.py      # Streamlit-free Firebase Realtime DB client (REST, env config) — §6.6
  repository.py          # maps engine dicts/dataclasses ↔ the Firebase {users, rooms} document
  room_sync.py           # per-room background poller → shared in-memory snapshot (real-time, §6.4)
  config_layer.py        # load events/players/schedules from JSON or uploaded CSV; per-event rules
  automation.py          # schedule-driven + manual-URL score processing hook + status panel
  seed.py                # seed IPL 2026 + T20 WC + schedules from legacy JSON

data/  (reuse legacy JSON)   tests/  (engine + scoring unit tests)
Dockerfile  docker-compose.yml  .env.example  README.md  PLAN.md
```

### Data model — Firebase document shape (expands the legacy `{users, rooms}` doc)
Stored as a JSON tree in Firebase Realtime DB (not SQL tables). Dataclasses below describe the *logical*
entities the repository serializes into `users/{username}` and `rooms/{room_code}` nodes.
- `User` (site account, §6.2): username (key), password_hash, created_at, rooms_created[], rooms_joined[].
  Owns rooms it creates and teams it claims.
- `Event` (room): id, name, sport, tournament_type, total_budget, **rules (JSON: increments, timer,
  squad cap, composition ranges, Best-11 ranges, scoring source)**, status (`setup|auction|live|done`),
  game_phase, current_gameweek, **admin_user_id**, **admin_participates** (bool), room_code.
- `Player`: id, event_id, name, team, role/position, base_price, metadata (JSON), profile_url.
- `Participant` (a team in a room): id, event_id, display_name/team_name, **join_pin** (claimed via room
  code + PIN, §6.2), **claimed_by_user_id** (nullable until claimed), budget_remaining, is_admin,
  is_eliminated.
- `RosterEntry`: id, participant_id, player_id, price_paid, **is_ir**, acquired_via (`auction|market|trade|loan|admin`).
- `AuctionState`: event_id, current_team, player_queue (JSON), current_player_id, current_bid,
  current_bidder_id, timer_ends_at, opted_out (JSON), status.
- `BidLog` (append-only): id, event_id, player_id, participant_id, amount, kind, timestamp.
- `ActionLog` (append-only): powers **undo** across auction *and* season actions.
- **Season tables:** `MarketBid` (open-bidding/sealed bids), `TradeProposal` (+ items, status), `Loan`
  (+ return gameweek, reverse), `Match` (gameweek, url, status, source), `PlayerScore`
  (player, match, points + stat breakdown), `GameweekSnapshot` (locked squads per GW), `Transaction`
  (global log).

Per-event `rules` JSON keeps cricket-vs-football and gameweek-dependent Best-11 ranges out of code.

---

## 5. Build phases (commit + green tests after each)

Phases 0–6 are the spec's auction core; **7–10 are the season-management additions** required by the
full-parity decision. Each phase ends with green tests + a commit so the build is resumable.

- **Phase 0 — this document. STOP for approval.** ← we are here.
- **Phase 1 — `auction_engine/`** + comprehensive unit tests (all rules in §2, incl. undo).
- **Phase 2 — Persistence & admin setup:** Streamlit-free `firebase_store.py` + `repository.py` over the
  `{users, rooms}` document (§6.6), with a schema-upgrade pass for new fields; sign-up/login; create-room
  flow (tournament → admin-by-default → participate-vs-admin-only); CSV squad upload (**FIFA path** — long
  format `Player,Role,Team,BasePrice`, plus the legacy roster format `Participant,Player,Role,Team,Price`)
  with clear validation errors; admin assigns team PINs. Reuse existing IPL/T20 player JSON + schedules.
- **Phase 3 — Real-time auction room:** live bidding, countdown, high bid/bidder, sold/unsold,
  per-participant budget+squad tracking, bid log, undo — all broadcast via the poll loop.
- **Phase 4 — Participant flow:** join by room code + display name, lobby (who's in), live bidder view.
- **Phase 5 — Polish:** responsive, dark theme (ported identity), new-bid/sold animations, optional sold
  sound, empty/loading/error/disconnect + graceful reconnect.
- **Phase 6 — Self-host:** Dockerfile + compose, `.env.example`, seed/demo data, README (run, VPS deploy,
  add-an-event).
- **Phase 7 — Scoring engine:** port `season_engine/best11.py` + `scoring.py` and the
  `scoring/` calculators/scrapers; unit tests for Best-11 (cricket gw-ranges, football ranges, IR,
  dual-position, hattrick, greedy fallback). Manual-URL processing first.
- **Phase 8 — Gameweek lifecycle & standings:** lock market, deadlines, advance/revert GW, snapshots;
  per-GW + cumulative standings, detailed Best-11, Top-3; schedule-driven processing + automation status
  panel.
- **Phase 9 — Market & trading:** post-auction open/sealed bidding on unsold + released players (IR),
  release + paid-release flags; trade proposals (accept/reject), admin approvals/force-trade, loans +
  reverse-loan, global transaction log.
- **Phase 10 — Knockout + admin suite:** knockout elimination via Best-11, preview, history,
  reverse-elimination; remaining admin tools (force add/release, participant PINs, backup/restore, reset/
  delete room). Final end-to-end pass against the §1 inventory for parity.

---

## 6. Ambiguities / decisions needed (read before approving)

**6.1 — Scope. ✅ RESOLVED: full feature parity (auction + season management).** Data model and phases
above reflect this.

**6.2 — Auth. ✅ RESOLVED (user, 2026-06-02): account sign-up + per-room admin + team PINs.**
This **deviates from the spec's env `ADMIN_KEY`** at the user's explicit request — followed deliberately.
Flow:
  1. **Sign up / log in** on the site (username + password, hashed). → `User` table.
  2. Logged-in user chooses **Create room** or **Join room**.
  3. **Create:** pick tournament (T20 WC / IPL 2026 / FIFA WC 2026); creator becomes **that room's admin**
     by default; asked **"will you participate as a team manager, or admin-only?"** Admin sets up the
     room's teams/participants and assigns each a **team PIN** (also auto-created on CSV import).
  4. **Join:** enter **room code + the PIN for that team** to claim/control that team.
  No global env admin key (per-room admin = room creator). `ADMIN_KEY` may remain an optional
  platform-ops env var but is not the auth mechanism.

**6.3 — Squad-composition enforcement during the auction.** Legacy enforces role limits only at *Best-11
scoring*, never at buy time; the spec wants composition limits enforced server-side. Plan: make them a
**per-event config**, default **off** for ported cricket events (preserve legacy behavior), enabled where
an event specifies them. OK?

**6.4 — Real-time mechanism (top technical risk).** Reflex doesn't share state across clients for free.
I'll use the verified **per-client background poll loop** over a shared DB state (sub-second, beats
Streamlit's 5s). The spec's "~200ms" is achievable but may need socket-level push if the poll feels
laggy; I'll validate empirically in Phase 3. Acceptable?

**6.5 — Auction granularity.** Legacy auctions **by team** (queue = a real team's players). Keep
team-by-team? Or also allow a flat "all undrafted players" queue / admin-curated order? (Recommend: keep
team-by-team to preserve behavior; add manual single-player nomination as a small improvement.)

**6.6 — Persistence. ✅ RESOLVED (user, 2026-06-02): Firebase is THE database.** The user is on a
Firebase Blaze plan and wants **Firebase Realtime Database as the sole datastore** — *not* SQLite/
SQLModel. This is a **deliberate deviation from the spec**, followed at the owner's explicit request.
Plan:
  - Port `backend/storage.py` into a **Streamlit-free** `firebase_store.py`: config from **env vars**
    (`FIREBASE_DATABASE_URL`, `FIREBASE_SECRET`) instead of `st.secrets`; REST GET/PUT/PATCH.
  - Keep all data access behind a small **repository interface** so the backend is still swappable later
    (the spec's "swap is a config change" intent is preserved at the interface seam, even though the
    chosen backend is Firebase, not SQL).
  - **Existing Firebase data is reused** (same `{users, rooms}` document). A light schema-upgrade pass
    fills in any new fields (team PINs, action log) without destroying current rooms.
  - The engines never touch Firebase — they operate on plain dicts/dataclasses; the repository serializes
    to/from the Firebase document.

**6.7 — Repo layout.** Build the new app in a new top-level dir (e.g. `app/` + `auction_engine/`),
leaving the legacy files in place untouched. OK? (Spec implies a `legacy/` folder that doesn't exist; I
won't move existing files unless you want me to relocate them under `legacy/`.)

---

*End of Phase 0. Awaiting approval + answers to §6 before starting Phase 1.*
