"""
TWSE Stock Filter API - Main Application
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from config import get_settings
from database import init_db, close_db
from routers import (
    stocks_router, analysis_router, backtest_router,
    watchlist_router, history_router, export_router, turnover_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting TWSE Stock Filter API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="台股漲幅區間篩選器 API - 提供股票篩選、技術分析、回測等功能",
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
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc)}
    )


# Include routers
app.include_router(stocks_router)
app.include_router(analysis_router)
app.include_router(backtest_router)
app.include_router(watchlist_router)
app.include_router(history_router)
app.include_router(export_router)
app.include_router(turnover_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/cache/clear")
async def clear_cache():
    """
    Manual cache clearing endpoint
    Clears all cached data to force fresh data fetching
    """
    from services.cache_manager import cache_manager
    
    stats_before = cache_manager.get_stats()
    cache_manager.clear()
    stats_after = cache_manager.get_stats()
    
    logger.info("Cache cleared via API")
    return {
        "success": True,
        "message": "快取已清除",
        "stats_before": stats_before,
        "stats_after": stats_after
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """Get current cache statistics"""
    from services.cache_manager import cache_manager
    return {
        "success": True,
        "data": cache_manager.get_stats()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
