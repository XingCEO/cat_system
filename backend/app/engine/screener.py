"""
Screener — 多維度篩選引擎
核心邏輯：從 DB 載入資料 → 套用自訂公式 → 逐條 Rule 產生 mask → AND/OR 合併 → 回傳結果
"""
import asyncio
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

# 從 DailyPrice 載入的所有欄位（含延伸指標）
_DAILY_PRICE_COLS = [
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
    # 延伸指標
    DailyPrice.turnover,
    DailyPrice.avg_volume_20,
    DailyPrice.avg_turnover_20,
    DailyPrice.lower_shadow,
    DailyPrice.lowest_lower_shadow_20,
    DailyPrice.ma20_curr_month_low,
    DailyPrice.ma20_prev_month_low,
    DailyPrice.wma10,
    DailyPrice.wma20,
    DailyPrice.wma60,
    DailyPrice.market_ok,
    DailyPrice.ma_bull_pullback_low_high_1_3,
    DailyPrice.ma_bull_pullback_low_high_2_3,
    DailyPrice.ma_bull_pullback_breakout_1_3,
    DailyPrice.ma_bull_pullback_breakout_2_3,
]


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

    # 載入當天所有股票的價格資料（含延伸指標）
    price_query = (
        select(*_DAILY_PRICE_COLS)
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
    # 先查詢最近 N 個交易日的日期，再以日期範圍過濾，避免 row-count cap 截斷當日資料
    dates_result = await db.execute(
        select(DailyPrice.date)
        .distinct()
        .order_by(DailyPrice.date.desc())
        .limit(days)
    )
    recent_dates = [row[0] for row in dates_result.fetchall()]
    if not recent_dates:
        return pd.DataFrame()
    min_date = min(recent_dates)

    price_query = (
        select(*_DAILY_PRICE_COLS)
        .where(DailyPrice.date >= min_date)
        .order_by(DailyPrice.date.desc())
    )
    result = await db.execute(price_query)
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r._mapping) for r in rows])

    # 載入股票基本資料
    ticker_query = select(Ticker.ticker_id, Ticker.name, Ticker.market_type, Ticker.industry)
    ticker_result = await db.execute(ticker_query)
    ticker_rows = ticker_result.fetchall()

    if ticker_rows:
        ticker_df = pd.DataFrame([dict(r._mapping) for r in ticker_rows])
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
        chip_df = pd.DataFrame([dict(r._mapping) for r in chip_rows])
        df = df.merge(chip_df, on="ticker_id", how="left")

    df = df.sort_values(["ticker_id", "date"]).reset_index(drop=True)
    return df


def apply_rule(df: pd.DataFrame, rule_dict: dict, warnings: Optional[list] = None) -> pd.Series:
    """
    套用單條規則，回傳 boolean mask

    Args:
        df: 資料 DataFrame
        rule_dict: Rule 字典 {field, operator, target_type, target_value}
        warnings: 選填，收集非致命警告（欄位缺失/無資料/target 非數值）供回傳前端

    Returns:
        pd.Series[bool]
    """
    field = rule_dict["field"]
    operator = rule_dict["operator"]
    target_type = rule_dict.get("target_type", "value")
    target_value = rule_dict["target_value"]

    def _warn(msg: str) -> None:
        logger.error(msg)
        if warnings is not None:
            warnings.append(msg)

    if field not in df.columns:
        _warn(f"篩選規則錯誤：欄位 '{field}' 不存在，此規則將讓所有股票不通過")
        return pd.Series(False, index=df.index)

    # 數值型 target_value 轉 float；非數值字串（誤用 target_type=value）不應讓整個
    # 篩選失效，改記錄並讓此規則不通過任何股票。
    def _coerce_target() -> Optional[float]:
        try:
            return float(target_value)
        except (ValueError, TypeError):
            _warn(
                f"篩選規則錯誤：target_value '{target_value}' 非數值（operator={operator}），此規則將讓所有股票不通過"
            )
            return None

    # 處理 CROSS_UP / CROSS_DOWN
    if operator in CROSS_OPERATORS:
        cross_fn = CROSS_OPERATORS[operator]
        if target_type == "field":
            return cross_fn(df, field, str(target_value))
        else:
            tv = _coerce_target()
            if tv is None:
                return pd.Series(False, index=df.index)
            return cross_fn(df, field, tv)

    # 一般比較運算子
    compare_fn = OPERATOR_MAP.get(operator)
    if compare_fn is None:
        _warn(f"篩選規則錯誤：不支援的運算子 '{operator}'，此規則將讓所有股票不通過")
        return pd.Series(False, index=df.index)

    # 數值欄位強制轉型，避免 object/字串 dtype 造成字典序比較（"9" > "100"）。
    # 非數值值 → NaN → fillna(False) 排除，符合「無法評估即不通過」語意。
    series_a = pd.to_numeric(df[field], errors="coerce")
    if series_a.notna().sum() == 0:
        _warn(f"篩選提示：欄位 '{field}' 全部無資料（可能尚未同步），此規則排除所有股票")

    if target_type == "field":
        target_col = str(target_value)
        if target_col not in df.columns:
            _warn(f"篩選規則錯誤：目標欄位 '{target_col}' 不存在，此規則將讓所有股票不通過")
            return pd.Series(False, index=df.index)
        target = pd.to_numeric(df[target_col], errors="coerce")
    else:
        target = _coerce_target()
        if target is None:
            return pd.Series(False, index=df.index)

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
    # 自動補資料：若 v1 DB 落後最新交易日就同步（冷卻保護 + 失敗不影響篩選）。
    # 修復「無最新資料」——不依賴交易時段或伺服器是否持續運行，使用者一打開就自癒。
    try:
        from app.engine.data_sync import ensure_fresh_data
        await ensure_fresh_data(db)
    except Exception as e:
        logger.warning(f"ensure_fresh_data skipped: {e}")

    # 判斷是否需要多天資料 (CROSS 運算子)
    needs_multi_day = any(
        r.operator in ("CROSS_UP", "CROSS_DOWN") for r in request.rules
    )

    if needs_multi_day:
        df = await load_multi_day_data(db, days=2)
    else:
        df = await load_latest_data(db)

    if df.empty:
        return _attach_staleness(ScreenResponse(matched_count=0, data=[], logic=request.logic), None)

    # 將 CPU-bound 的 DataFrame 運算移至 thread pool，避免阻塞 event loop
    result = await asyncio.to_thread(
        _compute_screen_sync, df, request, needs_multi_day
    )
    # 標示篩選所依據的資料日期 (官方收盤日)，供前端區分盤中即時與收盤資料
    data_date = None
    if "date" in df.columns and not df["date"].dropna().empty:
        data_date = str(df["date"].max())
    return _attach_staleness(result, data_date)


