"""
API v1 Router — 聚合所有 v1 子路由
"""
from fastapi import APIRouter

from app.api.v1.screen import router as screen_router
from app.api.v1.chart import router as chart_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.tickers import router as tickers_router

v1_router = APIRouter()

v1_router.include_router(screen_router, tags=["篩選"])
v1_router.include_router(chart_router, tags=["圖表"])
v1_router.include_router(strategies_router, tags=["策略"])
v1_router.include_router(tickers_router, tags=["股票"])
