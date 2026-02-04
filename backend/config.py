"""
TWSE Stock Filter - Configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    app_name: str = "TWSE Stock Filter API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./twse_filter.db"
    
    # FinMind API
    finmind_api_token: Optional[str] = None
    finmind_base_url: str = "https://api.finmindtrade.com/api/v4/data"
    
    # TWSE Open Data (backup)
    twse_base_url: str = "https://www.twse.com.tw/exchangeReport"
    
    # Cache settings (seconds)
    cache_daily_data: int = 300  # 5 minutes
    cache_historical_data: int = 86400  # 24 hours
    cache_indicators: int = 3600  # 1 hour
    cache_industries: int = 604800  # 7 days (permanent-like)
    
    # CORS
    cors_origins: str = "*"
    
    # Pagination
    default_page_size: int = 50
    max_page_size: int = 200
    
    # API retry settings
    api_retry_count: int = 3
    api_retry_delay: float = 1.0
    
    # Legacy/extra cache settings
    cache_expire_seconds: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
