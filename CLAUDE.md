# CLAUDE.md — 喵喵選股 (cat_system)

## Project Overview
台股客製化選股系統，支援多維度篩選、技術分析、K線圖表、策略管理。
Dual architecture: Legacy API (`/api/...`) + v1 API (`/api/v1/...`).

## Tech Stack
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy (async) + SQLite (aiosqlite)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Zustand + TanStack Query
- **Data Sources**: FinMind API, Yahoo Finance, TWSE Open Data, TWSE MIS (盤中即時)
- **UI**: shadcn/ui (Radix) + Recharts + Lightweight Charts

## Project Structure
```
backend/
  main.py                          # FastAPI entry, serves frontend SPA
  config.py                        # Pydantic settings (version, DB, cache)
  database.py                      # Async SQLAlchemy engine + session
  models/                          # Legacy ORM (Stock, DailyData)
  app/models/                      # v1 ORM (Ticker, DailyPrice, DailyChip)
  app/engine/                      # v1 screening engine (screener, operators, formula_parser, data_sync)
  app/api/v1/                      # v1 API routes (screen, chart, tickers, strategies, sync)
  routers/                         # Legacy API routes (stocks, turnover, analysis, backtest, export, watchlist)
  services/                        # Business logic (high_turnover_analyzer, data_fetcher, cache_manager)
  tests/                           # Unit tests (pytest)
frontend/
  src/pages/                       # React pages
  src/components/                  # UI components
  src/stores/store.ts              # Zustand store
  src/services/api.ts              # Axios API client
```

## Deployment
- **Zeabur**: `zeabur.toml` → 根目錄 `Dockerfile` (multi-stage: build frontend → copy to static → uvicorn)
- **Render**: `render.yaml` → 同上 Docker 部署
- **Docker Compose**: `docker-compose.yml` → 前後端分離 + PostgreSQL + Redis
- **Port**: 8000 (FastAPI serves both API + SPA)
- **DB**: Zeabur/Render 用 PostgreSQL (asyncpg)，本地開發用 SQLite (aiosqlite)

## Commands
```bash
# Backend
cd backend && python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Tests
cd backend && python -m pytest tests/ -v

# Build frontend
cd frontend && npm run build

# Type check
cd frontend && npx tsc --noEmit

# Docker (local)
docker build -t cat-system . && docker run -p 8000:8000 cat-system
```

## Key Conventions
- Two ORM model sets share the same SQLAlchemy `Base` — do not mix them
- Screening engine operators (cross_up/cross_down) must NOT mutate input DataFrames
- DataFrame construction uses dict-based `pd.DataFrame([dict(r._mapping) ...])`, never positional
- Config version in `config.py` must match `main.py` FastAPI version (currently 2.0.0)
- Store directory is `frontend/src/stores/` (not `store/`)
- Excel export uses XML Spreadsheet format (.xls), not CSV
- Realtime quotes use `realtime` cache type (10s TTL), not `general` (300s)
