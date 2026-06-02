# Fantasy Auction Platform (Reflex)

A real-time, multi-event fantasy **auction** platform — the migration of the legacy
Streamlit app to [Reflex](https://reflex.dev). Auctioneers run live auctions; participants
bid against each other with a countdown timer; budgets and squad limits are enforced
server-side; everything updates instantly for every connected client.

> This is the new stack. The legacy Streamlit app (`streamlit_app.py` and friends) is still
> in the repo for reference but is no longer the source of truth. See `PLAN.md` for the full
> migration plan and feature inventory.

## Stack
- **Reflex** (pure-Python reactive web framework, built-in WebSocket state sync)
- **Firebase Realtime Database** as the datastore (the owner runs on a Firebase Blaze plan)
- Pure, framework-free **`auction_engine/`** holding all auction rules (fully unit-tested)

## Architecture
```
auction_engine/   pure Python auction state machine (no framework) + tests
platform_core/    Firebase store, auth, CSV import, per-event config, repository + tests
fantasy_auction/  Reflex app: state, theme, pages, real-time room hub
```
Real-time: the app is a single self-hosted backend, so a module-level **room hub** holds one
shared auction engine per room — every connected client sees mutations within a sub-second poll
tick, with no Firebase round-trip per tick. Firebase is written (in a background thread) after
each mutation for durability.

## Run locally (dev)
```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements-app.txt
cp .env.example .env            # fill in Firebase config (see below)
./.venv/bin/reflex run          # → http://localhost:3000
```

## Run with Docker (self-host)
```bash
cp .env.example .env            # fill in Firebase config
docker compose up --build       # → http://localhost:3000
```

### Environment (`.env`)
| Var | Purpose |
|---|---|
| `FIREBASE_DATABASE_URL` | Realtime DB base URL (no trailing slash) |
| `FIREBASE_SECRET_KEY` | Legacy DB secret (appended as `?auth=`); optional |
| `AUCTION_DATA_FILE` | Local cache/fallback file (default `auction_data.json`) |
| `API_URL` | Public backend URL for prod (e.g. `https://auction.example.com`); defaults to `http://localhost:8000` |

If `FIREBASE_DATABASE_URL` is unset, the app runs fully on a local JSON file — handy for
development without a Firebase project.

## Deploy to a small VPS
1. Install Docker + Docker Compose on the VPS.
2. Clone the repo, `cp .env.example .env`, fill in Firebase config, and set
   `API_URL=https://your-domain` (the public URL the browser will use for the backend).
3. `docker compose up -d --build`.
4. Put a reverse proxy (Caddy/Nginx) in front: route `/` and the websocket to the app, and
   terminate TLS. Point `API_URL` at the proxied backend origin.
5. Open the firewall for 80/443 only; keep 3000/8000 internal behind the proxy.

## How to add a new event
1. Sign up / log in, click **Create room**, pick the tournament, and choose whether you'll
   participate or run admin-only. You become the room admin.
2. On the **Setup** page, add each team with a **PIN**, then share the room code + each team's
   PIN with participants.
3. **Upload squads** (CSV):
   - *Pool format* (e.g. FIFA WC, whose pool ships empty): `Player,Role,Team,BasePrice`
   - *Roster format* (pre-assign squads): `Participant,Player,Role,Team,Price`
   IPL 2026 and T20 World Cup pools are bundled and load automatically.
4. Go to the **auction room** and click **Start** for a team to begin live bidding.

To wire a brand-new tournament's bundled pool, drop a players JSON in the repo root and extend
`platform_core/config_layer.py` (`load_player_pool` + `default_config`).

## Tests
```bash
./.venv/bin/python -m pytest auction_engine/tests/ platform_core/tests/ -q
```
