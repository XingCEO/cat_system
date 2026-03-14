"""
Chart API — K 線圖資料路由
GET /api/v1/chart/{ticker_id}/kline
"""
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from app.schemas.screen import KlineCandle, KlineResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# v1 DB 資料量低於此閾值時 fallback 到 Legacy data_fetcher
_MIN_ROWS_THRESHOLD = 20


@router.get(
    "/chart/{ticker_id}/kline",
    response_model=KlineResponse,
    summary="K 線歷史資料",
)
async def get_kline(
    ticker_id: str,
    period: str = Query("daily", description="週期: daily / weekly / monthly"),
    limit: int = Query(120, description="最大筆數"),
    db: AsyncSession = Depends(get_db),
):
    """取得股票 K 線歷史資料"""
    # 查詢股票名稱
    ticker_result = await db.execute(
        select(Ticker).where(Ticker.ticker_id == ticker_id)
    )
    ticker = ticker_result.scalar_one_or_none()
    name = ticker.name if ticker else ticker_id

    # 查詢日 K 資料
    query = (
        select(DailyPrice)
        .where(DailyPrice.ticker_id == ticker_id)
        .order_by(DailyPrice.date.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    # v1 DB 資料不足時 fallback 到 Legacy (Yahoo/TWSE)
    if len(rows) < _MIN_ROWS_THRESHOLD:
        # 月K 預設上限較小，避免抓取過多歷史
        effective_limit = min(limit, 24) if period == "monthly" else limit
        return await _fallback_legacy_kline(ticker_id, name, period, effective_limit)

    # 反轉為時間正序
    rows = list(reversed(rows))

    # 週/月 K 聚合
    if period == "weekly":
        candles, indicators = _aggregate_weekly(rows)
    elif period == "monthly":
        candles, indicators = _aggregate_monthly(rows)
    else:
        candles = [
            KlineCandle(
                date=str(r.date),
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
            )
            for r in rows
        ]
        indicators = {
            "ma5": [r.ma5 for r in rows],
            "ma10": [r.ma10 for r in rows],
            "ma20": [r.ma20 for r in rows],
            "ma60": [r.ma60 for r in rows],
            "rsi14": [r.rsi14 for r in rows],
        }

    return KlineResponse(
        ticker_id=ticker_id,
        name=name,
        period=period,
        candles=candles,
        indicators=indicators,
    )


async def _fallback_legacy_kline(
    ticker_id: str, name: str, period: str, limit: int
) -> KlineResponse:
    """v1 DB 資料不足時，使用 Legacy data_fetcher 取得完整歷史 K 線"""
    from datetime import datetime, timedelta
    from services.data_fetcher import data_fetcher
    import pandas as pd

    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    legacy_period = period_map.get(period, "day")

    # 計算需要的日期範圍
    fetch_days = limit + 150  # 額外資料供 MA60/MA120 計算
    if legacy_period == "week":
        fetch_days = limit * 7 + 150
    elif legacy_period == "month":
        fetch_days = limit * 30 + 150

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=fetch_days)).strftime("%Y-%m-%d")

    df = await data_fetcher.get_historical_data(ticker_id, start_date, end_date)

    if df.empty:
        raise HTTPException(
            status_code=404, detail=f"找不到 {ticker_id} 的 K 線資料"
        )

    # 準備欄位
    col_map = {"max": "high", "min": "low", "Trading_Volume": "volume"}
    df = df.rename(columns=col_map)
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.sort_values("date").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])

    # 週/月重新取樣
    if legacy_period == "week":
        df = _resample(df, "W")
    elif legacy_period == "month":
        df = _resample(df, "ME")

    # 計算指標
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi14"] = 100 - (100 / (1 + rs))

    # 取最後 limit 筆
    df = df.tail(limit)

    candles = [
        KlineCandle(
            date=str(row["date"])[:10],
            open=_safe_round(row.get("open")),
            high=_safe_round(row.get("high")),
            low=_safe_round(row.get("low")),
            close=_safe_round(row.get("close")),
            volume=int(row["volume"]) if pd.notna(row.get("volume")) else 0,
        )
        for _, row in df.iterrows()
    ]
    indicators = {
        "ma5": [_safe_round(v) for v in df["ma5"]],
        "ma10": [_safe_round(v) for v in df["ma10"]],
        "ma20": [_safe_round(v) for v in df["ma20"]],
        "ma60": [_safe_round(v) for v in df["ma60"]],
        "rsi14": [_safe_round(v) for v in df["rsi14"]],
    }

    return KlineResponse(
        ticker_id=ticker_id,
        name=name,
        period=period,
        candles=candles,
        indicators=indicators,
    )


