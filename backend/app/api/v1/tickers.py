"""
Tickers API — 股票搜尋路由
GET /api/v1/tickers?q=關鍵字
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional

from database import get_db
from app.models.ticker import Ticker

logger = logging.getLogger(__name__)
router = APIRouter()


class TickerInfo(BaseModel):
    ticker_id: str
    name: str
    market_type: Optional[str] = None
    industry: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/tickers", response_model=list[TickerInfo], summary="股票搜尋")
async def search_tickers(
    q: str = Query("", description="搜尋關鍵字 (代號或名稱)"),
    limit: int = Query(20, description="最大筆數"),
    db: AsyncSession = Depends(get_db),
):
    """
    搜尋股票 — 支援代號或名稱模糊比對
    例: ?q=2330 或 ?q=台積
    """
    query = select(Ticker)

    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Ticker.ticker_id.like(pattern),
                Ticker.name.like(pattern),
            )
        )

    query = query.order_by(Ticker.ticker_id).limit(limit)
    result = await db.execute(query)
    tickers = result.scalars().all()

    return [TickerInfo.model_validate(t) for t in tickers]
