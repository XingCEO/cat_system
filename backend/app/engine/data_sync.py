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

    await db.commit()
    logger.info(f"Synced {count} new tickers")
    return count


async def sync_daily_prices(db: AsyncSession, trade_date: Optional[str] = None) -> int:
    """同步日K線資料到 daily_prices 表"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    daily_df = await data_fetcher.get_daily_data(trade_date)
    if daily_df.empty:
        return 0

    date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()
    count = 0

    for _, row in daily_df.iterrows():
        ticker_id = str(row.get("stock_id", row.get("Code", "")))
        if not ticker_id:
            continue

        close = _safe_float(row, "close", "ClosingPrice")
        if close is None:
            continue

        existing = await db.execute(
            select(DailyPrice).where(
                DailyPrice.ticker_id == ticker_id,
                DailyPrice.date == date_obj
            )
        )
        if existing.scalar_one_or_none():
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

    await db.commit()
    logger.info(f"Synced {count} daily prices for {trade_date}")
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
