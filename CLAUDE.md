# CLAUDE.md - System Memory v4.4

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
5. **Never claim 100% completion** - Until you visually verify the data matches expectations

Violations waste tokens and context window. This file exists to prevent redundant exploration.

---

## Timezone Standardization (CRITICAL)

**All datetime operations use Taiwan Timezone (UTC+8)**

### Backend Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `get_taiwan_now()` | `utils/date_utils.py` | Current Taiwan datetime |
| `get_taiwan_today()` | `utils/date_utils.py` | Current Taiwan date |
| `get_market_status()` | `utils/date_utils.py` | Returns `(status, should_have_today)` |
| `get_latest_trading_day()` | `utils/date_utils.py` | Today if market opened, else previous |
| `is_market_open()` | `utils/date_utils.py` | True if 09:00-13:30 Taiwan time |
| `_get_taiwan_now_naive()` | `models/kline_cache.py`, `schemas/common.py` | Taiwan time without tzinfo (for DB) |

### Frontend Pattern

```typescript
// 正確：使用 Asia/Taipei 時區
const now = new Date();
const taiwanTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));

// 錯誤：直接使用 new Date()
const wrong = new Date().toISOString().split('T')[0];  // 會得到 UTC 日期
```

**Market Status Values:**
- `"open"` - Market trading (09:00-13:30), `should_have_today=True`
- `"closed"` - After hours (>13:30), `should_have_today=True`
- `"pre_market"` - Before open (<09:00), `should_have_today=False`
- `"holiday"` - Non-trading day, `should_have_today=False`

**NEVER use:**
- Backend: `datetime.now()`, `date.today()`, `datetime.utcnow()`
- Frontend: `new Date().toISOString()` for display dates

**Database Timestamps:** All models use `_get_taiwan_now_naive()` for `cached_at`, `updated_at` columns.

**Limit-Up Threshold:** Taiwan stocks use **9.9%** (not 9.5%)

---

## Turnover Realtime Fallback (NEW)

**Problem Solved:** Turnover/Top200 pages showing yesterday's data before ~14:30.

**Root Cause:** TWSE OpenAPI `STOCK_DAY_ALL` doesn't accept date parameter - returns latest available data (yesterday until ~14:30).

**Solution:** Two-part fix in `data_fetcher.py` and `base.py`.

### Data Fetcher Date Validation

```python
# data_fetcher.py - _fetch_twse_daily_openapi()

# Parse actual date from API response
if actual_data_date and actual_data_date != trade_date:
    # Cache under ACTUAL date (not requested date)
    cache_manager.set(f"daily_{actual_data_date}", df.to_dict("records"), "daily")
    # Return empty - caller should use realtime fallback
    return pd.DataFrame()
```

### Base Analyzer Realtime Fallback

```python
# base.py - _fetch_daily_data()

if df.empty:
    today_str = get_taiwan_today().strftime("%Y-%m-%d")
    market_status, _ = get_market_status()

    if date == today_str and market_status in ("open", "closed"):
        df = await self._fetch_realtime_as_daily(date)
```

### Data Flow

```
Turnover/Top200 Request (today)
            ↓
data_fetcher.get_daily_data()
            ↓
TWSE API returns yesterday? → Cache under yesterday's key, return empty
            ↓
base.py detects empty + market open/closed
            ↓
_fetch_realtime_as_daily() → Batch fetch realtime quotes
            ↓
Convert to daily format → Return today's data ✅
```

---

## K-Line Realtime Candle Injection

**Problem Solved:** Charts showing yesterday's data even after market opens.

**Solution:** `enhanced_kline_service.py` now injects today's candle from realtime quotes.

### Key Methods

```python
# enhanced_kline_service.py

async def _ensure_today_candle(symbol, df, latest_trading_day, market_status):
    """
    Called on EVERY data retrieval path.
    If cache is missing today's candle, fetches from API or realtime quotes.
    """

async def _get_realtime_candle(symbol, date_str):
    """
    Constructs proper OHLC candle from TWSE MIS API.

    Priority:
    1. Direct OHLC from API (open_price, high_price, low_price, price)
    2. Estimate from prev_close (direction-based H/L)
    3. Estimate from bid/ask spread
    4. Fallback: single price (toothpick)
    """
```

### Data Flow

```
Request → Cache Check → Missing Today? → Fetch Delta from API
                              ↓
                        API Empty?
                              ↓
                    Get Realtime Quote → Construct OHLC Candle
                              ↓
                        Merge & Save to DB
```

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
           Smart TTL             Persistent           Only missing dates
