"""
sync_actual_latest.py - synchronize local DB to the latest official TWSE snapshot.

Uses the existing production sync path:
  - init_db additive migrations;
  - sync_tickers;
  - sync_daily_prices, which stores the actual date returned by the source;
  - repair latest-date derived indicators until no pending batch remains.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import app.models  # noqa: F401 - register ORM models before init_db
from sqlalchemy import func, select

from database import async_session_maker, init_db
from services.data_fetcher import data_fetcher
from app.engine.data_sync import _backfill_indicators, sync_daily_prices, sync_tickers
from app.models.daily_price import DailyPrice


async def main() -> int:
    await init_db()
    trade_date = await data_fetcher.get_latest_trading_date()

    async with async_session_maker() as session:
        ticker_count = await sync_tickers(session)

    async with async_session_maker() as session:
        price_count = await sync_daily_prices(session, trade_date)
        latest = (await session.execute(select(func.max(DailyPrice.date)))).scalar()
        pending = None
        passes = 0
        if latest is not None:
            while passes < 5:
                passes += 1
                pending = await _backfill_indicators(session, latest)
                if pending == 0:
                    break

    status = "pass" if latest is not None and (pending == 0 or pending is None) else "fail"
    print(json.dumps({
        "status": status,
        "queried_trade_date": trade_date,
        "db_latest_date": str(latest) if latest is not None else None,
        "new_tickers": ticker_count,
        "new_prices": price_count,
        "backfill_passes": passes,
        "pending": pending,
    }, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
