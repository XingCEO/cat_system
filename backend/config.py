"""
TWSE Stock Filter - Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    app_name: str = "TWSE Stock Filter API"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./twse_filter.db"
    
    # FinMind API
    finmind_api_token: Optional[str] = None
    finmind_base_url: str = "https://api.finmindtrade.com/api/v4/data"
    
    # TWSE Open Data (backup)
    twse_base_url: str = "https://www.twse.com.tw/exchangeReport"
    
    # Cache settings (seconds)
    cache_daily_data: int = 14400  # 4 hours (daily data only changes once a day)
    cache_historical_data: int = 86400  # 24 hours
    cache_indicators: int = 14400  # 4 hours (K線+技術指標，盤後才更新)
    cache_industries: int = 604800  # 7 days (permanent-like)
    
    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Pagination
    default_page_size: int = 50
    max_page_size: int = 200
    
    # API retry settings
    api_retry_count: int = 3
    api_retry_delay: float = 1.0
    
    # Legacy/extra cache settings
    cache_expire_seconds: int = 300

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
