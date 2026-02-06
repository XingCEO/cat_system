# CLAUDE.md - System Memory v3.0

**Repo:** https://github.com/XingCEO/cat_system.git
**Branch:** `main` | **Last Sync:** 2026-02-06
**Deployment:** Zeabur (Production)

---

## Token Efficiency Rules

**CRITICAL: READ THIS FIRST**

This document is the authoritative source for the project's current architecture. Future AI sessions MUST:

1. **STOP re-scanning** - Do not use exploratory `Grep`/`Glob` for understood components
2. **Trust this document** - Architecture, patterns, and file locations are current
3. **Read only when editing** - Only read specific files when making targeted changes
4. **Use correct services** - Use `delta_sync` for stock data (not raw `data_fetcher`)

Violations waste tokens and context window. This file exists to prevent redundant exploration.

---

## Deployment Architecture

### Environment Configuration

| Environment | Platform | Database | Config |
|-------------|----------|----------|--------|
| **Local** | localhost | SQLite | Default, no setup needed |
| **Production** | Zeabur | PostgreSQL | Via `DATABASE_URL` env var |

### Required Environment Variables (Production)

```bash
DATABASE_URL=postgresql://user:password@host:5432/database
FINMIND_API_TOKEN=your_token_here  # Optional, for historical data
```

### Database Driver Auto-Conversion

The system automatically converts `postgresql://` to `postgresql+asyncpg://` for async SQLAlchemy compatibility. No manual driver specification needed.

---

## Critical Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `asyncpg` | 0.30.0 | PostgreSQL async driver (production) |
| `aiosqlite` | 0.20.0 | SQLite async driver (local) |
| `sqlalchemy` | 2.0.36 | ORM with async support |
| `pydantic-settings` | 2.7.0 | Environment variable management |

All dependencies in `backend/requirements.txt`.

---

## Performance Architecture

### 3-Tier Caching (Delta Sync)

```
Request → Memory Cache (0.03ms) → DB Cache (72ms) → API Delta (257ms)
                ↓                      ↓                    ↓
           1-hour TTL            Persistent           Only missing dates
```

**Result:** <1ms stock switching, <500ms for 2-year history (cached)

### Frontend SWR Pattern

```typescript
useKLineData(symbol, 'day', 2)  // Instant display, background refresh
usePrefetchKLines().prefetch(['2330', '2317'])  // Preload stocks
```

**Config:** 5min staleTime, 60min gcTime, offlineFirst networkMode

### Indicator Persistence

All indicators pre-computed and stored in `KLineCache` table:
- MA5/10/20/60/120, RSI(14), MACD(12,26,9), KD(9,3,3), Bollinger(20,2)
- Incremental calculation for new data only

---

## Commands

### Local Development

```bash
# Backend (terminal 1)
cd backend && uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend && npm run dev
```

### Testing & Build

```bash
cd backend && pytest -v
cd frontend && npm run build
cd frontend && npm run lint
```

### Database Migration

```bash
cd backend && python3 -c "
import asyncio
from database import engine, Base
from models.kline_cache import KLineCache
from models.turnover import TurnoverRanking, TurnoverTrack

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migration complete')

asyncio.run(migrate())
"
```

---

## Critical Files

| Purpose | File |
|---------|------|
| Config | `backend/config.py` |
| Database | `backend/database.py` |
| Delta Sync | `backend/services/delta_sync_service.py` |
| K-Line Cache | `backend/models/kline_cache.py` |
| Technical Analysis | `backend/services/technical_analysis.py` |
| Turnover Tracker | `backend/services/turnover_tracker.py` |
| Frontend Hooks | `frontend/src/hooks/useStockData.ts` |
| Query Client | `frontend/src/lib/queryClient.ts` |

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/stocks/{symbol}/kline` | K-line + all indicators |
| `GET /api/turnover/top20` | Top 20 turnover stocks |
| `GET /api/turnover/ma-strategy/{type}` | MA strategy: `extreme`, `breakout`, `above_all` |
| `POST /api/turnover/track` | Create limit-up tracking |
| `GET /api/turnover/track/stats` | Tracking statistics |
| `GET /api/health` | Health check |

Full docs at `/docs` (Swagger UI).

---

## Key Implementation Details

1. **RSI:** Standard method - all days count in average (`technical_analysis.py:86-102`)
2. **Null Safety:** Float shares checked before division (`analyzers/base.py:220-225`)
3. **Taiwan Holidays:** 2024-2026 defined in `utils/date_utils.py`
4. **Limit-Up:** 10% rule with tick size adjustments
5. **PostgreSQL:** Auto-uses `NullPool` for async compatibility

---

## Data Sources

| Priority | Source | Use |
|----------|--------|-----|
| 1 | FinMind API | Historical OHLCV |
| 2 | TWSE OpenAPI | Real-time quotes |
| 3 | Yahoo Finance | Fallback |

---

## Performance Benchmarks

| Operation | Latency |
|-----------|---------|
| Memory cache hit | **0.03ms** |
| Stock switch (cached) | **0.04ms** |
| DB cache hit | 72ms |
| Cold API fetch | 257ms |

**Target:** <500ms for 2-year cached history ✅
