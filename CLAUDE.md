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
  app/api/v1/chart.py              # K 線路由: GET /chart/{ticker_id}/kline
  routers/                         # Legacy API routes (stocks, turnover, analysis, backtest, export, watchlist)
  services/                        # Business logic (high_turnover_analyzer, data_fetcher, cache_manager)
  tests/                           # Unit tests (pytest, 31 tests)
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
- **DB file**: `backend/twse_filter.db` — Legacy + v1 共用同一個 SQLAlchemy Base

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
- v1 Screen schema: `logic` ("AND"/"OR"), rules 需要 `type`/`field`/`operator`/`target_type`/`target_value`
- v1 Chart 路由: `/api/v1/chart/{ticker_id}/kline` (不是 `/chart/{ticker_id}`)
- `_backfill_indicators` 在 v1 DB 歷史不足時會 fallback 到 Legacy data_fetcher (Yahoo/TWSE)

## API Quick Reference
### Legacy API (`/api/...`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | 健康檢查 |
| `/api/status` | GET | 系統狀態 (version, stock count) |
| `/api/stocks/filter` | GET | 股票篩選 (Legacy) |
| `/api/stocks/{symbol}` | GET | 個股詳情 (即時+歷史) |
| `/api/stocks/industries` | GET | 產業列表 |
| `/api/turnover/*` | GET/POST | 高週轉率分析 |
| `/api/backtest/*` | POST | 回測引擎 |
| `/api/export/*` | GET | Excel 匯出 |

### v1 API (`/api/v1/...`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tickers` | GET | 股票列表 (支援 limit/offset) |
| `/api/v1/screen` | POST | 多維度篩選 (body: ScreenRequest) |
| `/api/v1/chart/{ticker_id}/kline` | GET | K 線 (period: daily/weekly/monthly) |
| `/api/v1/strategies` | GET/POST/PUT/DELETE | 策略 CRUD |
| `/api/v1/sync` | POST | 同步資料 (5 分鐘 cooldown) |

## Known Behaviors
- FinMind API 經常 400/402/404 → 自動 fallback 到 Yahoo Finance / TWSE OpenAPI
- 首次啟動時 v1 僅 1 天資料，`_backfill_indicators` 會批次 (200/batch) 從 Yahoo 抓歷史
- TWSE 資料日期可能與查詢日期不同（回傳最近交易日），sync 使用 API 回傳的「實際日期」
- 伺服器啟動時自動 pre-warm (載入股票列表 + 每日資料 + v1 同步)

## Bug Fix History (2026-02)
共修復 14 個 bug：
1. `enhanced_kline_service.py` — 移除死碼 + cache 過期檢查
2. `data_sync.py` — 新增 `_backfill_indicators()` 補算 MA/RSI + fallback 機制
3. `date_utils.py` — 2025 年假日修正
4. `technical_analysis.py` — KD 欄位名修正 (STOCHk_9_3_3 → STOCHk_14_3_3)
5. `calculator.py` — avg_change_5d 符號修正 (sort ascending)
6. `backtest.py` — stats[0] → next(s for s if holding_days==1)
7. `stocks.py` — exclude_special 參數傳遞
8. `v1/router.py` — sync 日期格式驗證 + try/except
9. `high_turnover_analyzer.py` — Yahoo timestamp timezone fix
10. `StrategiesPage.tsx` — JSON textarea rawJson 狀態分離
11. `ScreenPage.tsx` — target_value 在切換 type 時重置
12. `ChartProPage.tsx` — useEffect deps 加入 selectedTicker
13. `data_sync.py` — _backfill_indicators fallback 到 Legacy API 取歷史資料
14. `data_sync.py` — batch limit 從 50 提升到 200
