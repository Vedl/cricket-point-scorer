# Fantasy Sports Platform 🏏⚽

A full-stack fantasy sports platform supporting **IPL**, **T20 World Cup**, **UEFA Champions League**, and **FIFA World Cup 2026** — with live scoring, auction rooms, and multi-frontend delivery.

## Features

- **Live Scoring Engine** — real-time point calculation for cricket and football via Cricbuzz and FBRef scraping
- **Fantasy Auction Rooms** — multi-user draft rooms with bidding, squad constraints, and gameweek locking
- **Best-11 Selection** — per-gameweek auto-selection with role-based constraints (min. WK, BAT, AR, BWL counts)
- **Multi-Sport Support** — cricket (IPL, T20 WC) and football (UCL, FIFA WC 2026) in one platform
- **Admin Tools** — release management, player transfers, room resets, and paid-flag controls
- **Streamlit Dashboard** — lightweight admin interface alongside the React web app

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI |
| Scoring / Scraping | BeautifulSoup4, Cricbuzz, FBRef, WhoScored |
| Database | Firebase Firestore |
| Web Frontend | React, TypeScript, Vite, Tailwind CSS |
| Mobile Frontend | Flutter / Dart |
| Admin UI | Streamlit |
| Hosting | Firebase Hosting |

## Project Structure

```
├── api_server.py            # FastAPI backend (main entry point)
├── player_score_calculator.py
├── football_score_calculator.py
├── cricbuzz_scraper.py
├── fbref_adapter.py
├── whoscored_adapter.py
├── streamlit_app.py         # Admin dashboard
├── ui_theme.py
├── frontend/                # React/TypeScript web app
├── flutter_frontend/        # Flutter mobile app
├── backend/                 # Supporting backend modules
├── tests/                   # Pytest test suite
├── scripts/                 # Utility and migration scripts
│   ├── debug/               # Standalone debug scripts
│   └── migrations/          # One-off data migration scripts
└── data/                    # Static reference data (CSVs, schedules)
```

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- Firebase project (for Firestore)

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api_server.py
```

### React Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Admin Dashboard (Streamlit)

```bash
streamlit run streamlit_app.py
```

### Convenience script (all services)

```bash
./start_local.sh
```

## Supported Sports & Competitions

| Sport | Competition | Scoring Source |
|---|---|---|
| Cricket | IPL 2026 | Cricbuzz |
| Cricket | T20 World Cup | Cricbuzz |
| Football | UEFA Champions League | FBRef / WhoScored |
| Football | FIFA World Cup 2026 | FBRef / WhoScored |

## License

MIT