def _resample(df, rule: str):
    """將日 K 重新取樣為週/月 K"""
    import pandas as pd

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    resampled = df.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    resampled = resampled.reset_index()
    resampled["date"] = resampled["date"].dt.strftime("%Y-%m-%d")
    return resampled


def _safe_round(val, decimals=2):
    """安全地四捨五入，處理 NaN/None"""
    import pandas as pd

    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val), decimals)


def _aggregate_weekly(rows) -> tuple:
    """將日 K 聚合為週 K"""
    weeks = {}
    for r in rows:
        # ISO 週數作為 key
        week_key = r.date.isocalendar()[:2]
        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(r)

    candles = []
    for week_key in sorted(weeks.keys()):
        group = weeks[week_key]
        candles.append(KlineCandle(
            date=str(group[0].date),
            open=group[0].open,
            high=max(r.high for r in group if r.high is not None) if any(r.high is not None for r in group) else None,
            low=min(r.low for r in group if r.low is not None) if any(r.low is not None for r in group) else None,
            close=group[-1].close,
            volume=sum(r.volume or 0 for r in group),
        ))
    # 取每週最後一天的指標值（代表本週終值）
    indicators = {
        "ma5": [g[-1].ma5 for g in [weeks[k] for k in sorted(weeks.keys())]],
        "ma10": [g[-1].ma10 for g in [weeks[k] for k in sorted(weeks.keys())]],
        "ma20": [g[-1].ma20 for g in [weeks[k] for k in sorted(weeks.keys())]],
        "ma60": [g[-1].ma60 for g in [weeks[k] for k in sorted(weeks.keys())]],
        "rsi14": [g[-1].rsi14 for g in [weeks[k] for k in sorted(weeks.keys())]],
    }
    return candles, indicators


def _aggregate_monthly(rows) -> tuple:
    """將日 K 聚合為月 K"""
    months = {}
    for r in rows:
        month_key = (r.date.year, r.date.month)
        if month_key not in months:
            months[month_key] = []
        months[month_key].append(r)

    candles = []
    for month_key in sorted(months.keys()):
        group = months[month_key]
        candles.append(KlineCandle(
            date=str(group[0].date),
            open=group[0].open,
            high=max(r.high for r in group if r.high is not None) if any(r.high is not None for r in group) else None,
            low=min(r.low for r in group if r.low is not None) if any(r.low is not None for r in group) else None,
            close=group[-1].close,
            volume=sum(r.volume or 0 for r in group),
        ))
    # 取每月最後一天的指標值（代表本月終值）
    indicators = {
        "ma5": [g[-1].ma5 for g in [months[k] for k in sorted(months.keys())]],
        "ma10": [g[-1].ma10 for g in [months[k] for k in sorted(months.keys())]],
        "ma20": [g[-1].ma20 for g in [months[k] for k in sorted(months.keys())]],
        "ma60": [g[-1].ma60 for g in [months[k] for k in sorted(months.keys())]],
        "rsi14": [g[-1].rsi14 for g in [months[k] for k in sorted(months.keys())]],
    }
    return candles, indicators
