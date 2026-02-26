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
    return count


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
