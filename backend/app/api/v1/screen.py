"""
Screen API — 條件篩選路由
POST /api/v1/screen
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.schemas.screen import ScreenRequest, ScreenResponse
from app.engine.screener import run_screen

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/screen", response_model=ScreenResponse, summary="多維度條件篩選")
async def screen_stocks(
    request: ScreenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    根據條件組合篩選股票

    支援:
    - 技術面 (indicator): close, ma5, ma10, ma20, ma60, rsi14
    - 基本面 (fundamental): pe_ratio, eps
    - 籌碼面 (chip): foreign_buy, trust_buy, margin_balance
    - 運算子: >, <, =, >=, <=, CROSS_UP, CROSS_DOWN
    - 邏輯: AND / OR
    - 自訂公式: 白名單 token + pandas.eval()
    """
    try:
        result = await run_screen(request, db)
        return result
    except Exception as e:
        logger.error(f"篩選失敗: {e}", exc_info=True)
        return ScreenResponse(matched_count=0, data=[], logic=request.logic)
