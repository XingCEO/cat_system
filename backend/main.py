"""
喵喵選股 — 台股客製化選股系統 API
(TWSE Stock Filter API + 喵喵選股 v1 API)
"""
import os
import sys
import time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from config import get_settings
from database import init_db, close_db
from routers import (
    stocks_router, analysis_router, backtest_router,
    watchlist_router, history_router, export_router, turnover_router
)

# 新架構 v1 API
from app.api.v1.router import v1_router
import app.models  # 確保新的 ORM 模型被載入

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Find frontend directory - check multiple locations
FRONTEND_DIR = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()

logger.info(f"BASE_DIR: {BASE_DIR}")
logger.info(f"CWD: {CWD}")

FRONTEND_PATHS = [
    os.path.join(BASE_DIR, "static"),                       # Render: backend/static
    os.path.join(CWD, "static"),                            # Render: cwd/static
    os.path.join(CWD, "..", "frontend", "dist"),           # portable: from backend/, ../frontend/dist
    os.path.join(CWD, "frontend", "dist"),                  # if cwd is project root
    os.path.join(BASE_DIR, "..", "frontend", "dist"),       # dev: relative to main.py
]

for path in FRONTEND_PATHS:
    abs_path = os.path.abspath(path)
    index_file = os.path.join(abs_path, "index.html")
    logger.info(f"Checking: {abs_path} -> exists: {os.path.isfile(index_file)}")
    if os.path.isfile(index_file):
        FRONTEND_DIR = abs_path
        logger.info(f"✓ Frontend found: {FRONTEND_DIR}")
        break

if not FRONTEND_DIR:
    logger.warning("✗ Frontend not found - API only mode")
    # List what's in the directories for debugging
    logger.warning(f"Contents of BASE_DIR: {os.listdir(BASE_DIR) if os.path.isdir(BASE_DIR) else 'N/A'}")
    logger.warning(f"Contents of CWD: {os.listdir(CWD) if os.path.isdir(CWD) else 'N/A'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Meow Money Maker...")
    await init_db()
    logger.info("Database initialized")

    # 啟動時將資料預熱 + v1 資料同步移至背景任務，避免阻塞啟動流程
    import asyncio
    async def _background_sync():
        """Background task: pre-warm caches + sync v1 data without blocking startup"""
        try:
            await asyncio.sleep(1)  # 等待應用程式完全啟動

            # ===== Phase 1: 預熱 Legacy API 快取（讓首頁載入更快）=====
            from services.data_fetcher import data_fetcher
            logger.info("Pre-warming: fetching stock list...")
            stock_list = await data_fetcher.get_stock_list()
            logger.info(f"Pre-warming: {len(stock_list)} stocks loaded")

            trade_date = await data_fetcher.get_latest_trading_date()
            logger.info(f"Pre-warming: fetching daily data for {trade_date}...")
            daily_df = await data_fetcher.get_daily_data(trade_date)
            logger.info(f"Pre-warming: {len(daily_df)} daily records loaded")

            # ===== Phase 2: v1 DB 同步 =====
            from database import async_session_maker
            from app.engine.data_sync import sync_tickers, sync_daily_prices
            async with async_session_maker() as session:
                ticker_count = await sync_tickers(session)
                if ticker_count > 0:
                    logger.info(f"Background synced {ticker_count} tickers")
            # 單獨的 session 來同步 daily prices
            async with async_session_maker() as session:
                price_count = await sync_daily_prices(session)
                if price_count > 0:
                    logger.info(f"Background synced {price_count} daily prices")
                else:
                    logger.info("Daily prices already up to date (or no data available)")
        except Exception as e:
            logger.warning(f"Background sync error: {e}")

    async def _periodic_refresh():
        """定期刷新：盤中每 30 分鐘重新抓取最新資料（僅在台股交易時段）"""
        from utils.date_utils import is_trading_day, taiwan_now
        from services.cache_manager import cache_manager
        while True:
            await asyncio.sleep(1800)  # 30 分鐘
            try:
                now = taiwan_now()
                # 只在交易日 8:30-14:30 自動刷新
                if not is_trading_day(now.date()):
                    continue
                if now.hour < 8 or (now.hour == 8 and now.minute < 30) or now.hour > 14 or (now.hour == 14 and now.minute > 30):
                    continue

                logger.info("Periodic refresh: clearing daily cache, re-fetching...")
                cache_manager.clear("daily")
                cache_manager.delete("latest_trading_date", "general")
                cache_manager.delete("_daily_canonical_key", "general")

                from services.data_fetcher import data_fetcher
                trade_date = await data_fetcher.get_latest_trading_date()
                df = await data_fetcher.get_daily_data(trade_date)
                logger.info(f"Periodic refresh: {len(df)} records for {trade_date}")

                # 同步到 v1 DB
                from database import async_session_maker
                from app.engine.data_sync import sync_daily_prices
                async with async_session_maker() as session:
                    count = await sync_daily_prices(session, trade_date)
                    if count > 0:
                        logger.info(f"Periodic refresh: synced {count} daily prices to v1 DB")
            except Exception as e:
                logger.warning(f"Periodic refresh error: {e}")

    asyncio.create_task(_background_sync())
    asyncio.create_task(_periodic_refresh())
    logger.info("Background sync + periodic refresh scheduled")

    yield
    logger.info("Shutting down...")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="喵喵選股 API",
    version="2.0.0",
    description="台股客製化選股系統 — 支援多維度篩選、K 線圖表、策略管理",
    lifespan=lifespan
)

