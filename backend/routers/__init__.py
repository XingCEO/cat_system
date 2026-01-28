"""Routers package"""
from routers.stocks import router as stocks_router
from routers.analysis import router as analysis_router
from routers.backtest import router as backtest_router
from routers.watchlist import router as watchlist_router
from routers.history import router as history_router
from routers.export import router as export_router
from routers.turnover import router as turnover_router

__all__ = [
    "stocks_router",
    "analysis_router",
    "backtest_router",
    "watchlist_router",
    "history_router",
    "export_router",
    "turnover_router"
]

