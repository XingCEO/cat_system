# CLAUDE.md - System Memory v2.0

## Token Efficiency Rules

**READ FIRST:** Do not re-scan the codebase for context. This file contains current architecture state.

- Trust this document for project structure and patterns
- Only read specific files when making targeted edits
- Avoid exploratory `Grep`/`Glob` for understood components
- Use `delta_sync` for all stock data operations (not raw `data_fetcher`)

---

## Architecture Summary

**Stack:** FastAPI + React 18 + TypeScript + SQLite (async)

### 3-Tier Caching (Delta Sync)

```
Request → Memory Cache (0.03ms) → DB Cache (72ms) → API Delta (257ms)
                ↓                      ↓                    ↓
           1-hour TTL            Persistent           Only missing dates
```

**Service:** `backend/services/delta_sync_service.py`
- `delta_sync.get_stock_history_fast(symbol, days=500)` - Primary method
- `delta_sync.prefetch_symbols([...])` - Background warmup
- `delta_sync.clear_memory_cache()` - Cache invalidation

### Indicator Persistence

All indicators stored in `KLineCache` table, calculated incrementally:
- MA5/10/20/60/120, RSI(14), MACD(12,26,9), KD(9,3,3), Bollinger(20,2)
- **No recalculation on cached data** - only new delta points

### Frontend SWR

**Files:** `frontend/src/hooks/useStockData.ts`, `frontend/src/lib/queryClient.ts`

```typescript
useKLineData(symbol, 'day', 2)  // Instant cache display, background refresh
usePrefetchKLines().prefetch(['2330', '2317'])  // Preload anticipated stocks
```

**Performance:** <1ms stock switching (memory), 5min staleTime, 60min gcTime

---

## Commands

```bash
# Backend
cd backend && uvicorn main:app --reload --port 8000
cd backend && pytest -v

# Frontend
cd frontend && npm run dev
cd frontend && npm run build

# DB Migration (run once after schema changes)
cd backend && python3 -c "import asyncio; from database import engine, Base; from models.kline_cache import KLineCache; asyncio.run(engine.begin().__aenter__().then(lambda c: c.run_sync(Base.metadata.create_all)))"
```

---

## Critical Files

| Purpose | File |
|---------|------|
| Delta Sync | `backend/services/delta_sync_service.py` |
| K-Line Cache Model | `backend/models/kline_cache.py` |
| Technical Analysis | `backend/services/technical_analysis.py` |
| Turnover Tracker | `backend/services/turnover_tracker.py` |
| Frontend Hooks | `frontend/src/hooks/useStockData.ts` |
| Query Client | `frontend/src/lib/queryClient.ts` |
| API Client | `frontend/src/services/api.ts` |

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/stocks/{symbol}/kline` | K-line + indicators (uses enhanced_kline_service) |
| `GET /api/turnover/top20` | Top 20 turnover stocks |
| `GET /api/turnover/ma-strategy/{strategy}` | MA strategy: `extreme`, `breakout`, `above_all` |
| `POST /api/turnover/track` | Create tracking task |
| `GET /api/turnover/track/stats` | Tracking statistics |
| `GET /api/health` | Health check |

---

## Key Patterns

1. **RSI Calculation:** Standard method - all days count in period average (fixed in `technical_analysis.py:86-102`)
2. **Null Safety:** Float shares checked for None before division (`analyzers/base.py:220-225`)
3. **Date Utils:** Taiwan holidays 2024-2026 defined in `utils/date_utils.py`
4. **Limit-Up Detection:** 10% rule with tick size adjustments

---

## Data Sources (Priority Order)

1. **FinMind API** - Historical OHLCV (primary)
2. **TWSE OpenAPI** - Real-time quotes
3. **Yahoo Finance** - Fallback for missing data

---

## Performance Benchmarks

| Operation | Time |
|-----------|------|
| Memory cache hit | 0.03ms |
| DB cache hit | 72ms |
| Cold API fetch | 257ms |
| Stock switch (cached) | 0.04ms |

**Target met:** <500ms for 2-year cached history ✓
