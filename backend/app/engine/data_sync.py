"""
Data Sync — 從 Legacy data_fetcher 同步資料到 v1 表 (Ticker, DailyPrice, DailyChip)
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from app.models.daily_chip import DailyChip
from services.data_fetcher import data_fetcher

logger = logging.getLogger(__name__)


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
        trade_date = datetime.now().strftime("%Y-%m-%d")

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
        # 只同步已知 tickers（skipREITs、受益憑證等沒有基本資料的）
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
        prev_close = close - change if change is not None and close else None
        if prev_close and prev_close > 0 and change is not None:
            change_pct = round(change / prev_close * 100, 2)

        db.add(DailyPrice(
            date=date_obj,
            ticker_id=ticker_id,
            open=open_p,
            high=high,
            low=low,
            close=close,
            volume=volume,
            change_percent=change_pct,
        ))
        count += 1

    if count > 0:
        await db.commit()
    if skipped_unknown > 0:
        logger.info(f"Skipped {skipped_unknown} unknown ticker_ids (REITs, etc.)")
    logger.info(f"Synced {count} daily prices for {date_obj}")

    # 補算技術指標 (MA5/10/20/60, RSI14)
    await _backfill_indicators(db, date_obj)

    return count


async def _backfill_indicators(db: AsyncSession, target_date) -> None:
    """
    對 target_date 那天 ma5/ma10/ma20/ma60/rsi14 為 NULL 的股票，
    用歷史資料補算技術指標並回寫 DB。

    如果 v1 DB 的歷史天數不足（例如剛啟動，只有 1 天），
    會 fallback 到 Legacy data_fetcher 拿 FinMind/Yahoo 歷史資料來計算。
    """
    import pandas as pd
    from sqlalchemy import update, and_

    # 找出當天缺少 MA 的所有 ticker_ids
    missing_result = await db.execute(
        select(DailyPrice.ticker_id).where(
            DailyPrice.date == target_date,
            DailyPrice.ma5.is_(None),
        )
    )
    missing_tickers = [r[0] for r in missing_result.fetchall()]

    if not missing_tickers:
        return

    logger.info(f"Backfilling indicators for {len(missing_tickers)} tickers on {target_date}...")

    # 批次載入 v1 DB 歷史資料
    from datetime import timedelta
    lookback_date = target_date - timedelta(days=120)

    hist_result = await db.execute(
        select(
            DailyPrice.ticker_id,
            DailyPrice.date,
            DailyPrice.close,
        )
        .where(
            DailyPrice.ticker_id.in_(missing_tickers),
            DailyPrice.date >= lookback_date,
            DailyPrice.date <= target_date,
        )
        .order_by(DailyPrice.ticker_id, DailyPrice.date)
    )
    hist_rows = hist_result.fetchall()

    # 看 DB 裡每支股票有幾天資料
    df = pd.DataFrame([dict(r._mapping) for r in hist_rows]) if hist_rows else pd.DataFrame()
    db_day_counts = {}
    if not df.empty:
        db_day_counts = df.groupby("ticker_id").size().to_dict()

    # 找出 DB 歷史不足 5 天的股票（需要 fallback）
    need_fallback = [t for t in missing_tickers if db_day_counts.get(t, 0) < 5]

    # === Fallback: 用 Legacy data_fetcher 抓歷史資料 ===
    fallback_data = {}
    if need_fallback:
        try:
            start_str = (target_date - timedelta(days=200)).strftime("%Y-%m-%d")
            end_str = target_date.strftime("%Y-%m-%d")
            # 限制每次最多處理 200 支，避免 API 負擔太大
            batch = need_fallback[:200]
            for ticker_id in batch:
                try:
                    hist_df = await data_fetcher.get_historical_data(ticker_id, start_str, end_str)
                    if not hist_df.empty and "close" in hist_df.columns:
                        if "date" in hist_df.columns:
                            hist_df = hist_df.sort_values("date")
                        closes = pd.to_numeric(hist_df["close"], errors="coerce").dropna()
                        if len(closes) >= 5:
                            fallback_data[ticker_id] = closes
                except Exception:
                    continue
            if fallback_data:
                logger.info(f"Fallback: got history for {len(fallback_data)}/{len(batch)} tickers from Legacy API")
        except Exception as e:
            logger.warning(f"Fallback history fetch failed: {e}")

    updated = 0
    for ticker_id in missing_tickers:
        # 優先使用 DB 歷史資料，不足時用 fallback
        if ticker_id in fallback_data:
            closes = fallback_data[ticker_id]
        elif not df.empty and ticker_id in db_day_counts:
            group = df[df["ticker_id"] == ticker_id].sort_values("date").reset_index(drop=True)
            if group.empty:
                continue
            closes = group["close"].astype(float)
        else:
            continue

        n = len(closes)

        # 計算 MA
        ma5 = round(float(closes.tail(5).mean()), 2) if n >= 5 else None
        ma10 = round(float(closes.tail(10).mean()), 2) if n >= 10 else None
        ma20 = round(float(closes.tail(20).mean()), 2) if n >= 20 else None
        ma60 = round(float(closes.tail(60).mean()), 2) if n >= 60 else None

        # 計算 RSI14
        rsi14 = None
        if n >= 15:
            delta = closes.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.rolling(window=14).mean().iloc[-1]
            avg_loss = loss.rolling(window=14).mean().iloc[-1]
            if avg_loss != 0:
                rs = avg_gain / avg_loss
                rsi14 = round(float(100 - (100 / (1 + rs))), 2)

        # 回寫
        await db.execute(
            update(DailyPrice)
            .where(
                and_(
                    DailyPrice.ticker_id == ticker_id,
                    DailyPrice.date == target_date,
                )
            )
            .values(ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60, rsi14=rsi14)
        )
        updated += 1

    if updated > 0:
        await db.commit()
        logger.info(f"Backfilled indicators for {updated} tickers on {target_date}")


def _safe_float(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return float(str(v).replace(",", ""))
            except (ValueError, TypeError):
                continue
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
