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

    if not rows:
        raise HTTPException(status_code=404, detail=f"找不到 {ticker_id} 的 K 線資料")

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


def _aggregate_weekly(rows) -> tuple:
    """將日 K 聚合為週 K"""
    from datetime import timedelta
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
    indicators = {}
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
    indicators = {}
    return candles, indicators