```

**Smart Cache TTL:**
- Market open: 1-minute TTL (refresh frequently)
- Market closed: 1-hour TTL (data stable)
- Missing today's data: Immediate invalidation

**Result:** <1ms stock switching, <500ms for 2-year history (cached)

### Frontend SWR Pattern

```typescript
useKLineData(symbol, 'day', 2)  // Instant display, background refresh
usePrefetchKLines().prefetch(['2330', '2317'])  // Preload stocks
```

**Config:** Dynamic staleTime (1min market open, 5min closed), 60min gcTime, refetchOnMount: 'always'

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
| **Timezone Utils** | `backend/utils/date_utils.py` |
| Delta Sync | `backend/services/delta_sync_service.py` |
| **Enhanced K-Line** | `backend/services/enhanced_kline_service.py` |
| K-Line Cache Model | `backend/models/kline_cache.py` |
| Technical Analysis | `backend/services/technical_analysis.py` |
| Realtime Quotes | `backend/services/realtime_quotes.py` |
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

1. **Timezone:** 100% Taiwan (UTC+8) via `get_taiwan_now()` / `get_taiwan_today()`
2. **RSI:** Standard method - all days count in average (`technical_analysis.py:86-102`)
3. **Null Safety:** Float shares checked before division (`analyzers/base.py:220-225`)
4. **Taiwan Holidays:** 2024-2026 defined in `utils/date_utils.py`
5. **Limit-Up:** 10% rule with tick size adjustments
6. **PostgreSQL:** Auto-uses `NullPool` for async compatibility
7. **Realtime Candle:** Proper OHLC extraction with fallback chain

---

## Data Sources

| Priority | Source | Use |
|----------|--------|-----|
| 1 | FinMind API | Historical OHLCV |
| 2 | TWSE MIS API | Real-time quotes (via `realtime_quotes.py`) |
| 3 | Yahoo Finance | Fallback |

---

## Performance Benchmarks

| Operation | Latency |
|-----------|---------|
| Memory cache hit | **0.03ms** |
| Stock switch (cached) | **0.04ms** |
| DB cache hit | 72ms |
| Cold API fetch | 257ms |
| Realtime candle injection | ~150ms |

**Target:** <500ms for 2-year cached history ✅

---

## Recent Fixes (2026-02-06)

### Critical Fix: Full System Timezone Standardization

**Backend Fixes:**

| Issue | Root Cause | Fix |
|-------|------------|-----|
| **Data not saving in production** | SQLite-only `insert` dialect used | Auto-detect DB type, use `pg_insert` for PostgreSQL |
| **datetime.utcnow() in models** | Cache staleness calculated wrong | Replaced with `_get_taiwan_now_naive()` |
| **API response UTC timestamp** | Inconsistent with data timezone | Changed to Taiwan time |
| **is_stale() wrong timezone** | Comparing UTC vs Taiwan time | Fixed to use Taiwan time |
| Timezone cache mismatch | Comparing aware vs naive datetime | Normalize to naive datetime before comparison |
| Realtime quote hanging | No timeout protection | Added 10s `asyncio.wait_for` timeout |
| OTC stocks not found | Oversimplified market classification | Improved logic with fallback mechanism |
| Stale cache served | `_get_from_cache_any` skipped expiry check | Added market-aware TTL check |

**Frontend Fixes:**

| Issue | Root Cause | Fix |
|-------|------------|-----|
| **Market status wrong timezone** | Used local `Date()` | Changed to `Asia/Taipei` timezone |
| **Limit-up threshold 9.5%** | Incorrect threshold | Fixed to 9.9% (Taiwan rule) |
| **Quick date buttons wrong** | Used `toISOString()` (UTC) | Use Taiwan timezone formatting |
| **Date picker max wrong** | Used UTC date | Use Taiwan date |
| Frontend shows old data | `refetchOnMount: false` | Changed to `'always'` |
| Fixed 5min stale time | Ignores market hours | Dynamic: 1min open, 5min closed |

### Previous Fixes

| Issue | Root Cause | Fix |
|-------|------------|-----|
| Charts show yesterday | No timezone awareness | Added Taiwan UTC+8 throughout |
| Stale cache blocking | 1-hour TTL too long | Smart TTL based on market status |
| Missing today's candle | No realtime injection | Added `_ensure_today_candle()` |
| Toothpick/Doji candles | All OHLC = price | Proper field extraction with fallbacks |
| Wrong API method | `get_batch_quotes` | Changed to `get_quotes()` |

---

## Verification Checklist

Before claiming completion, verify:

```bash
# 1. Check latest candle date matches today
curl https://your-url/api/stocks/2330/kline | jq '.kline_data[-1].date'
# Expected: "2026-02-06"

# 2. Check OHLC are distinct values (not toothpick)
curl https://your-url/api/stocks/2330/kline | jq '.kline_data[-1] | {o:.open, h:.high, l:.low, c:.close}'
# Expected: 4 different values for a real candle body

# 3. Check Top 20 turnover date
curl https://your-url/api/turnover/top20 | jq '.query_date'
# Expected: "2026-02-06"

# 4. Check API timestamp is Taiwan time
curl https://your-url/api/health | jq '.timestamp'
# Expected: ~14:xx or 15:xx (Taiwan time, not 06:xx UTC)
```
