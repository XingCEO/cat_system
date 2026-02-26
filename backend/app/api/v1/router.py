"""
API v1 Router — 聚合所有 v1 子路由
"""
import time
from fastapi import APIRouter, Depends, HTTPException
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


# Rate limit state for sync endpoint
_sync_last = 0.0
_SYNC_COOLDOWN = 300  # 5 minutes


@v1_router.post("/sync", tags=["資料同步"])
async def sync_data(date: str = None, db: AsyncSession = Depends(get_db)):
    """手動觸發 v1 資料同步（股票基本資料 + 日K線）"""
    global _sync_last
    now = time.monotonic()
    if now - _sync_last < _SYNC_COOLDOWN:
        remaining = int(_SYNC_COOLDOWN - (now - _sync_last))
        raise HTTPException(status_code=429, detail=f"同步冷卻中，請等待 {remaining} 秒")
    _sync_last = now

    # 日期格式驗證
    if date is not None:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise HTTPException(status_code=400, detail="日期格式錯誤，請使用 YYYY-MM-DD")

    try:
        from app.engine.data_sync import sync_tickers, sync_daily_prices
        ticker_count = await sync_tickers(db)
        price_count = await sync_daily_prices(db, trade_date=date)
        return {
            "success": True,
            "synced_tickers": ticker_count,
            "synced_prices": price_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="資料同步失敗，請稍後再試")
