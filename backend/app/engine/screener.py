"""
Screener — 多維度篩選引擎
核心邏輯：從 DB 載入資料 → 套用自訂公式 → 逐條 Rule 產生 mask → AND/OR 合併 → 回傳結果
"""
import logging
import pandas as pd
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from app.models.daily_chip import DailyChip
from app.schemas.screen import ScreenRequest, TickerResult, ScreenResponse
from app.engine.formula_parser import safe_eval_formula
from app.engine.operators import OPERATOR_MAP, CROSS_OPERATORS

logger = logging.getLogger(__name__)


async def load_latest_data(db: AsyncSession) -> pd.DataFrame:
    """
    從 DB 載入最新一天的完整資料 (JOIN tickers + daily_prices + daily_chips)
    回傳 Pandas DataFrame
    """
    # 找最新日期
    latest_date_result = await db.execute(
        select(func.max(DailyPrice.date))
    )
    latest_date = latest_date_result.scalar()
    if latest_date is None:
        return pd.DataFrame()

    # 載入當天所有股票的價格資料
    price_query = (
        select(
            DailyPrice.ticker_id,
            DailyPrice.date,
            DailyPrice.open,
            DailyPrice.high,
            DailyPrice.low,
            DailyPrice.close,
            DailyPrice.volume,
            DailyPrice.ma5,
            DailyPrice.ma10,
            DailyPrice.ma20,
            DailyPrice.ma60,
            DailyPrice.rsi14,
            DailyPrice.pe_ratio,
            DailyPrice.eps,
            DailyPrice.change_percent,
        )
        .where(DailyPrice.date == latest_date)
    )
    price_result = await db.execute(price_query)
    price_rows = price_result.fetchall()

    if not price_rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r._mapping) for r in price_rows])

    # 載入股票基本資料
    ticker_query = select(Ticker.ticker_id, Ticker.name, Ticker.market_type, Ticker.industry)
    ticker_result = await db.execute(ticker_query)
    ticker_rows = ticker_result.fetchall()

    if ticker_rows:
        ticker_df = pd.DataFrame([dict(r._mapping) for r in ticker_rows])
        df = df.merge(ticker_df, on="ticker_id", how="left")

    # 載入籌碼資料
    chip_query = (
        select(
            DailyChip.ticker_id,
            DailyChip.foreign_buy,
            DailyChip.trust_buy,
            DailyChip.margin_balance,
        )
        .where(DailyChip.date == latest_date)
    )
    chip_result = await db.execute(chip_query)
    chip_rows = chip_result.fetchall()

    if chip_rows:
        chip_df = pd.DataFrame([dict(r._mapping) for r in chip_rows])
        df = df.merge(chip_df, on="ticker_id", how="left")

    return df


async def load_multi_day_data(db: AsyncSession, days: int = 2) -> pd.DataFrame:
    """
    載入多天資料 (供 CROSS_UP/CROSS_DOWN 使用)
    """
    price_query = (
        select(
            DailyPrice.ticker_id,
            DailyPrice.date,
            DailyPrice.open,
            DailyPrice.high,
            DailyPrice.low,
            DailyPrice.close,
            DailyPrice.volume,
            DailyPrice.ma5,
            DailyPrice.ma10,
            DailyPrice.ma20,
            DailyPrice.ma60,
            DailyPrice.rsi14,
            DailyPrice.pe_ratio,
            DailyPrice.eps,
            DailyPrice.change_percent,
        )
        .order_by(DailyPrice.date.desc())
        .limit(days * 2000)  # 假設最多 2000 支股票
    )
    result = await db.execute(price_query)
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "ticker_id", "date", "open", "high", "low", "close", "volume",
        "ma5", "ma10", "ma20", "ma60", "rsi14", "pe_ratio", "eps",
        "change_percent",
    ])

    # 載入股票基本資料
    ticker_query = select(Ticker.ticker_id, Ticker.name, Ticker.market_type, Ticker.industry)
    ticker_result = await db.execute(ticker_query)
    ticker_rows = ticker_result.fetchall()

    if ticker_rows:
        ticker_df = pd.DataFrame(ticker_rows, columns=["ticker_id", "name", "market_type", "industry"])
        df = df.merge(ticker_df, on="ticker_id", how="left")

    # 載入籌碼資料 (最新日期)
    latest_date = df["date"].max()
    chip_query = (
        select(
            DailyChip.ticker_id,
            DailyChip.foreign_buy,
            DailyChip.trust_buy,
            DailyChip.margin_balance,
        )
        .where(DailyChip.date == latest_date)
    )
    chip_result = await db.execute(chip_query)
    chip_rows = chip_result.fetchall()

    if chip_rows:
        chip_df = pd.DataFrame(chip_rows, columns=["ticker_id", "foreign_buy", "trust_buy", "margin_balance"])
        df = df.merge(chip_df, on="ticker_id", how="left")

    df = df.sort_values(["ticker_id", "date"]).reset_index(drop=True)
    return df


