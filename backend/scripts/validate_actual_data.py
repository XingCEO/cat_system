"""
validate_actual_data.py - read-only production-style data validation.

Checks:
  1. DB coverage for latest global trading date.
  2. Latest-row indicator values recomputed from DB history.
  3. Optional TWSE STOCK_DAY_ALL comparison for the same latest date.

This script does not write to the database or call sync jobs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
from sqlalchemy import func, select

from database import async_session_maker
from app.engine.data_sync import _compute_ma_bull_pullback_flags
from app.models.daily_price import DailyPrice
from app.models.ticker import Ticker
from services.data_fetcher import data_fetcher
from utils.indicators import wilder_rsi


LATEST_FIELDS = [
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "rsi14",
    "turnover",
    "avg_volume_20",
    "avg_turnover_20",
    "lower_shadow",
    "lowest_lower_shadow_20",
    "ma20_curr_month_low",
    "ma20_prev_month_low",
    "wma10",
    "wma20",
    "wma60",
    "ma_bull_pullback_low_high_1_3",
    "ma_bull_pullback_low_high_2_3",
    "ma_bull_pullback_breakout_1_3",
    "ma_bull_pullback_breakout_2_3",
]

EXTERNAL_FIELDS = ["open", "high", "low", "close", "volume", "change_percent", "turnover", "lower_shadow"]

TOLERANCES = {
    "ma5": 0.005,
    "ma10": 0.005,
    "ma20": 0.005,
    "ma60": 0.005,
    "rsi14": 0.005,
    "turnover": 0.5,
    "avg_volume_20": 0.5,
    "avg_turnover_20": 0.5,
    "lower_shadow": 0.00005,
    "lowest_lower_shadow_20": 0.00005,
    "ma20_curr_month_low": 0.005,
    "ma20_prev_month_low": 0.005,
    "wma10": 0.005,
    "wma20": 0.005,
    "wma60": 0.005,
    "ma_bull_pullback_low_high_1_3": 0,
    "ma_bull_pullback_low_high_2_3": 0,
    "ma_bull_pullback_breakout_1_3": 0,
    "ma_bull_pullback_breakout_2_3": 0,
    "open": 0.00005,
    "high": 0.00005,
    "low": 0.00005,
    "close": 0.00005,
    "volume": 0.5,
    "change_percent": 0.005,
}


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)


def _round_or_none(value: Any, digits: int = 2) -> float | None:
    if _is_missing(value):
        return None
    return round(float(value), digits)


def _num_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _matches(actual: Any, expected: Any, tolerance: float) -> bool:
    if _is_missing(actual) and _is_missing(expected):
        return True
    if _is_missing(actual) or _is_missing(expected):
        return False
    return abs(float(actual) - float(expected)) <= tolerance


def _issue(kind: str, ticker_id: str, field: str, actual: Any, expected: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "kind": kind,
        "ticker_id": ticker_id,
        "field": field,
        "db": None if _is_missing(actual) else actual,
        "expected": None if _is_missing(expected) else expected,
    }
    if extra:
        item.update(extra)
    return item


def _compute_latest_expected(hist: pd.DataFrame, target_date: date) -> dict[str, float | None]:
    hist = hist.sort_values("date").reset_index(drop=True)
    # Production _backfill_indicators intentionally computes derived latest-row
    # fields from a bounded 450-day lookback. Use the same window here so this
    # validator checks the actual app contract, not a subtly different oracle.
    hist = hist[hist["date"] >= target_date - timedelta(days=450)].reset_index(drop=True)
    closes = pd.to_numeric(hist["close"], errors="coerce")
    vols = pd.to_numeric(hist.get("volume"), errors="coerce") if "volume" in hist else pd.Series(dtype=float)

    expected: dict[str, Any] = {
        "ma5": _round_or_none(closes.tail(5).mean()) if closes.dropna().shape[0] >= 5 else None,
        "ma10": _round_or_none(closes.tail(10).mean()) if closes.dropna().shape[0] >= 10 else None,
        "ma20": _round_or_none(closes.tail(20).mean()) if closes.dropna().shape[0] >= 20 else None,
        "ma60": _round_or_none(closes.tail(60).mean()) if closes.dropna().shape[0] >= 60 else None,
        "rsi14": None,
        "turnover": None,
        "avg_volume_20": None,
        "avg_turnover_20": None,
        "lower_shadow": None,
        "lowest_lower_shadow_20": None,
        "ma20_curr_month_low": None,
        "ma20_prev_month_low": None,
        "wma10": None,
        "wma20": None,
        "wma60": None,
        "ma_bull_pullback_low_high_1_3": False,
        "ma_bull_pullback_low_high_2_3": False,
        "ma_bull_pullback_breakout_1_3": False,
        "ma_bull_pullback_breakout_2_3": False,
    }

    if closes.dropna().shape[0] >= 15:
        expected["rsi14"] = _round_or_none(wilder_rsi(closes.dropna(), 14).iloc[-1])

    last = hist.iloc[-1]
    close = _num_or_none(last.get("close"))
    volume = _num_or_none(last.get("volume"))
    if close is not None and volume is not None:
        expected["turnover"] = round(close * volume, 0)

    if vols.dropna().shape[0] >= 20:
        expected["avg_volume_20"] = round(float(vols.tail(20).mean()), 0)

    if "turnover" in hist and pd.to_numeric(hist["turnover"], errors="coerce").dropna().shape[0] >= 20:
        turnovers = pd.to_numeric(hist["turnover"], errors="coerce")
    elif close is not None and "volume" in hist:
        turnovers = closes * vols
    else:
        turnovers = pd.Series(dtype=float)
    if turnovers.dropna().shape[0] >= 20:
        expected["avg_turnover_20"] = round(float(turnovers.tail(20).mean()), 0)

    if all(col in hist for col in ["open", "low", "close"]):
        opens = pd.to_numeric(hist["open"], errors="coerce")
        lows = pd.to_numeric(hist["low"], errors="coerce")
        body_bottom = opens.combine(closes, min)
        lower_shadow = (body_bottom - lows).clip(lower=0.0)
        if not lower_shadow.empty and pd.notna(lower_shadow.iloc[-1]):
            expected["lower_shadow"] = round(float(lower_shadow.iloc[-1]), 4)
        prev = lower_shadow.iloc[:-1]
        if prev.dropna().shape[0] >= 20:
            expected["lowest_lower_shadow_20"] = round(float(prev.tail(20).min()), 4)

    if "date" in hist and closes.dropna().shape[0] >= 20:
        ma20_series = closes.rolling(20).mean()
        ma_dates = pd.to_datetime(hist["date"], errors="coerce")
        mdf = pd.DataFrame({"d": ma_dates, "ma20": ma20_series}).dropna(subset=["d", "ma20"])
        if not mdf.empty:
            mdf["ym"] = mdf["d"].dt.to_period("M")
            cur_period = pd.Period(target_date, freq="M")
            prev_period = cur_period - 1
            cur_low = mdf.loc[(mdf["ym"] == cur_period) & (mdf["d"].dt.date <= target_date), "ma20"].min()
            prev_low = mdf.loc[mdf["ym"] == prev_period, "ma20"].min()
            expected["ma20_curr_month_low"] = _round_or_none(cur_low)
            expected["ma20_prev_month_low"] = _round_or_none(prev_low)

    if "date" in hist and closes.dropna().shape[0] >= 10:
        dates = pd.to_datetime(hist["date"].astype(str), errors="coerce")
        weekly = hist.copy()
        weekly["close_num"] = closes
        weekly["iso_year"] = dates.dt.isocalendar().year.values
        weekly["iso_week"] = dates.dt.isocalendar().week.values
        weekly_closes = weekly.groupby(["iso_year", "iso_week"], sort=True)["close_num"].last().dropna()
        expected["wma10"] = _round_or_none(weekly_closes.tail(10).mean()) if len(weekly_closes) >= 10 else None
        expected["wma20"] = _round_or_none(weekly_closes.tail(20).mean()) if len(weekly_closes) >= 20 else None
        expected["wma60"] = _round_or_none(weekly_closes.tail(60).mean()) if len(weekly_closes) >= 60 else None

    expected.update(_compute_ma_bull_pullback_flags(hist))

    return expected


async def _load_db_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    async with async_session_maker() as session:
        tickers = (await session.execute(select(Ticker))).scalars().all()
        prices = (await session.execute(select(DailyPrice).order_by(DailyPrice.ticker_id, DailyPrice.date))).scalars().all()

    tickers_df = pd.DataFrame([
        {
            "ticker_id": t.ticker_id,
            "name": t.name,
            "market_type": t.market_type,
            "industry": t.industry,
        }
        for t in tickers
    ])
    prices_df = pd.DataFrame([
        {
            col.name: getattr(p, col.name)
            for col in DailyPrice.__table__.columns
        }
        for p in prices
    ])
    return tickers_df, prices_df


def _validate_latest_indicators(tickers_df: pd.DataFrame, prices_df: pd.DataFrame, sample_limit: int) -> dict[str, Any]:
    if prices_df.empty:
        return {"status": "fail", "reason": "daily_prices is empty", "issues": []}

    latest = prices_df["date"].max()
    latest_rows = prices_df[prices_df["date"] == latest].copy()
    latest_ids = set(latest_rows["ticker_id"].astype(str))
    ticker_ids = set(tickers_df["ticker_id"].astype(str))
    missing_latest = sorted(ticker_ids - latest_ids)

    issues: list[dict[str, Any]] = []
    for ticker_id, hist in prices_df.groupby("ticker_id", sort=True):
        latest_hist = hist.sort_values("date")
        if latest_hist.empty or latest_hist.iloc[-1]["date"] != latest:
            continue
        row = latest_hist.iloc[-1]
        expected = _compute_latest_expected(latest_hist, latest)
        for field in LATEST_FIELDS:
            actual = row.get(field)
            exp = expected.get(field)
            if not _matches(actual, exp, TOLERANCES[field]):
                issues.append(_issue("db_recompute_mismatch", str(ticker_id), field, actual, exp, {"date": str(latest)}))

    return {
        "status": "pass" if not issues else "fail",
        "coverage_status": "pass" if not missing_latest else "source_check_required",
        "latest_date": str(latest),
        "ticker_count": int(len(ticker_ids)),
        "latest_row_count": int(len(latest_ids)),
        "missing_latest_count": int(len(missing_latest)),
        "missing_latest_sample": missing_latest[:sample_limit],
        "indicator_mismatch_count": int(len(issues)),
        "indicator_mismatch_sample": issues[:sample_limit],
    }


async def _validate_twse_external(tickers_df: pd.DataFrame, prices_df: pd.DataFrame, sample_limit: int) -> dict[str, Any]:
    if prices_df.empty:
        return {"status": "fail", "reason": "daily_prices is empty"}

    latest = prices_df["date"].max()
    external = await data_fetcher._fetch_twse_daily_openapi(datetime.now().date().isoformat())
    if external.empty:
        return {"status": "fail", "reason": "TWSE STOCK_DAY_ALL returned no comparable rows", "latest_date": str(latest)}

    external = external.rename(columns={"stock_id": "ticker_id", "max": "high", "min": "low", "Trading_Volume": "volume"})
    external["ticker_id"] = external["ticker_id"].astype(str)
    external_date = str(external["date"].max())

    if str(latest) != external_date:
        return {
            "status": "fail",
            "reason": "db_latest_date_differs_from_twse",
            "db_latest_date": str(latest),
            "twse_date": external_date,
            "twse_row_count": int(len(external)),
        }

    db_latest = prices_df[prices_df["date"] == latest].copy()
    db_latest["ticker_id"] = db_latest["ticker_id"].astype(str)
    db_latest = db_latest.set_index("ticker_id")
    external = external.set_index("ticker_id")
    known_ids = set(tickers_df["ticker_id"].astype(str))
    external_known = external.loc[external.index.intersection(known_ids)]

    common = sorted(set(db_latest.index) & set(external_known.index))
    missing_in_db = sorted(set(external_known.index) - set(db_latest.index))
    missing_in_twse = sorted(set(db_latest.index) - set(external_known.index))
    known_without_latest_not_in_twse = sorted(known_ids - set(db_latest.index) - set(external_known.index))
    external_out_of_scope = sorted(set(external.index) - known_ids)
    issues: list[dict[str, Any]] = []

    for ticker_id in common:
        db_row = db_latest.loc[ticker_id]
        ex_row = external_known.loc[ticker_id]
        if isinstance(db_row, pd.DataFrame):
            db_row = db_row.iloc[0]
        if isinstance(ex_row, pd.DataFrame):
            ex_row = ex_row.iloc[0]

        close = _num_or_none(ex_row.get("close"))
        change = _num_or_none(ex_row.get("spread"))
        expected_change_pct = None
        if close is not None and change is not None:
            prev_close = close - change
            if prev_close > 0:
                expected_change_pct = round(change / prev_close * 100, 2)

        expected = {
            "open": _num_or_none(ex_row.get("open")),
            "high": _num_or_none(ex_row.get("high")),
            "low": _num_or_none(ex_row.get("low")),
            "close": close,
            "volume": _num_or_none(ex_row.get("volume")),
            "change_percent": expected_change_pct,
            "turnover": round(close * float(ex_row.get("volume")), 0)
            if close is not None and not _is_missing(ex_row.get("volume"))
            else None,
            "lower_shadow": None,
        }
        if expected["open"] is not None and expected["low"] is not None and expected["close"] is not None:
            expected["lower_shadow"] = round(max(0.0, min(expected["open"], expected["close"]) - expected["low"]), 4)

        for field in EXTERNAL_FIELDS:
            actual = db_row.get(field)
            exp = expected.get(field)
            if not _matches(actual, exp, TOLERANCES[field]):
                issues.append(_issue("twse_mismatch", ticker_id, field, actual, exp, {"date": str(latest)}))

    status = "pass"
    if str(latest) != external_date or issues or missing_in_db:
        status = "fail"

    return {
        "status": status,
        "db_latest_date": str(latest),
        "twse_date": external_date,
        "common_count": int(len(common)),
        "missing_in_db_count": int(len(missing_in_db)),
        "missing_in_db_sample": missing_in_db[:sample_limit],
        "missing_in_twse_count": int(len(missing_in_twse)),
        "missing_in_twse_sample": missing_in_twse[:sample_limit],
        "known_without_latest_not_in_twse_count": int(len(known_without_latest_not_in_twse)),
        "known_without_latest_not_in_twse_sample": known_without_latest_not_in_twse[:sample_limit],
        "external_out_of_scope_count": int(len(external_out_of_scope)),
        "external_out_of_scope_sample": external_out_of_scope[:sample_limit],
        "mismatch_count": int(len(issues)),
        "mismatch_sample": issues[:sample_limit],
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-twse", action="store_true", help="Compare DB latest rows to TWSE STOCK_DAY_ALL.")
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--json", type=Path, default=None, help="Write full JSON report to this path.")
    args = parser.parse_args()

    tickers_df, prices_df = await _load_db_frames()
    report: dict[str, Any] = {
        "database": {
            "tickers": int(len(tickers_df)),
            "daily_prices": int(len(prices_df)),
        },
        "latest_indicators": _validate_latest_indicators(tickers_df, prices_df, args.sample_limit),
    }

    if args.external_twse:
        report["twse_external"] = await _validate_twse_external(tickers_df, prices_df, args.sample_limit)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sections = [report["latest_indicators"]["status"]]
    if "twse_external" in report:
        sections.append(report["twse_external"]["status"])
    return 0 if all(status == "pass" for status in sections) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
