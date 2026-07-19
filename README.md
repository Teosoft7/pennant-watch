# KBO Championship Probability Dashboard

A daily-updated dashboard that predicts each KBO (Korea Baseball Organization)
team's probability of winning the regular-season pennant and reaching the
postseason.

## What the dashboard shows

- **Standings table** — all 10 teams ranked by actual win percentage, with
  win-loss-draw record, games behind, OPS, and ERA. Each row carries a donut
  ring showing the team's postseason probability and a column with its
  championship probability. A cut line marks the top-5 postseason boundary.
- **Season forecast panel** — horizontal bar charts of the top-5 teams by
  postseason probability and by championship probability (normalized so the
  league's championship probabilities sum to 1).
- **Trend chart** — toggles between two views:
  - *Win % trend*: actual daily win percentage of the current top-5 teams,
    backfilled from opening day via the official KBO daily standings page.
  - *Championship probability trend*: model output accumulated once per day.
- Light and dark themes follow the OS setting automatically.

## How the prediction works

A pair of logistic-regression models (pennant winner / postseason berth)
trained on 2015–2025 team seasons. Only **rate stats** are used — OPS, RISP
average, ERA, WHIP, fielding percentage, SB%, CS% — standardized as z-scores
within each season, so mid-season snapshots can be scored on the same scale as
full seasons. Validated with leave-one-season-out CV: 63.6% top-1 accuracy for
the pennant winner, 4.18 of 5 postseason teams on average, AUC 0.94 (see
`KBO_우승팀_예측모델.ipynb` for the design rationale).

## Architecture

```
data collection (fetcher) ──▶ prediction (predict) ──▶ snapshot store (storage)
        ▲                                                    │
        │ daily at 00:00 KST (APScheduler)                   ▼
        └──────────── scheduler ◀────── FastAPI (/api/*) ──▶ dashboard (static)
```

```
kbo-champ-dashboard/
├── app/
│   ├── main.py            # FastAPI app (API + dashboard + scheduler lifespan)
│   ├── config.py          # settings (overridable via environment variables)
│   ├── scheduler.py       # daily update job + APScheduler
│   ├── storage.py         # snapshot store (JSON files; MongoDB seam documented)
│   ├── model/
│   │   ├── train.py       # model training (historical seasons → model.pkl)
│   │   └── predict.py     # prediction pipeline
│   └── data/fetcher.py    # current-season data collection (csv | web)
├── static/index.html      # dashboard UI (Chart.js)
├── data/
│   ├── kbo_historical.csv     # training data (2015–2025)
│   ├── current_season.csv     # current-season snapshot (daily input / scrape cache)
│   ├── model.pkl              # trained model bundle
│   ├── snapshots/             # daily prediction results (one JSON per date)
│   └── standings_history.csv  # daily actual standings (win % trend chart)
└── scripts/
    ├── run_daily_update.py    # run one manual update
    ├── backfill_standings.py  # collect daily standings since opening day (incremental)
    ├── build_static_site.py   # build the static site for GitHub Pages
    └── seed_demo_data.py      # generate demo data (development only)
```

## Quick start

```bash
pip install -r requirements.txt

# 1. Train the model (once; retrain after each season)
python -m app.model.train

# 2. Fetch live data and produce today's prediction
DATA_SOURCE=web python -m scripts.run_daily_update

# 3. Run the server
uvicorn app.main:app --reload
# → http://localhost:8000
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/api/latest` | Latest daily prediction |
| GET | `/api/history?season=2026` | Daily prediction snapshots (trend chart) |
| GET | `/api/standings-history` | Daily actual standings since opening day (win % trend) |
| POST | `/api/refresh` | Manual update (`X-Refresh-Token` header required when REFRESH_TOKEN is set) |
| GET | `/health` | Health check |

## Data sources

**Scraping mode (`DATA_SOURCE=web`, recommended)**
`fetch_from_kbo_web()` merges five official KBO pages — daily standings,
hitting, pitching, defense, and baserunning — into one snapshot (verified
against the live page structure as of July 2026). On success the result is
cached to `current_season.csv`; on failure (e.g. a site layout change) the
fetcher falls back to the last successful cache automatically.

**Manual mode (`DATA_SOURCE=csv`, default)**
Maintain `data/current_season.csv` yourself with columns
`TEAM, G, W, L, D, OPS, RISP, ERA, WHIP, FPCT, SB%, CS%`.
The scheduler predicts and stores results daily at 00:00 KST either way.

## Deployment

### Option 1: GitHub Actions + Pages (recommended — free, serverless)

No always-on server. A workflow updates the data and republishes the static
site every night.

1. Push the repository to GitHub
2. Settings → Pages → Source: **GitHub Actions**
3. Done — `.github/workflows/daily-update.yml` runs daily at 00:00 KST:
   scrape → predict → commit `data/` (persistence via git history) → build and
   deploy the static site. Trigger manually from the Actions tab if needed.

Preview the static build locally:

```bash
python -m scripts.build_static_site
python -m http.server 8000 --directory site
```

### Option 2: Railway (always-on server + live API)

`Procfile` included. Connect the repository and set environment variables:

```
DATA_SOURCE=web
REFRESH_TOKEN=<any secret>
```

Note: Railway's default filesystem resets on redeploy — mount a Volume at
`data/` (or switch to MongoDB) to persist snapshots.

## MongoDB (Beanie) extension point

`app/storage.py` exposes only `save / load_latest / load_history`. To move to
MongoDB Atlas, replace this one file (a Document schema example is in the
module docstring).

## Notes & caveats

- **"Championship" means finishing first in the regular season** (the
  pennant), which can differ from the Korean Series result (e.g. 2015, 2018).
- **Early-season reliability**: team rate stats stabilize after roughly 58
  games (40% of the season). The dashboard shows a reliability warning before
  that point.
- **Demo data**: snapshots produced by `seed_demo_data.py` are synthetic
  (marked `"demo": true`). Empty `data/snapshots/` before going live.
- **Retraining**: after each season, append the new season to
  `kbo_historical.csv` and rerun `python -m app.model.train`.
