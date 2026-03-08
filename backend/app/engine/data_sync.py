"""
Data Sync — 從 Legacy data_fetcher 同步資料到 v1 表 (Ticker, DailyPrice, DailyChip)
包含延伸指標計算：avg_volume_20, avg_turnover_20, lower_shadow,
lowest_lower_shadow_20, 週MA, market_ok
"""
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
        prev_close = close - change if change is not None and close else None
        if prev_close and prev_close > 0 and change is not None:
            change_pct = round(change / prev_close * 100, 2)

        # 計算成交值 = 收盤 × 成交量 (股)
        turnover = round(close * volume, 0) if close and volume else None

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

    # 補算技術指標 (MA5/10/20/60, RSI14, avg_volume_20, avg_turnover_20,
    #               lowest_lower_shadow_20, 週MA, market_ok)
    await _backfill_indicators(db, date_obj)

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


async def _backfill_indicators(db: AsyncSession, target_date) -> None:
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
    """
    import pandas as pd
    from sqlalchemy import update, and_

    # 找出當天缺少 MA 或延伸指標的所有 ticker_ids
    missing_result = await db.execute(
        select(DailyPrice.ticker_id).where(
            DailyPrice.date == target_date,
            DailyPrice.ma5.is_(None),
        )
    )
    missing_tickers = [r[0] for r in missing_result.fetchall()]

    # 另外找出 ma5 已存在但延伸指標缺失的股票
    extended_missing_result = await db.execute(
        select(DailyPrice.ticker_id).where(
            DailyPrice.date == target_date,
            DailyPrice.ma5.is_not(None),
            DailyPrice.avg_volume_20.is_(None),
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
        return

    logger.info(f"Backfilling indicators for {len(all_missing)} tickers on {target_date}...")

    # 批次載入 v1 DB 歷史資料（需要至少 60 週 = ~300 天的歷史）
    lookback_date = target_date - timedelta(days=450)

    hist_result = await db.execute(
        select(
            DailyPrice.ticker_id,
            DailyPrice.date,
            DailyPrice.open,
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

    # 找出 DB 歷史不足 5 天的股票（需要 fallback）
    need_fallback = [t for t in all_missing if db_day_counts.get(t, 0) < 5]

    # === Fallback: 用 Legacy data_fetcher 抓歷史資料 ===
    fallback_data: dict[str, pd.DataFrame] = {}
    if need_fallback:
        try:
            start_str = (target_date - timedelta(days=450)).strftime("%Y-%m-%d")
            end_str = target_date.strftime("%Y-%m-%d")
            batch = need_fallback[:200]
            for ticker_id in batch:
                try:
                    hist_df = await data_fetcher.get_historical_data(ticker_id, start_str, end_str)
                    if hist_df.empty:
                        continue

                    # 統一欄位名 (FinMind / Yahoo / TWSE 格式不同)
                    col_map = {}
                    for src, dst in [
                        ("Close", "close"), ("Open", "open"), ("Low", "low"),
                        ("Volume", "volume"), ("Date", "date"),
                        ("ClosingPrice", "close"), ("OpeningPrice", "open"),
                        ("LowestPrice", "low"), ("Trading_Volume", "volume"),
                        ("stock_id", "ticker_id"),
                    ]:
                        if src in hist_df.columns and dst not in hist_df.columns:
                            col_map[src] = dst
                    if col_map:
                        hist_df = hist_df.rename(columns=col_map)

                    if "date" in hist_df.columns:
                        hist_df["date"] = pd.to_datetime(hist_df["date"]).dt.date

                    needed_cols = ["close"]
                    if all(c in hist_df.columns for c in needed_cols):
                        fallback_data[ticker_id] = hist_df.sort_values("date").reset_index(drop=True)
                except Exception:
                    continue
            if fallback_data:
                logger.info(f"Fallback: got history for {len(fallback_data)}/{len(batch)} tickers from Legacy API")
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

        # RSI14
        rsi14 = None
        if nc >= 15:
            delta = closes.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.rolling(14).mean().iloc[-1]
            avg_loss = loss.rolling(14).mean().iloc[-1]
            if avg_loss == 0:
                rsi14 = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi14 = round(float(100 - (100 / (1 + rs))), 2)

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

        # 回寫
        update_vals: dict = dict(
            ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60, rsi14=rsi14,
            avg_volume_20=avg_volume_20,
            avg_turnover_20=avg_turnover_20,
            wma10=wma10, wma20=wma20, wma60=wma60,
            market_ok=market_ok,
        )
        if lower_shadow_target is not None:
            update_vals["lower_shadow"] = lower_shadow_target
        if lowest_ls_20 is not None:
            update_vals["lowest_lower_shadow_20"] = lowest_ls_20

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

    # 套用大盤條件到剩餘已有指標的股票
    await _apply_market_ok(db, target_date)


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
