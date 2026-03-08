# 喵喵選股 (cat_system) — Copilot Instructions

## Project Overview
Taiwan Stock (台股) custom screening system. Dual API architecture: **Legacy API** (`/api/...` in `backend/routers/`) and **v1 API** (`/api/v1/...` in `backend/app/api/v1/`). FastAPI serves both the API and the React SPA from a single port (8000).

## Commands

```bash
# Backend dev server
cd backend && python -m uvicorn main:app --reload --port 8000

# Frontend dev server
cd frontend && npm run dev

# Run all tests
cd backend && python -m pytest tests/ -v

# Run a single test file
cd backend && python -m pytest tests/test_screener.py -v

# Run a specific test
cd backend && python -m pytest tests/test_operators.py::TestCrossUp::test_basic_cross_up -v

# Frontend type check
cd frontend && npx tsc --noEmit

# Build frontend
cd frontend && npm run build

# Docker build + run
docker build -t cat-system . && docker run -p 8000:8000 cat-system
```

## Architecture

### Data Flow
```
External APIs (FinMind / Yahoo Finance / TWSE)
    ↓
services/data_fetcher.py  (Legacy fetcher, cached)
    ↓
app/engine/data_sync.py   (sync_tickers / sync_daily_prices)
    ↓
v1 DB tables: Ticker, DailyPrice, DailyChip
    ↓
app/engine/screener.py    (screening engine, returns DataFrame)
    ↓
app/api/v1/screen.py      (POST /api/v1/screen)
```

### ORM Model Sets
Two separate ORM model sets share the **same** `Base` from `database.py`:
- **Legacy** (`backend/models/`): `Stock`, `DailyData` — used by `routers/`
- **v1** (`backend/app/models/`): `Ticker`, `DailyPrice`, `DailyChip`, `UserStrategy` — used by `app/api/v1/`

Never mix models from these two sets. Both are registered on the same `Base.metadata` and created by a single `init_db()` call.

### Database
- **Local dev**: SQLite (`backend/twse_filter.db`, driver `aiosqlite`)
- **Production** (Zeabur/Render): PostgreSQL (`asyncpg`); `database.py` auto-detects `POSTGRES_URI`, `POSTGRES_HOST`, etc. and rewrites the URL to `postgresql+asyncpg://`

### Startup Sequence
On startup, two background tasks are scheduled via `asyncio.create_task`:
1. `_background_sync` — pre-warms Legacy cache, then syncs v1 `tickers` + `daily_prices` tables
2. `_periodic_refresh` — every 30 min during TSE trading hours (8:30–14:30) refreshes daily data

### Cache Types (in-memory TTLCache)
| Cache type | TTL | Use for |
|---|---|---|
| `realtime` | 10 s | Live quotes |
| `general` | 300 s | Misc short-lived data |
| `daily` | 4 h | Daily OHLCV data |
| `indicator` | 4 h | K-line + technical indicators |
| `historical` | 24 h | Historical price series |
| `industry` | 7 d | Industry/sector lists |

### Screening Engine (`app/engine/`)
- `screener.py` — loads latest data from DB → applies formulas → evaluates rules → AND/OR merge
- `operators.py` — vectorized Pandas operators (`>`, `<`, `CROSS_UP`, `CROSS_DOWN`, …)
- `formula_parser.py` — whitelist-token sandbox using `pandas.eval()`; only fields in `ALLOWED_FIELDS` are permitted
- `data_sync.py` — `_backfill_indicators()` fills missing MA/RSI history by falling back to Legacy `data_fetcher` when v1 DB has < N days

### Frontend
- State management: Zustand store at `frontend/src/stores/store.ts` (directory is `stores/`, not `store/`)
- API client: `frontend/src/services/api.ts` (Axios)
- Pages: `ScreenPage`, `ChartProPage`, `StrategiesPage`, `HighTurnoverPage`, `TurnoverFiltersPage`, etc.

## Key Conventions

### Backend
- **DataFrame construction** — always use dict-based form: `pd.DataFrame([dict(r._mapping) for r in rows])`. Never use positional unpacking from SQLAlchemy rows.
- **Operators must not mutate DataFrames** — `cross_up` / `cross_down` use `.shift()` on a copy; the original `df` passed in must remain unchanged.
- **Config version sync** — `config.py` `app_version` must equal the `version=` argument in `FastAPI(...)` in `main.py` (currently `"2.0.0"`).
- **FinMind fallback** — FinMind API frequently returns 400/402/404; always fallback to Yahoo Finance or TWSE OpenAPI.
- **TWSE date handling** — TWSE returns the most recent trading day, which may differ from the queried date. Use the date in the API response, not the query date.
- **Realtime cache** — use cache type `"realtime"` (10 s TTL) for live quote data, never `"general"` (300 s).
- **Excel export** — uses XML Spreadsheet format (`.xls`), not CSV or `openpyxl`.

### v1 Screen API
`POST /api/v1/screen` body (`ScreenRequest`):
```json
{
  "logic": "AND",
  "rules": [
    {
      "type": "indicator",
      "field": "close",
      "operator": ">",
      "target_type": "value",
      "target_value": 100
    }
  ],
  "custom_formulas": []
}
```
`type` must be `"indicator"` | `"fundamental"` | `"chip"`.  
`operator` must be `">"` | `"<"` | `"="` | `">="` | `"<="` | `"CROSS_UP"` | `"CROSS_DOWN"`.

### v1 Chart Route
`GET /api/v1/chart/{ticker_id}/kline` — **not** `/api/v1/chart/{ticker_id}`.

### Frontend
- `target_value` in `ScreenPage.tsx` must be reset when `type` changes (to avoid stale values).
- `ChartProPage.tsx` `useEffect` deps must include `selectedTicker`.
- In `StrategiesPage.tsx`, JSON textarea uses a separate `rawJson` state to avoid controlled/uncontrolled conflicts.
