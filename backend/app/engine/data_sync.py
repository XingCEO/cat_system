"""
Data Sync — 從 Legacy data_fetcher 同步資料到 v1 表 (Ticker, DailyPrice, DailyChip)
包含延伸指標計算：avg_volume_20, avg_turnover_20, lower_shadow,
lowest_lower_shadow_20, 週MA, market_ok
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from app.models.daily_chip import DailyChip
from app.models.market_index import MarketIndex
from services.data_fetcher import data_fetcher
from config import get_settings

logger = logging.getLogger(__name__)

# Serializes concurrent sync_daily_prices callers (_background_sync + _periodic_refresh)
# to prevent check-then-insert races that cause duplicate rows / unique violations.
_sync_daily_lock = asyncio.Lock()

# Serializes write-heavy maintenance jobs on SQLite. Startup gap backfills and
# on-demand freshness syncs can otherwise overlap and surface transient
# "database is locked" errors even with a busy timeout.
_maintenance_write_lock = asyncio.Lock()

# Auto catch-up guard: serialize + throttle on-demand freshness syncs triggered from
# read paths (screener / ensure-latest endpoint) so a burst of requests can't stampede
# the external data source. Reset whenever a catch-up actually runs.
_catchup_lock = asyncio.Lock()
_last_catchup_monotonic: float = 0.0
_CATCHUP_COOLDOWN_SECS: float = 300.0  # 5 min between automatic catch-up attempts

PULLBACK_WINDOW_DAYS = 60
BREAKOUT_LOOKBACK_DAYS = 20
PULLBACK_ONE_THIRD = 1.0 / 3.0
PULLBACK_TWO_THIRDS = 2.0 / 3.0
PULLBACK_FLAG_FIELDS = (
    "ma_bull_pullback_low_high_1_3",
    "ma_bull_pullback_low_high_2_3",
    "ma_bull_pullback_breakout_1_3",
    "ma_bull_pullback_breakout_2_3",
)


async def sync_tickers(db: AsyncSession) -> int:
    """同步股票基本資料到 tickers 表"""
    stock_list = await data_fetcher.get_stock_list()
    if stock_list.empty:
        return 0

    # Bulk query existing ticker_ids to avoid N+1
    all_ids = [str(row.get("stock_id", "")) for _, row in stock_list.iterrows() if row.get("stock_id")]
    existing_result = await db.execute(select(Ticker.ticker_id).where(Ticker.ticker_id.in_(all_ids)))
    existing_ids = set(existing_result.scalars().all())

    count = 0
    for _, row in stock_list.iterrows():
        ticker_id = str(row.get("stock_id", ""))
        if not ticker_id or ticker_id in existing_ids:
            continue
        db.add(Ticker(
            ticker_id=ticker_id,
            name=str(row.get("stock_name", ticker_id)),
            market_type="TSE",
            industry=row.get("industry_category"),
        ))
        count += 1

    if count > 0:
        await db.commit()
    logger.info(f"Synced {count} new tickers (total existing: {len(existing_ids)})")
    return count


async def sync_daily_prices(db: AsyncSession, trade_date: Optional[str] = None) -> int:
    """
    同步日K線資料到 daily_prices 表

    重要修復：使用 API 回傳的**實際日期**，而非傳入的查詢日期。
    TWSE API 通常回傳最近交易日的資料（可能是昨天）。
    使用批次查詢避免 N+1 問題。
    """
    if trade_date is None:
        from utils.date_utils import get_latest_trading_day
        trade_date = get_latest_trading_day()  # 台灣時區 + 自動退回最近交易日

    daily_df = await data_fetcher.get_daily_data(trade_date)
    if daily_df.empty:
        logger.warning(f"No daily data returned for {trade_date}")
        return 0

    # 使用 API 回傳的**實際日期**，而非傳入的查詢日期
    if "date" in daily_df.columns:
        actual_date_str = str(daily_df["date"].iloc[0])
        try:
            date_obj = datetime.strptime(actual_date_str, "%Y-%m-%d").date()
        except ValueError:
            date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()
        logger.info(f"Daily data actual date: {date_obj} (queried: {trade_date})")
    else:
        date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()

    async with _sync_daily_lock:
        # 批次查詢：取得該日已存在的所有 ticker_ids
        existing_result = await db.execute(
            select(DailyPrice.ticker_id).where(DailyPrice.date == date_obj)
        )
        existing_tickers = set(existing_result.scalars().all())

        # 取得所有已知 ticker_ids（只同步有基本資料的股票，避免 orphan records）
        known_result = await db.execute(select(Ticker.ticker_id))
        known_tickers = set(known_result.scalars().all())

        if existing_tickers:
            logger.info(f"Already have {len(existing_tickers)} prices for {date_obj}, checking for new...")

        skipped_unknown = 0
        count = 0
        for _, row in daily_df.iterrows():
            ticker_id = str(row.get("stock_id", row.get("Code", "")))
            if not ticker_id or ticker_id in existing_tickers:
                continue
            # 只同步已知 tickers（跳過 REITs、受益憑證等沒有基本資料的）
            if ticker_id not in known_tickers:
                skipped_unknown += 1
                continue

            close = _safe_float(row, "close", "ClosingPrice")
            if close is None:
                continue

            open_p = _safe_float(row, "open", "OpeningPrice")
            high = _safe_float(row, "max", "HighestPrice")
            low = _safe_float(row, "min", "LowestPrice")
            volume = _safe_int(row, "Trading_Volume", "TradeVolume")
            change = _safe_float(row, "spread", "Change")
            change_pct = None
            if change is not None and close is not None:
                prev_close = close - change
                if prev_close > 0:
                    change_pct = round(change / prev_close * 100, 2)

            # 計算成交值 = 收盤 × 成交量 (股)
            turnover = round(close * volume, 0) if close is not None and volume is not None else None

            # 計算下引價 = body_bottom - low (下影線長度，body_bottom >= low 故為非負)
            lower_shadow = None
            if low is not None and open_p is not None and close is not None:
                body_bottom = min(open_p, close)
                lower_shadow = round(max(0.0, body_bottom - low), 4)

            db.add(DailyPrice(
                date=date_obj,
                ticker_id=ticker_id,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=volume,
                change_percent=change_pct,
                turnover=turnover,
                lower_shadow=lower_shadow,
            ))
            count += 1

        if count > 0:
            await db.commit()
        if skipped_unknown > 0:
            logger.info(f"Skipped {skipped_unknown} unknown ticker_ids (REITs, etc.)")
        logger.info(f"Synced {count} daily prices for {date_obj}")

    # Keep latest-date maintenance together so startup gap backfills do not
    # interleave between indicator, chip, and fundamental writes.
    async with _maintenance_write_lock:
        await _backfill_indicators_unlocked(db, date_obj)
        try:
            await sync_daily_chips(db, date_obj)
        except Exception as e:
            logger.warning(f"sync_daily_chips failed: {e}")
        try:
            await sync_fundamentals(db, date_obj)
        except Exception as e:
            logger.warning(f"sync_fundamentals failed: {e}")

    return count


async def sync_daily_chips(db: AsyncSession, target_date) -> int:
    """
    同步三大法人買賣超 (T86) + 融資餘額 (MI_MARGN) 到 daily_chips。
    foreign_buy / trust_buy 單位為股 (可為負)，margin_balance 單位為張。
    """
    import pandas as pd

    inst_df = await data_fetcher.get_institutional_net()
    margin_df = await data_fetcher.get_margin_balance()
    if inst_df.empty and margin_df.empty:
        logger.warning("No chip data available (T86 + MI_MARGN both empty)")
        return 0

    if inst_df.empty:
        merged = margin_df.copy()
        merged["foreign_buy"] = None
        merged["trust_buy"] = None
    elif margin_df.empty:
        merged = inst_df.copy()
        merged["margin_balance"] = None
    else:
        merged = inst_df.merge(margin_df, on="stock_id", how="outer")

    known_result = await db.execute(select(Ticker.ticker_id))
    known = set(known_result.scalars().all())

    existing_result = await db.execute(
        select(DailyChip).where(DailyChip.date == target_date)
    )
    existing = {c.ticker_id: c for c in existing_result.scalars().all()}

    def _to_int(v):
        try:
            if v is None or pd.isna(v):
                return None
            return int(v)
        except (ValueError, TypeError):
            return None

    count = 0
    for _, row in merged.iterrows():
        sid = str(row.get("stock_id", "")).strip()
        if not sid or sid not in known:
            continue
        fb = _to_int(row.get("foreign_buy"))
        tb = _to_int(row.get("trust_buy"))
        mb = _to_int(row.get("margin_balance"))
        if fb is None and tb is None and mb is None:
            continue
        obj = existing.get(sid)
        if obj is None:
            db.add(DailyChip(
                date=target_date, ticker_id=sid,
                foreign_buy=fb, trust_buy=tb, margin_balance=mb,
            ))
            count += 1
        else:
            obj.foreign_buy = fb
            obj.trust_buy = tb
            obj.margin_balance = mb

    await db.commit()
    logger.info(f"Synced {count} new daily chips for {target_date} (updated {len(existing)} existing)")
    return count


async def sync_fundamentals(db: AsyncSession, target_date) -> int:
    """
    填入當日 pe_ratio / eps 到 daily_prices。
    pe_ratio 來自 TWSE BWIBBU_ALL；eps 由 close / pe_ratio 推算 (pe>0)。
    """
    import pandas as pd
    from sqlalchemy import update

    per_df = await data_fetcher.get_per_pbr()
    if per_df.empty:
        logger.warning("No fundamental data available (BWIBBU_ALL empty)")
        return 0

    close_rows = await db.execute(
        select(DailyPrice.ticker_id, DailyPrice.close).where(DailyPrice.date == target_date)
    )
    close_map = {tid: c for tid, c in close_rows.fetchall()}

    count = 0
    for _, row in per_df.iterrows():
        sid = str(row.get("stock_id", "")).strip()
        if sid not in close_map:
            continue
        pe = row.get("pe_ratio")
        if pe is None or pd.isna(pe):
            continue
        pe = float(pe)
        close = close_map.get(sid)
        eps = round(close / pe, 2) if (pe > 0 and close) else None
        await db.execute(
            update(DailyPrice)
            .where(DailyPrice.ticker_id == sid, DailyPrice.date == target_date)
            .values(pe_ratio=round(pe, 2), eps=eps)
        )
        count += 1

    if count > 0:
        await db.commit()
    logger.info(f"Synced fundamentals (pe/eps) for {count} tickers on {target_date}")
    return count


async def sync_market_index(db: AsyncSession, target_date=None) -> bool:
    """
    同步 TAIEX 大盤指數資料，計算多頭條件並寫入 market_index 表。
    回傳當日大盤條件是否滿足 (ok)。
    """
    import pandas as pd
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy import insert

    if target_date is None:
        target_date = datetime.now().date()

    # 確認是否已計算
    existing = await db.execute(
        select(MarketIndex).where(MarketIndex.date == target_date)
    )
    row = existing.scalar_one_or_none()
    if row is not None and row.ok is not None:
        return bool(row.ok)

    # 抓 TAIEX 歷史 (需要 60 週資料 = 約 300 交易日)
    start_str = (target_date - timedelta(days=450)).strftime("%Y-%m-%d")
    end_str = target_date.strftime("%Y-%m-%d")

    try:
        # Yahoo Finance 大盤代碼: ^TWII (透過 _fetch_yahoo_historical 支援特殊 symbol)
        taiex_df = await data_fetcher.get_historical_data("^TWII", start_str, end_str)
        if taiex_df.empty:
            # 嘗試備用 symbol
            taiex_df = await data_fetcher.get_historical_data("0050", start_str, end_str)
    except Exception as e:
        logger.warning(f"Failed to fetch TAIEX data: {e}")
        taiex_df = pd.DataFrame()

    if taiex_df.empty:
        logger.warning("No TAIEX data available, market_ok will be NULL")
        return False

    # 統一欄位名
    if "close" not in taiex_df.columns:
        for col in ["Close", "ClosingPrice", "close_price"]:
            if col in taiex_df.columns:
                taiex_df = taiex_df.rename(columns={col: "close"})
                break

    if "date" not in taiex_df.columns:
        for col in ["Date", "trade_date"]:
            if col in taiex_df.columns:
                taiex_df = taiex_df.rename(columns={col: "date"})
                break

    if "close" not in taiex_df.columns or "date" not in taiex_df.columns:
        logger.warning("TAIEX data missing required columns")
        return False

    taiex_df = taiex_df[["date", "close"]].copy()
    taiex_df["date"] = pd.to_datetime(taiex_df["date"]).dt.date
    taiex_df = taiex_df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    taiex_df["close"] = pd.to_numeric(taiex_df["close"], errors="coerce")
    taiex_df = taiex_df.dropna(subset=["close"])

    n = len(taiex_df)
    if n < 5:
        logger.warning(f"Insufficient TAIEX data ({n} rows)")
        return False

    # 日線 MA20, MA60
    taiex_df["ma20"] = taiex_df["close"].rolling(20).mean()
    taiex_df["ma60"] = taiex_df["close"].rolling(60).mean()

    # 週線: ISO 週分組，取每週最後一根收盤
    taiex_df["iso_year"] = pd.to_datetime(taiex_df["date"]).dt.isocalendar().year.values
    taiex_df["iso_week"] = pd.to_datetime(taiex_df["date"]).dt.isocalendar().week.values

    weekly = (
        taiex_df.groupby(["iso_year", "iso_week"], sort=True)
        .agg(week_close=("close", "last"), week_end_date=("date", "last"))
        .reset_index()
    )
    weekly["wma20"] = weekly["week_close"].rolling(20).mean()

    # 合併週線 wma20 回日線 (forward-fill)
    taiex_df = taiex_df.merge(
        weekly[["iso_year", "iso_week", "wma20", "week_close"]],
        on=["iso_year", "iso_week"],
        how="left",
    )
    # forward-fill within date order
    taiex_df["wma20_filled"] = taiex_df["wma20"].ffill()
    taiex_df["weekly_close_filled"] = taiex_df["week_close"].ffill()

    # 取最新一列 (target_date 或最近交易日)
    latest = taiex_df[taiex_df["date"] <= target_date].tail(1)
    if latest.empty:
        return False

    row_data = latest.iloc[0]
    close_val = float(row_data["close"]) if not pd.isna(row_data["close"]) else None
    ma20_val = float(row_data["ma20"]) if not pd.isna(row_data["ma20"]) else None
    ma60_val = float(row_data["ma60"]) if not pd.isna(row_data["ma60"]) else None
    wma20_val = float(row_data["wma20_filled"]) if not pd.isna(row_data["wma20_filled"]) else None
    weekly_close_val = float(row_data["weekly_close_filled"]) if not pd.isna(row_data["weekly_close_filled"]) else None

    # 大盤條件:
    # 大盤收盤 >= 大盤MA20
    # AND 大盤MA20 >= 大盤MA60
    # AND 大盤週收盤 >= 大盤週MA20
    ok = (
        close_val is not None and ma20_val is not None and ma60_val is not None
        and wma20_val is not None and weekly_close_val is not None
        and close_val >= ma20_val
        and ma20_val >= ma60_val
        and weekly_close_val >= wma20_val
    )

    # Upsert market_index
    from sqlalchemy.dialects.sqlite import insert as _sqlite_insert
    from sqlalchemy import text

    existing_row = await db.execute(
        select(MarketIndex).where(MarketIndex.date == target_date)
    )
    existing_obj = existing_row.scalar_one_or_none()

    if existing_obj is None:
        db.add(MarketIndex(
            date=target_date,
            close=close_val,
            ma20=ma20_val,
            ma60=ma60_val,
            weekly_close=weekly_close_val,
            wma20=wma20_val,
            ok=ok,
        ))
    else:
        existing_obj.close = close_val
        existing_obj.ma20 = ma20_val
        existing_obj.ma60 = ma60_val
        existing_obj.weekly_close = weekly_close_val
        existing_obj.wma20 = wma20_val
        existing_obj.ok = ok

    await db.commit()
    logger.info(f"MarketIndex {target_date}: close={close_val}, ma20={ma20_val}, ma60={ma60_val}, "
                f"weekly_close={weekly_close_val}, wma20={wma20_val}, ok={ok}")
    return bool(ok)


def _empty_pullback_flags() -> dict[str, bool]:
    return {field: False for field in PULLBACK_FLAG_FIELDS}


def _pullback_depth_flags(wave_low, wave_high, latest_close) -> tuple[bool, bool]:
    try:
        low = float(wave_low)
        high = float(wave_high)
        close = float(latest_close)
    except (TypeError, ValueError):
        return False, False

    if low != low or high != high or close != close or high <= low:
        return False, False

    ratio = (high - close) / (high - low)
    if ratio < 0 or ratio > 1:
        return False, False

    return (
        PULLBACK_ONE_THIRD <= ratio < PULLBACK_TWO_THIRDS,
        ratio >= PULLBACK_TWO_THIRDS,
    )


def _latest_ma_from_close(closes, window: int) -> float | None:
    valid = closes.dropna()
    if len(valid) < window:
        return None
    return round(float(valid.tail(window).mean()), 2)


def _compute_ma_bull_pullback_flags(
    hist,
    *,
    window_days: int = PULLBACK_WINDOW_DAYS,
    breakout_lookback_days: int = BREAKOUT_LOOKBACK_DAYS,
) -> dict[str, bool]:
    """
    Compute four MA-bull pullback presets for the latest row in a price history.

    low_high: latest close pullback depth from the recent low-to-high wave.
    breakout: latest close pullback depth from start low to post-breakout high.
    """
    import pandas as pd

    flags = _empty_pullback_flags()
    if hist is None or getattr(hist, "empty", True):
        return flags
    if not {"close", "high", "low"}.issubset(hist.columns):
        return flags

    work = hist.copy()
    if "date" in work.columns:
        work = work.sort_values("date")
    work = work.reset_index(drop=True)
    closes = pd.to_numeric(work["close"], errors="coerce")
    highs = pd.to_numeric(work["high"], errors="coerce")
    lows = pd.to_numeric(work["low"], errors="coerce")

    if closes.empty or pd.isna(closes.iloc[-1]):
        return flags

    ma5 = _latest_ma_from_close(closes, 5)
    ma20 = _latest_ma_from_close(closes, 20)
    ma60 = _latest_ma_from_close(closes, 60)
    if ma5 is None or ma20 is None or ma60 is None or not (ma5 > ma20 > ma60):
        return flags

    latest_close = float(closes.iloc[-1])
    wave = pd.DataFrame({"high": highs, "low": lows}).dropna().reset_index(drop=True)
    if len(wave) < 2:
        return flags

    recent = wave.tail(window_days).reset_index(drop=True)
    if len(recent) >= 2:
        low_pos = int(recent["low"].idxmin())
        high_after_low = recent.loc[low_pos:]
        high_pos = int(high_after_low["high"].idxmax())
        if high_pos > low_pos:
            one_third, two_thirds = _pullback_depth_flags(
                recent.loc[low_pos, "low"],
                recent.loc[high_pos, "high"],
                latest_close,
            )
            flags["ma_bull_pullback_low_high_1_3"] = one_third
            flags["ma_bull_pullback_low_high_2_3"] = two_thirds

    if breakout_lookback_days > 0 and len(wave) > breakout_lookback_days:
        breakout_wave = wave.copy()
        breakout_wave["prior_high"] = (
            breakout_wave["high"]
            .shift(1)
            .rolling(breakout_lookback_days, min_periods=breakout_lookback_days)
            .max()
        )
        recent_start = max(0, len(breakout_wave) - window_days)
        recent_breakouts = breakout_wave.iloc[recent_start:]
        candidates = recent_breakouts[
            recent_breakouts["prior_high"].notna()
            & (recent_breakouts["high"] > recent_breakouts["prior_high"])
        ]
        if not candidates.empty:
            breakout_pos = int(candidates.index[0])
            base_slice = breakout_wave.loc[recent_start:breakout_pos]
            post_breakout_slice = breakout_wave.loc[breakout_pos:]
            start_low = base_slice["low"].min()
            post_breakout_high = post_breakout_slice["high"].max()
            one_third, two_thirds = _pullback_depth_flags(
                start_low,
                post_breakout_high,
                latest_close,
            )
            flags["ma_bull_pullback_breakout_1_3"] = one_third
            flags["ma_bull_pullback_breakout_2_3"] = two_thirds

    return flags


async def _backfill_indicators(db: AsyncSession, target_date) -> int:
    async with _maintenance_write_lock:
        return await _backfill_indicators_unlocked(db, target_date)


async def _backfill_indicators_unlocked(db: AsyncSession, target_date) -> int:
    """
    對 target_date 那天缺少延伸指標的股票補算並回寫 DB。

    計算項目:
    - ma5, ma10, ma20, ma60 (日線 MA)
    - rsi14 (RSI)
    - avg_volume_20 (20日平均成交量)
    - avg_turnover_20 (20日平均成交值)
    - lower_shadow (下引價)
    - lowest_lower_shadow_20 (Ref(Lowest(下引價,20),1))
    - wma10, wma20, wma60 (週線 MA)
    - market_ok (大盤條件)

    若 v1 DB 歷史不足，fallback 到 Legacy data_fetcher 抓歷史資料。

    Returns:
        int — 因 batch_size 上限而尚未在本次處理的股票數（pending）。
        呼叫端可據此持續重跑直到回傳 0（見 main.py 冷啟動 backfill 迴圈）。
    """
    import pandas as pd
    from sqlalchemy import update, and_, or_

    # 找出當天缺少 MA 或延伸指標的所有 ticker_ids
    missing_result = await db.execute(
        select(DailyPrice.ticker_id).where(
            DailyPrice.date == target_date,
            DailyPrice.ma5.is_(None),
        )
    )
    missing_tickers = [r[0] for r in missing_result.fetchall()]

    # 另外找出 ma5 已存在但延伸指標缺失的股票。
    # Additive schema migrations create new nullable columns on old DBs; every
    # derived screening field must be included here so startup backfill can
    # repair existing latest rows without waiting for a new trading day.
    extended_missing_result = await db.execute(
        select(DailyPrice.ticker_id).where(
            DailyPrice.date == target_date,
            DailyPrice.ma5.is_not(None),
            or_(
                DailyPrice.avg_volume_20.is_(None),
                DailyPrice.avg_turnover_20.is_(None),
                DailyPrice.lower_shadow.is_(None),
                DailyPrice.lowest_lower_shadow_20.is_(None),
                DailyPrice.ma20_curr_month_low.is_(None),
                DailyPrice.ma20_prev_month_low.is_(None),
                DailyPrice.wma10.is_(None),
                DailyPrice.wma20.is_(None),
                DailyPrice.wma60.is_(None),
                DailyPrice.ma_bull_pullback_low_high_1_3.is_(None),
                DailyPrice.ma_bull_pullback_low_high_2_3.is_(None),
                DailyPrice.ma_bull_pullback_breakout_1_3.is_(None),
                DailyPrice.ma_bull_pullback_breakout_2_3.is_(None),
            ),
        )
    )
    extended_missing = [r[0] for r in extended_missing_result.fetchall()]

    # 合併去重
    all_missing = list(set(missing_tickers + extended_missing))

    if not all_missing:
        # 同步大盤資料（即使股票指標都已存在）
        try:
            await sync_market_index(db, target_date)
            await _apply_market_ok(db, target_date)
        except Exception as e:
            logger.warning(f"Market index sync failed: {e}")
        return 0

    logger.info(f"Backfilling indicators for {len(all_missing)} tickers on {target_date}...")

    # 批次載入 v1 DB 歷史資料（需要至少 60 週 = ~300 天的歷史）
    lookback_date = target_date - timedelta(days=450)

    hist_result = await db.execute(
        select(
            DailyPrice.ticker_id,
            DailyPrice.date,
            DailyPrice.open,
            DailyPrice.high,
            DailyPrice.close,
            DailyPrice.low,
            DailyPrice.volume,
            DailyPrice.turnover,
            DailyPrice.lower_shadow,
        )
        .where(
            DailyPrice.ticker_id.in_(all_missing),
            DailyPrice.date >= lookback_date,
            DailyPrice.date <= target_date,
        )
        .order_by(DailyPrice.ticker_id, DailyPrice.date)
    )
    hist_rows = hist_result.fetchall()

    df = pd.DataFrame([dict(r._mapping) for r in hist_rows]) if hist_rows else pd.DataFrame()
    db_day_counts = {}
    if not df.empty:
        db_day_counts = df.groupby("ticker_id").size().to_dict()

    # 找出 DB 歷史不足 N 天的股票（需要 fallback） — 由 settings.backfill_min_days 控制
    settings = get_settings()
    min_days = settings.backfill_min_days
    need_fallback = [t for t in all_missing if db_day_counts.get(t, 0) < min_days]

    # 因 batch_size 上限本次無法處理的股票數，回傳給呼叫端持續重跑
    pending_count = max(0, len(need_fallback) - settings.backfill_batch_size)

    # === Fallback: 用 Legacy data_fetcher 抓歷史資料 ===
    fallback_data: dict[str, pd.DataFrame] = {}
    if need_fallback:
        try:
            start_str = (target_date - timedelta(days=450)).strftime("%Y-%m-%d")
            end_str = target_date.strftime("%Y-%m-%d")
            batch_size = settings.backfill_batch_size
            batch = need_fallback[:batch_size]
            pending = len(need_fallback) - len(batch)
            if pending > 0:
                logger.warning(
                    f"Backfill batch capped at {batch_size}; still {pending} tickers pending for next pass"
                )

            # 並行抓取，Semaphore 限流避免打爆 Yahoo/TWSE
            sem = asyncio.Semaphore(settings.backfill_concurrency)
            col_map_pairs = [
                ("Close", "close"), ("Open", "open"), ("Low", "low"), ("High", "high"),
                # FinMind / Yahoo / TWSE historical use min/max for low/high
                ("min", "low"), ("max", "high"),
                ("Volume", "volume"), ("Date", "date"),
                ("ClosingPrice", "close"), ("OpeningPrice", "open"),
                ("LowestPrice", "low"), ("HighestPrice", "high"),
                ("Trading_Volume", "volume"),
                ("stock_id", "ticker_id"),
            ]

            async def _one(ticker_id: str):
                async with sem:
                    try:
                        hist_df = await data_fetcher.get_historical_data(ticker_id, start_str, end_str)
                    except Exception as e:
                        logger.debug(f"Backfill fetch failed for {ticker_id}: {e}")
                        return ticker_id, None
                    if hist_df is None or hist_df.empty:
                        return ticker_id, None
                    col_map = {src: dst for src, dst in col_map_pairs
                               if src in hist_df.columns and dst not in hist_df.columns}
                    if col_map:
                        hist_df = hist_df.rename(columns=col_map)
                    if "date" in hist_df.columns:
                        hist_df["date"] = pd.to_datetime(hist_df["date"]).dt.date
                    if "close" not in hist_df.columns:
                        return ticker_id, None
                    return ticker_id, hist_df.sort_values("date").reset_index(drop=True)

            results = await asyncio.gather(*(_one(t) for t in batch), return_exceptions=False)
            for ticker_id, df_out in results:
                if df_out is not None:
                    fallback_data[ticker_id] = df_out
            if fallback_data:
                logger.info(
                    f"Fallback: got history for {len(fallback_data)}/{len(batch)} tickers "
                    f"(concurrency={settings.backfill_concurrency})"
                )
            # #7 觀測性：明確告警抓不到歷史的股票（下市/查無資料/來源異常）
            failed = [t for t in batch if t not in fallback_data]
            if failed:
                logger.warning(
                    f"Backfill: {len(failed)}/{len(batch)} tickers had no fetchable history "
                    f"(will stay NULL — likely delisted/new/no source): {failed[:10]}"
                    + (" ..." if len(failed) > 10 else "")
                )
        except Exception as e:
            logger.warning(f"Fallback history fetch failed: {e}")

    # 計算大盤條件
    try:
        market_ok = await sync_market_index(db, target_date)
    except Exception as e:
        logger.warning(f"Market index sync failed: {e}")
        market_ok = None

    updated = 0
    for ticker_id in all_missing:
        # 優先 fallback，其次 DB 歷史資料
        if ticker_id in fallback_data:
            hist = fallback_data[ticker_id]
        elif not df.empty and ticker_id in db_day_counts:
            hist = df[df["ticker_id"] == ticker_id].sort_values("date").reset_index(drop=True)
        else:
            continue

        if hist.empty:
            continue

        n = len(hist)

        # ---- 收盤序列 ----
        closes = pd.to_numeric(hist["close"], errors="coerce").dropna()
        nc = len(closes)

        # 日線 MA
        ma5  = round(float(closes.tail(5).mean()),  2) if nc >= 5  else None
        ma10 = round(float(closes.tail(10).mean()), 2) if nc >= 10 else None
        ma20 = round(float(closes.tail(20).mean()), 2) if nc >= 20 else None
        ma60 = round(float(closes.tail(60).mean()), 2) if nc >= 60 else None

        # RSI14 (Wilder 平滑，與圖表/技術分析路徑一致)
        rsi14 = None
        if nc >= 15:
            from utils.indicators import wilder_rsi
            rsi_val = wilder_rsi(closes, 14).iloc[-1]
            if pd.notna(rsi_val):
                rsi14 = round(float(rsi_val), 2)

        # ---- 成交量序列 ----
        avg_volume_20 = None
        avg_turnover_20 = None

        if "volume" in hist.columns:
            vols = pd.to_numeric(hist["volume"], errors="coerce")
            if len(vols.dropna()) >= 20:
                avg_volume_20 = round(float(vols.tail(20).mean()), 0)

        # 成交值 (優先用 DB 欄位，否則自行計算)
        if "turnover" in hist.columns and hist["turnover"].notna().sum() >= 20:
            tovs = pd.to_numeric(hist["turnover"], errors="coerce")
        elif "volume" in hist.columns:
            # turnover = close * volume
            tovs = pd.to_numeric(hist["close"], errors="coerce") * pd.to_numeric(hist["volume"], errors="coerce")
        else:
            tovs = pd.Series(dtype=float)

        if len(tovs.dropna()) >= 20:
            avg_turnover_20 = round(float(tovs.tail(20).mean()), 0)

        # ---- 下引價 ----
        # 重新計算 (從 open/low/close 推算)
        lower_shadow_target = None
        if all(c in hist.columns for c in ["open", "low", "close"]):
            opens_s = pd.to_numeric(hist["open"], errors="coerce")
            lows_s  = pd.to_numeric(hist["low"],  errors="coerce")
            cls_s   = pd.to_numeric(hist["close"], errors="coerce")
            body_bottom = opens_s.combine(cls_s, min)
            ls_series = (body_bottom - lows_s).clip(lower=0.0)
            # 當天下引價 (最後一行)
            if not ls_series.empty and not pd.isna(ls_series.iloc[-1]):
                lower_shadow_target = round(float(ls_series.iloc[-1]), 4)

            # Ref(Lowest(下引價, 20), 1):
            # 前一日為基準的近20日下引價最低值
            # = ls_series.shift(1) 後的最近20筆最小值 => rolling(20).min().shift(1)
            # 即當天之前20個交易日（不含今天）的最低下引價
            lowest_ls_20 = None
            if len(ls_series.dropna()) >= 20:
                # 取前N-1筆（不含今天）的最低值
                prev_ls = ls_series.iloc[:-1]
                if len(prev_ls) >= 20:
                    lowest_ls_20 = round(float(prev_ls.tail(20).min()), 4)

        else:
            lowest_ls_20 = None

        # ---- 週線 MA ----
        wma10 = wma20 = wma60 = None
        if "date" in hist.columns and nc >= 10:
            dates_s = pd.to_datetime(hist["date"].astype(str))
            hist_w = hist.copy()
            hist_w["date_parsed"] = dates_s
            hist_w["close_num"] = pd.to_numeric(hist_w["close"], errors="coerce")
            hist_w["iso_year"] = dates_s.dt.isocalendar().year.values
            hist_w["iso_week"] = dates_s.dt.isocalendar().week.values

            weekly_closes = (
                hist_w.groupby(["iso_year", "iso_week"], sort=True)["close_num"]
                .last()
                .dropna()
            )
            nw = len(weekly_closes)
            wma10 = round(float(weekly_closes.tail(10).mean()), 2) if nw >= 10 else None
            wma20 = round(float(weekly_closes.tail(20).mean()), 2) if nw >= 20 else None
            wma60 = round(float(weekly_closes.tail(60).mean()), 2) if nw >= 60 else None

        # ---- 月度 MA20 最低點 (當月至今 vs 上個月整月) ----
        # 「MA20 月度墊高」：當月(月初~target_date) MA20 最低值 高於 上個月整月 MA20 最低值。
        # 以「欄位對欄位」規則 ma20_curr_month_low > ma20_prev_month_low 比較，引擎邏輯不用改。
        ma20_curr_month_low = None
        ma20_prev_month_low = None
        if "date" in hist.columns and nc >= 20:
            ma20_series = pd.to_numeric(hist["close"], errors="coerce").rolling(20).mean()
            ma_dates = pd.to_datetime(hist["date"], errors="coerce")
            mdf = pd.DataFrame({"d": ma_dates, "ma20": ma20_series}).dropna(subset=["d", "ma20"])
            if not mdf.empty:
                mdf["ym"] = mdf["d"].dt.to_period("M")
                cur_p = pd.Period(target_date, freq="M")
                prev_p = cur_p - 1
                cur_low = mdf.loc[(mdf["ym"] == cur_p) & (mdf["d"].dt.date <= target_date), "ma20"].min()
                prev_low = mdf.loc[mdf["ym"] == prev_p, "ma20"].min()
                if pd.notna(cur_low):
                    ma20_curr_month_low = round(float(cur_low), 2)
                if pd.notna(prev_low):
                    ma20_prev_month_low = round(float(prev_low), 2)

        pullback_flags = _compute_ma_bull_pullback_flags(hist)

        # 回寫
        update_vals: dict = dict(
            ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60, rsi14=rsi14,
            avg_volume_20=avg_volume_20,
            avg_turnover_20=avg_turnover_20,
            wma10=wma10, wma20=wma20, wma60=wma60,
            market_ok=market_ok,
            **pullback_flags,
        )
        if lower_shadow_target is not None:
            update_vals["lower_shadow"] = lower_shadow_target
        if lowest_ls_20 is not None:
            update_vals["lowest_lower_shadow_20"] = lowest_ls_20
        if ma20_curr_month_low is not None:
            update_vals["ma20_curr_month_low"] = ma20_curr_month_low
        if ma20_prev_month_low is not None:
            update_vals["ma20_prev_month_low"] = ma20_prev_month_low

        await db.execute(
            update(DailyPrice)
            .where(
                and_(
                    DailyPrice.ticker_id == ticker_id,
                    DailyPrice.date == target_date,
                )
            )
            .values(**update_vals)
        )
        updated += 1

    if updated > 0:
        await db.commit()
        logger.info(f"Backfilled indicators for {updated} tickers on {target_date}")

    # #4 持久化抓取到的歷史 K 線 → 讓 CROSS/多日篩選可用，並避免每日重抓
    if fallback_data:
        await _persist_fetched_history(db, fallback_data, target_date)

    # 套用大盤條件到剩餘已有指標的股票
    await _apply_market_ok(db, target_date)

    return pending_count


async def _persist_fetched_history(db: AsyncSession, fallback_data: dict, target_date) -> None:
    """
    將 fallback 抓到的歷史 K 線（target_date 之前的交易日）寫入 daily_prices，
    並計算每列的 ma5/ma10/ma20/ma60/rsi14，供 CROSS_UP/CROSS_DOWN 與多日篩選使用。

    只插入「尚未存在」的 (ticker_id, date)；target_date 當天列由既有邏輯維護，不在此覆寫。
    以 _sync_daily_lock 序列化，避免與其他 sync 路徑的 check-then-insert race。
    """
    import pandas as pd

    def _f(v):
        try:
            return None if (v is None or pd.isna(v)) else round(float(v), 4)
        except (ValueError, TypeError):
            return None

    def _i(v):
        try:
            return None if (v is None or pd.isna(v)) else int(float(v))
        except (ValueError, TypeError):
            return None

    tickers = list(fallback_data.keys())
    async with _sync_daily_lock:
        existing_result = await db.execute(
            select(DailyPrice.ticker_id, DailyPrice.date)
            .where(DailyPrice.ticker_id.in_(tickers))
        )
        existing = {(t, d) for t, d in existing_result.fetchall()}

        mappings = []
        for tid, hist in fallback_data.items():
            if hist is None or hist.empty or "date" not in hist.columns or "close" not in hist.columns:
                continue
            h = hist.copy()
            closes = pd.to_numeric(h["close"], errors="coerce")
            # 漲跌幅 = 與前一交易日收盤比較 (供歷史漲停/漲跌幅判定，避免該欄位永遠 NULL)
            h["_cp"] = closes.pct_change() * 100
            h["_ma5"] = closes.rolling(5).mean()
            h["_ma10"] = closes.rolling(10).mean()
            h["_ma20"] = closes.rolling(20).mean()
            h["_ma60"] = closes.rolling(60).mean()
            from utils.indicators import wilder_rsi
            h["_rsi14"] = wilder_rsi(closes, 14)

            for _, r in h.iterrows():
                d = r["date"]
                if isinstance(d, str):
                    try:
                        d = datetime.strptime(d, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                if d is None or d >= target_date or (tid, d) in existing:
                    continue
                close = _f(r.get("close"))
                if close is None:
                    continue
                open_p = _f(r.get("open"))
                low = _f(r.get("low"))
                vol = _i(r.get("volume"))
                turnover = round(close * vol, 0) if (close is not None and vol is not None) else None
                lower_shadow = None
                if low is not None and open_p is not None:
                    lower_shadow = round(max(0.0, min(open_p, close) - low), 4)
                mappings.append({
                    "date": d, "ticker_id": tid,
                    "open": open_p, "high": _f(r.get("high")), "low": low,
                    "close": close, "volume": vol,
                    "turnover": turnover, "lower_shadow": lower_shadow,
                    "change_percent": _f(r.get("_cp")),
                    "ma5": _f(r.get("_ma5")), "ma10": _f(r.get("_ma10")),
                    "ma20": _f(r.get("_ma20")), "ma60": _f(r.get("_ma60")),
                    "rsi14": _f(r.get("_rsi14")),
                })
                existing.add((tid, d))

        if mappings:
            await db.execute(DailyPrice.__table__.insert(), mappings)
            await db.commit()
            logger.info(f"Persisted {len(mappings)} historical K-line rows (CROSS/multi-day enabled)")


async def _apply_market_ok(db: AsyncSession, target_date) -> None:
    """
    將 market_index 的 ok 值寫入當日所有股票的 market_ok 欄位。
    （只更新 market_ok 為 NULL 的記錄）
    """
    from sqlalchemy import update

    mi = await db.execute(select(MarketIndex).where(MarketIndex.date == target_date))
    mi_row = mi.scalar_one_or_none()
    if mi_row is None:
        return

    ok_val = mi_row.ok
    await db.execute(
        update(DailyPrice)
        .where(DailyPrice.date == target_date, DailyPrice.market_ok.is_(None))
        .values(market_ok=ok_val)
    )
    await db.commit()


def _safe_float(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                fv = float(str(v).replace(",", ""))
            except (ValueError, TypeError):
                continue
            # NaN（來源欄位為 pandas NaN）視為缺值，避免 NaN 寫入 DB 汙染指標計算
            if fv != fv:  # NaN check without importing math
                continue
            return fv
    return None


def _safe_int(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return int(float(str(v).replace(",", "")))
            except (ValueError, TypeError):
                continue
    return None


async def backfill_all_indicators(db: AsyncSession, max_dates: int = 30) -> int:
    """
    對「有價格列但缺指標」的所有日期補算指標（非只有最新日）。

    冷啟動補資料只跑最新日，導致 gap 日（伺服器停機期間補進的舊交易日）
    指標永遠為 NULL → 該日的 v1 篩選/圖表「沒有資料」。此函式掃出所有
    ma5 或 avg_volume_20 為 NULL 的日期，由新到舊逐日 _backfill_indicators。

    Args:
        max_dates: 單次最多處理的日期數（保護，避免冷啟動跑太久）。

    Returns:
        實際處理的日期數。
    """
    from sqlalchemy import func, or_

    result = await db.execute(
        select(DailyPrice.date)
        .where(or_(
            DailyPrice.ma5.is_(None),
            DailyPrice.avg_volume_20.is_(None),
            DailyPrice.ma_bull_pullback_low_high_1_3.is_(None),
            DailyPrice.ma_bull_pullback_low_high_2_3.is_(None),
            DailyPrice.ma_bull_pullback_breakout_1_3.is_(None),
            DailyPrice.ma_bull_pullback_breakout_2_3.is_(None),
        ))
        .distinct()
        .order_by(DailyPrice.date.desc())
        .limit(max_dates)
    )
    dates = [r[0] for r in result.fetchall()]
    if not dates:
        return 0

    logger.info(f"backfill_all_indicators: {len(dates)} date(s) need indicators: {dates[:5]}...")
    for d in dates:
        try:
            await _backfill_indicators(db, d)
        except Exception as e:
            logger.warning(f"backfill_all_indicators failed for {d}: {e}")
    logger.info(f"backfill_all_indicators: processed {len(dates)} date(s)")
    return len(dates)


async def ensure_fresh_data(db: AsyncSession, *, force: bool = False) -> dict:
    """
    確保 v1 DB 已同步到「最新可用交易日」。供讀取路徑（screener / ensure-latest
    端點）按需呼叫，自動修復「無最新資料」——不依賴交易時段或伺服器是否持續運行。

    流程：
      1. 比較 DB max(date) 與日曆最新交易日。
      2. 已是最新 → 直接回傳（不打外部 API）。
      3. 落後 → 經冷卻保護 + 鎖序列化後，sync_daily_prices(latest) 補上最新交易日。
         （TWSE STOCK_DAY_ALL 永遠回最近收盤日，sync 內以 API 實際日期寫入。）
      4. 失敗不拋例外（呼叫端仍可服務既有資料）。

    Returns:
        dict(synced, db_date, latest_date, fresh, throttled)
    """
    import time
    from sqlalchemy import func
    from utils.date_utils import get_latest_trading_day

    global _last_catchup_monotonic

    latest_str = get_latest_trading_day()
    try:
        latest_date = datetime.strptime(latest_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"synced": 0, "db_date": None, "latest_date": latest_str, "fresh": False}

    db_max = (await db.execute(select(func.max(DailyPrice.date)))).scalar()

    # 已是最新（或更新）→ 不動作
    if db_max is not None and db_max >= latest_date and not force:
        return {"synced": 0, "db_date": str(db_max), "latest_date": latest_str, "fresh": True}

    # 冷卻保護：避免讀取路徑被打爆時重複觸發外部抓取
    now = time.monotonic()
    if not force and (now - _last_catchup_monotonic) < _CATCHUP_COOLDOWN_SECS:
        return {
            "synced": 0,
            "db_date": str(db_max) if db_max else None,
            "latest_date": latest_str,
            "fresh": False,
            "throttled": True,
        }

    async with _catchup_lock:
        # 取得鎖後重新檢查（可能另一個請求已補完）
        db_max = (await db.execute(select(func.max(DailyPrice.date)))).scalar()
        if db_max is not None and db_max >= latest_date and not force:
            return {"synced": 0, "db_date": str(db_max), "latest_date": latest_str, "fresh": True}

        _last_catchup_monotonic = time.monotonic()
        synced = 0
        try:
            synced = await sync_daily_prices(db, latest_str)
        except Exception as e:
            logger.warning(f"ensure_fresh_data: sync_daily_prices failed: {e}", exc_info=True)

        new_max = (await db.execute(select(func.max(DailyPrice.date)))).scalar()
        return {
            "synced": synced,
            "db_date": str(new_max) if new_max else None,
            "latest_date": latest_str,
            "fresh": new_max is not None and new_max >= latest_date,
        }
