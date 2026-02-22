"""
API v1 Router — 聚合所有 v1 子路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.screen import router as screen_router
from app.api.v1.chart import router as chart_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.tickers import router as tickers_router
from database import get_db

v1_router = APIRouter()

v1_router.include_router(screen_router, tags=["篩選"])
v1_router.include_router(chart_router, tags=["圖表"])
v1_router.include_router(strategies_router, tags=["策略"])
v1_router.include_router(tickers_router, tags=["股票"])


@v1_router.post("/sync", tags=["資料同步"])
async def sync_data(date: str = None, db: AsyncSession = Depends(get_db)):
    """手動觸發 v1 資料同步（股票基本資料 + 日K線）"""
    from app.engine.data_sync import sync_tickers, sync_daily_prices
    ticker_count = await sync_tickers(db)
    price_count = await sync_daily_prices(db, trade_date=date)
    return {
        "success": True,
        "synced_tickers": ticker_count,
        "synced_prices": price_count,
    }
