"""
repair_latest_indicators.py - repair derived indicators on the DB latest date.

This is intentionally narrow:
  - runs the normal additive schema migration;
  - finds max(daily_prices.date);
  - calls app.engine.data_sync._backfill_indicators for that date until no
    pending fallback batch remains, or --max-passes is reached.

It does not delete rows or overwrite raw OHLCV source data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import app.models  # noqa: F401 - register ORM models before init_db
from sqlalchemy import func, select, update

from database import async_session_maker, init_db
from app.engine.data_sync import _backfill_indicators
from app.models.daily_price import DailyPrice


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-passes", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="Clear derived latest-date fields before backfill.")
    parser.add_argument("--force-cycles", type=int, default=2, help="Force-clear/backfill cycles when --force is used.")
    args = parser.parse_args()

    await init_db()

    async with async_session_maker() as session:
        latest = (await session.execute(select(func.max(DailyPrice.date)))).scalar()
        if latest is None:
            print(json.dumps({"status": "fail", "reason": "daily_prices is empty"}, ensure_ascii=False))
            return 1

        cycles = max(1, args.force_cycles if args.force else 1)
        passes = 0
        pending = None
        for _ in range(cycles):
            if args.force:
                await session.execute(
                    update(DailyPrice)
                    .where(DailyPrice.date == latest)
                    .values(
                        ma5=None,
                        ma10=None,
                        ma20=None,
                        ma60=None,
                        rsi14=None,
                        avg_volume_20=None,
                        avg_turnover_20=None,
                        lower_shadow=None,
                        lowest_lower_shadow_20=None,
                        ma20_curr_month_low=None,
                        ma20_prev_month_low=None,
                        wma10=None,
                        wma20=None,
                        wma60=None,
                        market_ok=None,
                        ma_bull_pullback_low_high_1_3=None,
                        ma_bull_pullback_low_high_2_3=None,
                        ma_bull_pullback_breakout_1_3=None,
                        ma_bull_pullback_breakout_2_3=None,
                    )
                )
                await session.commit()

            cycle_passes = 0
            while cycle_passes < args.max_passes:
                passes += 1
                cycle_passes += 1
                pending = await _backfill_indicators(session, latest)
                if pending == 0:
                    break

    status = "pass" if pending == 0 else "fail"
    print(json.dumps({
        "status": status,
        "latest_date": str(latest),
        "force": args.force,
        "force_cycles": cycles,
        "passes": passes,
        "pending": pending,
    }, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
