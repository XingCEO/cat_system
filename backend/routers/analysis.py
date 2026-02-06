"""
Analysis Router - Technical analysis API endpoints
支援 5 年歷史 K 線資料
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Literal
from datetime import date, timedelta

from schemas.common import APIResponse
from services.technical_analysis import technical_analyzer
from services.data_fetcher import data_fetcher
from utils.validators import validate_symbol
from utils.date_utils import get_taiwan_today
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/stocks/{symbol}/indicators")
async def get_stock_indicators(
    symbol: str,
    days: int = Query(200, ge=30, le=500, description="歷史天數")
):
    """
    取得股票技術指標
    
    包含：
    - 移動平均線 (MA5, MA10, MA20, MA60)
    - RSI(14)
    - MACD
    - KD 指標
    - 布林通道
    """
    valid, error = validate_symbol(symbol)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        result = await technical_analyzer.get_indicators(symbol, days)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return APIResponse.ok(data=result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/kline")
async def get_kline_data(
    symbol: str,
    period: Literal["day", "week", "month"] = Query("day", description="週期：day(日K)/week(週K)/month(月K)"),
    years: int = Query(5, ge=1, le=5, description="歷史年數（1-5 年，預設 5 年）"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（不指定則自動計算）"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD（預設今天）"),
    force_refresh: bool = Query(False, description="強制刷新，忽略快取")
):
    """
    取得 K 線圖資料與技術指標（支援 5 年歷史資料）
    
    回傳包含：
    - K 線資料（OHLCV）
    - 移動平均線（MA5, MA10, MA20, MA60, MA120）
    - MACD 指標
    - KD 指標
    - RSI 指標
    - 布林通道
    - 成交量均線
    
    可選週期：
    - day: 日K線
    - week: 週K線  
    - month: 月K線
    
    日期範圍：
    - 支援最多 5 年歷史資料
    - 預設載入完整 5 年（約 1,250 筆日 K 資料）
    
    參數：
    - years: 歷史年數（1-5 年，新增參數）
    - start_date: 起始日期（不指定則自動計算）
    - end_date: 結束日期（預設今天）
    - force_refresh: 強制刷新忽略快取
    """
    valid, error = validate_symbol(symbol)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        from services.enhanced_kline_service import enhanced_kline_service
        
        # 計算日期範圍
        today = get_taiwan_today()
        
        # 若未指定 end_date，使用今天
        if not end_date:
            end_date = today.strftime("%Y-%m-%d")
        
        # 若未指定 start_date，根據 years 計算
        if not start_date:
            start_dt = today - timedelta(days=years * 365)
            start_date = start_dt.strftime("%Y-%m-%d")
        
        logger.info(f"K線請求: {symbol} {start_date} ~ {end_date} ({period})")
        
        if force_refresh:
            # 清除快取
            from services.cache_manager import cache_manager
            cache_key = f"kline_extended_{symbol}_{period}"
            cache_manager.delete(cache_key, "indicator")
            # 清除資料庫快取
            await _clear_db_cache(symbol)
            logger.info(f"Force refresh: cleared all cache for {symbol}")
        
        result = await enhanced_kline_service.get_kline_data_extended(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        result["force_refreshed"] = force_refresh
        result["requested_years"] = years
        
        return APIResponse.ok(data=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"K線資料取得失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _clear_db_cache(symbol: str) -> None:
    """清除資料庫中的 K 線快取"""
    try:
        from database import async_session_maker
        from models.kline_cache import KLineCache
        from sqlalchemy import delete
        
        async with async_session_maker() as session:
            stmt = delete(KLineCache).where(KLineCache.symbol == symbol)
            await session.execute(stmt)
            await session.commit()
            logger.info(f"已清除 {symbol} 的資料庫快取")
    except Exception as e:
        logger.warning(f"清除資料庫快取失敗: {e}")


@router.delete("/stocks/{symbol}/kline/cache")
async def clear_kline_cache(symbol: str):
    """
    清除指定股票的 K 線快取
    
    用於強制重新抓取資料
    """
    valid, error = validate_symbol(symbol)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        from services.cache_manager import cache_manager
        
        # 清除記憶體快取
        for period in ["day", "week", "month"]:
            cache_key = f"kline_extended_{symbol}_{period}"
            cache_manager.delete(cache_key, "indicator")
        
        # 清除資料庫快取
        await _clear_db_cache(symbol)
        
        return APIResponse.ok(data={"message": f"已清除 {symbol} 的所有快取"})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries")
async def get_industries():
    """
    取得所有產業類別列表
    """
    try:
        industries = await data_fetcher.get_industries()
        return APIResponse.ok(data=industries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-date")
async def get_trading_date():
    """
    取得最近交易日
    """
    try:
        from utils.date_utils import get_previous_trading_day, format_date, is_trading_day
        from datetime import date
        
        today = get_taiwan_today()
        latest = get_previous_trading_day(today)
        
        return APIResponse.ok(data={
            "today": format_date(today),
            "latest_trading_day": format_date(latest),
            "is_today_trading": is_trading_day(today)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