# Configure CORS
origins = settings.cors_origins.split(",")
# 在生產環境（非 localhost），如果未設定 CORS_ORIGINS，允許所有來源
if len(origins) == 1 and "localhost" in origins[0] and os.getenv("CORS_ORIGINS") is None:
    # 偵測到可能在雲端部署但未設定 CORS，改為寬鬆模式
    import socket
    try:
        hostname = socket.gethostname()
        if hostname != "localhost" and not hostname.startswith("DESKTOP"):
            origins = ["*"]
            logger.info("CORS: 雲端環境未設定 CORS_ORIGINS，已設為允許所有來源")
    except Exception:
        pass
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    if settings.debug:
        error_message = str(exc)
    else:
        error_message = "伺服器內部錯誤，請稍後再試"
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": error_message}
    )


# ============ API ROUTES (must be before static files) ============
# 原有 API 路由 (保留)
app.include_router(stocks_router)
app.include_router(analysis_router)
app.include_router(backtest_router)
app.include_router(watchlist_router)
app.include_router(history_router)
app.include_router(export_router)
app.include_router(turnover_router)

# 新架構 v1 API 路由
app.include_router(v1_router, prefix="/api/v1")


@app.get("/api/status")
async def api_status():
    return {"name": settings.app_name, "version": settings.app_version, "status": "running"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


# Rate limit state for cache/clear
_cache_clear_last = 0.0
_CACHE_CLEAR_COOLDOWN = 60  # seconds


@app.get("/api/cache/clear")
async def clear_cache(request: Request):
    global _cache_clear_last
    now = time.monotonic()
    if now - _cache_clear_last < _CACHE_CLEAR_COOLDOWN:
        remaining = int(_CACHE_CLEAR_COOLDOWN - (now - _cache_clear_last))
        raise HTTPException(status_code=429, detail=f"請等待 {remaining} 秒後再試")
    _cache_clear_last = now
    from services.cache_manager import cache_manager
    stats_before = cache_manager.get_stats()
    cache_manager.clear()
    return {"success": True, "message": "快取已清除", "stats_before": stats_before}


# Rate limit state for data refresh
_data_refresh_last = 0.0
_DATA_REFRESH_COOLDOWN = 120  # 2 minutes


@app.get("/api/data/refresh")
async def refresh_data(request: Request):
    """強制刷新所有資料快取並重新抓取最新資料"""
    global _data_refresh_last
    now = time.monotonic()
    if now - _data_refresh_last < _DATA_REFRESH_COOLDOWN:
        remaining = int(_DATA_REFRESH_COOLDOWN - (now - _data_refresh_last))
        raise HTTPException(status_code=429, detail=f"請等待 {remaining} 秒後再試")
    _data_refresh_last = now

    from services.cache_manager import cache_manager
    from services.data_fetcher import data_fetcher

    # 清除日資料快取
    cache_manager.clear("daily")
    cache_manager.delete("latest_trading_date", "general")
    cache_manager.delete("_daily_canonical_key", "general")

    # 重新抓取
    trade_date = await data_fetcher.get_latest_trading_date()
    daily_df = await data_fetcher.get_daily_data(trade_date)
    actual_date = daily_df["date"].iloc[0] if not daily_df.empty and "date" in daily_df.columns else trade_date

    return {
        "success": True,
        "message": f"資料已刷新 ({actual_date})",
        "trade_date": trade_date,
        "actual_data_date": actual_date,
        "stock_count": len(daily_df),
    }


@app.get("/api/cache/stats")
async def cache_stats():
    from services.cache_manager import cache_manager
    return {"success": True, "data": cache_manager.get_stats()}


# ============ FRONTEND STATIC FILES ============
if FRONTEND_DIR:
    # Mount assets folder
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        logger.info(f"✓ Assets mounted: {assets_dir}")

    # Read index.html content once at startup
    INDEX_HTML_PATH = os.path.join(FRONTEND_DIR, "index.html")

    @app.get("/", response_class=HTMLResponse)
    async def serve_root():
        """Serve frontend index.html"""
        return FileResponse(INDEX_HTML_PATH, media_type="text/html")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve frontend files or fallback to index.html for SPA"""
        # Skip API paths
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})

        # Try to serve exact file with path traversal protection
        file_path = os.path.realpath(os.path.join(FRONTEND_DIR, path))
        frontend_real = os.path.realpath(FRONTEND_DIR)
        if not file_path.startswith(frontend_real + os.sep) and file_path != frontend_real:
            return JSONResponse(status_code=403, content={"error": "Forbidden"})
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Fallback to index.html for SPA routing
        return FileResponse(INDEX_HTML_PATH, media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