def _attach_staleness(result: ScreenResponse, data_date: Optional[str]) -> ScreenResponse:
    """填入 data_date / latest_trading_day / data_age_days / is_stale，供前端標示資料新鮮度。"""
    from datetime import datetime
    from utils.date_utils import get_latest_trading_day

    result.data_date = data_date
    latest = get_latest_trading_day()
    result.latest_trading_day = latest
    if data_date:
        try:
            d0 = datetime.strptime(data_date[:10], "%Y-%m-%d").date()
            d1 = datetime.strptime(latest, "%Y-%m-%d").date()
            age = (d1 - d0).days
            result.data_age_days = age
            result.is_stale = age > 1
        except (ValueError, TypeError):
            pass
    else:
        # 完全沒有資料也算過期，讓前端顯示「資料尚未就緒」而非單純「查無符合」
        result.is_stale = True
    return result


def _compute_screen_sync(
    df: pd.DataFrame, request: ScreenRequest, needs_multi_day: bool
) -> ScreenResponse:
    """純 CPU 運算的同步函式（在 thread pool 中執行）"""
    warnings: list[str] = []
    # 套用自訂公式
    for formula in request.custom_formulas:
        try:
            df = safe_eval_formula(df, formula.name, formula.formula)
        except ValueError as e:
            logger.error(f"自訂公式錯誤: {e}")
            warnings.append(f"自訂公式 '{formula.name}' 錯誤：{e}")
            continue

    # 套用所有規則
    masks = []
    for rule in request.rules:
        mask = apply_rule(df, rule.model_dump(), warnings=warnings)
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
        latest_date = df["date"].max()
        combined = combined & (df["date"] == latest_date)

    filtered = df[combined]

    # 去重 (每支股票只出現一次)
    filtered = filtered.drop_duplicates(subset=["ticker_id"], keep="last")

    # 構建結果
    results = []
    for _, row in filtered.iterrows():
        # 安全取得字串欄位，處理 NaN
        ticker_id = row.get("ticker_id", "")
        ticker_id = str(ticker_id) if pd.notna(ticker_id) else ""
        name = row.get("name", "")
        name = str(name) if pd.notna(name) else ticker_id
        market_type = row.get("market_type")
        market_type = str(market_type) if pd.notna(market_type) else None
        industry = row.get("industry")
        industry = str(industry) if pd.notna(industry) else None

        results.append(TickerResult(
            ticker_id=ticker_id,
            name=name,
            market_type=market_type,
            industry=industry,
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
            # 延伸指標
            turnover=_safe_float(row.get("turnover")),
            avg_volume_20=_safe_float(row.get("avg_volume_20")),
            avg_turnover_20=_safe_float(row.get("avg_turnover_20")),
            lower_shadow=_safe_float(row.get("lower_shadow")),
            lowest_lower_shadow_20=_safe_float(row.get("lowest_lower_shadow_20")),
            ma20_curr_month_low=_safe_float(row.get("ma20_curr_month_low")),
            ma20_prev_month_low=_safe_float(row.get("ma20_prev_month_low")),
            wma10=_safe_float(row.get("wma10")),
            wma20=_safe_float(row.get("wma20")),
            wma60=_safe_float(row.get("wma60")),
            market_ok=_safe_bool(row.get("market_ok")),
            ma_bull_pullback_low_high_1_3=_safe_bool(row.get("ma_bull_pullback_low_high_1_3")),
            ma_bull_pullback_low_high_2_3=_safe_bool(row.get("ma_bull_pullback_low_high_2_3")),
            ma_bull_pullback_breakout_1_3=_safe_bool(row.get("ma_bull_pullback_breakout_1_3")),
            ma_bull_pullback_breakout_2_3=_safe_bool(row.get("ma_bull_pullback_breakout_2_3")),
        ))

    return ScreenResponse(
        matched_count=len(results),
        data=results,
        logic=request.logic,
        warnings=list(dict.fromkeys(warnings)),
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


def _safe_bool(val) -> Optional[bool]:
    """安全轉換為 bool，NaN/None → None"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return bool(val)