def apply_rule(df: pd.DataFrame, rule_dict: dict) -> pd.Series:
    """
    套用單條規則，回傳 boolean mask

    Args:
        df: 資料 DataFrame
        rule_dict: Rule 字典 {field, operator, target_type, target_value}

    Returns:
        pd.Series[bool]
    """
    field = rule_dict["field"]
    operator = rule_dict["operator"]
    target_type = rule_dict.get("target_type", "value")
    target_value = rule_dict["target_value"]

    if field not in df.columns:
        logger.warning(f"欄位 '{field}' 不存在，跳過此規則")
        return pd.Series(True, index=df.index)

    # 處理 CROSS_UP / CROSS_DOWN
    if operator in CROSS_OPERATORS:
        cross_fn = CROSS_OPERATORS[operator]
        if target_type == "field":
            return cross_fn(df, field, str(target_value))
        else:
            return cross_fn(df, field, float(target_value))

    # 一般比較運算子
    compare_fn = OPERATOR_MAP.get(operator)
    if compare_fn is None:
        logger.warning(f"不支援的運算子 '{operator}'，跳過此規則")
        return pd.Series(True, index=df.index)

    series_a = df[field]
    if target_type == "field":
        target_col = str(target_value)
        if target_col not in df.columns:
            logger.warning(f"目標欄位 '{target_col}' 不存在，跳過此規則")
            return pd.Series(True, index=df.index)
        target = df[target_col]
    else:
        target = float(target_value)

    return compare_fn(series_a, target).fillna(False)


async def run_screen(request: ScreenRequest, db: AsyncSession) -> ScreenResponse:
    """
    執行篩選

    Args:
        request: ScreenRequest
        db: AsyncSession

    Returns:
        ScreenResponse
    """
    # 判斷是否需要多天資料 (CROSS 運算子)
    needs_multi_day = any(
        r.operator in ("CROSS_UP", "CROSS_DOWN") for r in request.rules
    )

    if needs_multi_day:
        df = await load_multi_day_data(db, days=2)
    else:
        df = await load_latest_data(db)

    if df.empty:
        return ScreenResponse(matched_count=0, data=[], logic=request.logic)

    # 套用自訂公式
    for formula in request.custom_formulas:
        try:
            df = safe_eval_formula(df, formula.name, formula.formula)
        except ValueError as e:
            logger.error(f"自訂公式錯誤: {e}")
            continue

    # 如果是多天資料，只保留最新日期的記錄作為結果
    if needs_multi_day:
        latest_date = df["date"].max()

    # 套用所有規則
    masks = []
    for rule in request.rules:
        mask = apply_rule(df, rule.model_dump())
        masks.append(mask)

    # 合併 masks
    if masks:
        if request.logic == "AND":
            combined = masks[0]
            for m in masks[1:]:
                combined = combined & m
        else:  # OR
            combined = masks[0]
            for m in masks[1:]:
                combined = combined | m
    else:
        combined = pd.Series(True, index=df.index)

    # 如果是多天資料，只取最新日期的結果
    if needs_multi_day:
        combined = combined & (df["date"] == latest_date)

    filtered = df[combined]

    # 去重 (每支股票只出現一次)
    filtered = filtered.drop_duplicates(subset=["ticker_id"], keep="last")

    # 構建結果
    results = []
    for _, row in filtered.iterrows():
        results.append(TickerResult(
            ticker_id=str(row.get("ticker_id", "")),
            name=str(row.get("name", "")),
            market_type=row.get("market_type"),
            industry=row.get("industry"),
            close=_safe_float(row.get("close")),
            change_percent=_safe_float(row.get("change_percent")),
            volume=_safe_int(row.get("volume")),
            ma5=_safe_float(row.get("ma5")),
            ma10=_safe_float(row.get("ma10")),
            ma20=_safe_float(row.get("ma20")),
            ma60=_safe_float(row.get("ma60")),
            rsi14=_safe_float(row.get("rsi14")),
            pe_ratio=_safe_float(row.get("pe_ratio")),
            eps=_safe_float(row.get("eps")),
            foreign_buy=_safe_int(row.get("foreign_buy")),
            trust_buy=_safe_int(row.get("trust_buy")),
            margin_balance=_safe_int(row.get("margin_balance")),
        ))

    return ScreenResponse(
        matched_count=len(results),
        data=results,
        logic=request.logic,
    )


def _safe_float(val) -> Optional[float]:
    """安全轉換為 float"""
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """安全轉換為 int"""
    if val is None or pd.isna(val):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
