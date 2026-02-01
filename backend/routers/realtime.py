"""
盤中即時報價 API 路由
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from services.realtime_quotes import realtime_quotes_service

router = APIRouter(prefix="/realtime", tags=["即時報價"])


@router.get("/quotes")
async def get_realtime_quotes(
    symbols: str = Query(..., description="股票代號，逗號分隔，例如: 2330,2317,2454"),
    force_refresh: bool = Query(False, description="是否強制刷新（忽略快取）"),
):
    """
    取得多檔即時報價

    - 資料來源：證交所 MIS（主）、Yahoo Finance（備援）
    - 快取時間：30 秒
    - 延遲：約 10-30 秒（證交所本身延遲）
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="請提供至少一個股票代號")

    if len(symbol_list) > 200:
        raise HTTPException(status_code=400, detail="一次最多查詢 200 檔")

    result = await realtime_quotes_service.get_quotes(symbol_list, force_refresh=force_refresh)
    return result


@router.get("/top-turnover")
async def get_top_turnover_realtime(
    limit: int = Query(50, ge=1, le=200, description="取前 N 名"),
):
    """
    取得週轉率前 N 名的即時報價

    結合週轉率排名資料 + 盤中即時報價
    """
    result = await realtime_quotes_service.get_top_turnover_realtime(limit=limit)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/status")
async def get_service_status():
    """
    取得即時報價服務狀態

    包含快取狀態、資料來源健康度、統計資訊
    """
    return realtime_quotes_service.get_status()


@router.post("/clear-cache")
async def clear_cache():
    """
    清除即時報價快取
    """
    realtime_quotes_service.clear_cache()
    return {"success": True, "message": "快取已清除"}


@router.post("/reset-sources")
async def reset_sources():
    """
    重置資料來源狀態

    當資料來源被標記為不健康時，可用此 API 重置
    """
    realtime_quotes_service.reset_sources()
    return {"success": True, "message": "資料來源狀態已重置"}
