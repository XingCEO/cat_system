# CLAUDE.md - System Memory v4.6

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
4. **Use correct services** - Use `delta_sync` or `enhanced_kline` (not raw `data_fetcher`)
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
// Correct: Use Asia/Taipei timezone (正確：使用 Asia/Taipei 時區)
const now = new Date();
const taiwanTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));

// Incorrect: Directly use new Date() (錯誤：直接使用 new Date())
const wrong = new Date().toISOString().split('T')[0];  // Will get UTC date (會得到 UTC 日期)
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

## Realtime Fallback for ALL Daily Data Endpoints

**Problem Solved:** All pages showing yesterday's data before ~14:30.
**Root Cause:** TWSE OpenAPI `STOCK_DAY_ALL` doesn't accept date parameter - returns latest available data (yesterday until ~14:30).
**Solution:** ALL endpoints using `get_daily_data()` now have realtime fallback.

### Files with Realtime Fallback

| File | Endpoint | Method |
|------|----------|--------|
| `data_fetcher.py` | (core) | Date validation - returns empty if stale |
| `analyzers/base.py` | `/api/turnover/top20` | `_fetch_realtime_as_daily()` |
| `stock_filter.py` | `/api/stocks/filter` | `_fetch_realtime_as_daily()` |
| `routers/stocks.py` | `/api/stocks/{symbol}` | `_fetch_realtime_as_daily_for_symbol()` |
| **`enhanced_kline_service.py`** | (core service) | `_ensure_today_candle()` |

### Data Flow

```
ANY Daily Data Request (today)
            ↓
data_fetcher.get_daily_data()
            ↓
TWSE API returns yesterday? → Cache under yesterday's key, return empty
            ↓
Endpoint detects empty + market open/closed
            ↓
_fetch_realtime_as_daily() → Batch fetch realtime quotes
            ↓
Convert to daily format → Return today's data ✅
```

---

## MA Strategy Optimization (New 2026-02-06)

**Problem Solved:** MA Strategy scanning was slow due to sequential `yfinance` calls and lack of caching.
**Solution:** Migrated to `EnhancedKLineService` with async concurrency.

### Key Improvements

1.  **Centralized Caching (`TechnicalAnalyzerMixin`)**:
    *   Replaced `yfinance.download` with `enhanced_kline_service.get_kline_data_extended`.
    *   Leverages the 3-Tier Cache (Memory -> DB -> API).
    *   Supports 5-year historical data retention.

2.  **Concurrency Control**:
    *   Implemented `asyncio.Semaphore(10)` to limit parallel requests.
    *   Batch processing (20 stocks per batch) to prevent event loop blocking.

3.  **Strict Mode**:
    *   For "Today" queries, strictly validates realtime price existence.
    *   Filters out stocks with invalid or missing Quotes.

---

## K-Line Realtime Candle Injection & Robustness

**Problem Solved:** 
1. Charts showing yesterday's data even after market opens.
2. Incomplete realtime data (missing OHLC) causing "toothpick" candles or errors.

**Solution:** `enhanced_kline_service.py` injects today's candle and robustly reconstructs OHLC.

### Candle Reconstruction Logic (`_get_realtime_candle`)

When TWSE MIS API returns incomplete data (common), we reconstruction candle:

| Scenario | Logic | Result |
|----------|-------|--------|
| **Full Data** | `open`, `high`, `low`, `price` exist | Standard Candle |
| **Missing OHL** | Have `prev_close` & `price` | Estimate from direction (Up: L=O, H=C; Down: H=O, L=C) |
| **Missing Prev** | Have `bid`/`ask` | Estimate range from bid/ask spread |
| **Last Resort** | Only `price` | Toothpick Candle (O=H=L=C) |

### Realtime Injection Flow (`_ensure_today_candle`)

```python
if cache_latest_date < today and market_is_open:
    # 1. Try API Delta (Historical)
    delta = fetch_historical(cache_date + 1, today)
    
    # 2. If API empty (during day), Inject Realtime
    if delta.empty:
        candle = _get_realtime_candle(symbol)
        delta = DataFrame([candle])
    
    # 3. Merge & Return
    df = concat(df, delta)
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

**Database Driver:** Auto-converts `postgresql://` to `postgresql+asyncpg://`.

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

### Benchmarks (MA Strategy)
*   **Before:** ~30-60s for 200 stocks (Sequential HTTP)
*   **After:** ~2-5s (Cached + Async Semaphore)

### Indicator Persistence
All indicators pre-computed and stored in `KLineCache` table:
- MA5/10/20/60/120, RSI(14), MACD(12,26,9), KD(9,3,3), Bollinger(20,2)

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
cd frontend && npm run build  # Now fixed (typescript error resolved)
cd frontend && npm run lint
```

---

## Critical Files

| Purpose | File |
|---------|------|
| **Enhanced K-Line** | `backend/services/enhanced_kline_service.py` |
| **Technical Analysis** | `backend/services/analyzers/technical.py` |
| Timezone Utils | `backend/utils/date_utils.py` |
| Delta Sync | `backend/services/delta_sync_service.py` |
| Realtime Quotes | `backend/services/realtime_quotes.py` |
| Frontend Hooks | `frontend/src/hooks/useStockData.ts` |
| Error Boundary | `frontend/src/components/ErrorBoundary.tsx` |

---

## Recent Fixes (2026-02-06)

### Optimization & Stability

| ID | Issue | Fix |
|----|-------|-----|
| **PERF-01** | **MA Strategy Slow** | Migrated to `EnhancedKLineService` + Async Semaphore (10) |
| **DATA-01** | **Realtime Candle Missing** | Added `_ensure_today_candle` with fallback construction (Prev/Bid/Ask) |
| **DATA-02** | **Realtime Quote Hanging** | Added 10s `asyncio.wait_for` timeout in `realtime_quotes` |
| **BUILD-01** | **TypeScript Error** | Removed unused `React` import in `ErrorBoundary.tsx` |
| **I18N-01** | **Language Revert** | Reverted accidental English translation, restored Traditional Chinese UI |

### Previous Critical Fixes (Timezone)

| Issue | Root Cause | Fix |
|-------|------------|-----|
| **Data not saving in production** | SQLite-only dialect | Auto-detect DB type, use `pg_insert` for Postgres |
| **datetime.utcnow()** | Cache staleness wrong | Replaced with `get_taiwan_now()` |
| **Market status wrong** | Used local `Date()` | Fixed frontend to use `Asia/Taipei` |
| **Limit-up threshold** | Incorrect 9.5% | Fixed to **9.9%** (Taiwan rule) |

---

## Verification Checklist

Before claiming completion, verify:

```bash
# 1. Check MA Strategy Speed & Data
curl "https://your-url/api/turnover/ma-strategy/extreme" | jq '.matched_count'

# 2. Check Latest Candle (Realtime Injection)
curl https://your-url/api/stocks/2330/kline | jq '.kline_data[-1].date'
# Expected: Today's date (if market open)

# 3. Check OHLC distinct values
curl https://your-url/api/stocks/2330/kline | jq '.kline_data[-1] | {o:.open, h:.high, l:.low, c:.close}'
# Expected: 4 different values (unless market flat)

# 4. Check API Timestamp
curl https://your-url/api/health | jq '.timestamp'
# Expected: Taiwan Time (UTC+8)
```
