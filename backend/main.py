"""
喵喵選股 — 台股客製化選股系統 API
(TWSE Stock Filter API + 喵喵選股 v1 API)
"""
import os
import sys
from fastapi import FastAPI, Request
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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


@app.get("/api/cache/clear")
async def clear_cache():
    from services.cache_manager import cache_manager
    stats_before = cache_manager.get_stats()
    cache_manager.clear()
    return {"success": True, "message": "快取已清除", "stats_before": stats_before}


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

        # Try to serve exact file
        file_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Fallback to index.html for SPA routing
        return FileResponse(INDEX_HTML_PATH, media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
