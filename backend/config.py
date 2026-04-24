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

    # TWSE SSL (Python 3.14 strict verification workaround)
    #   "default"  — use system/certifi CA bundle (recommended)
    #   "certifi"  — force certifi bundle
    #   "relaxed"  — accept missing Subject Key Identifier (workaround for TWSE cert)
    #   "insecure" — disable verification entirely (NOT recommended in prod)
    twse_ssl_mode: str = "default"
    twse_ssl_ca_bundle: Optional[str] = None

    # Cache settings (seconds)
    cache_daily_data: int = 14400
    cache_historical_data: int = 86400
    cache_indicators: int = 14400
    cache_industries: int = 604800

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

    # Background sync / backfill (previously hard-coded)
    backfill_min_days: int = 60            # was `< 5`; MA20/MA60 need >= 60 days
    backfill_batch_size: int = 200         # max tickers fetched from legacy per sync
    backfill_concurrency: int = 10         # parallel fetch cap
    periodic_refresh_interval: int = 1800  # 30 min
    sync_tse_open_hour: int = 8
    sync_tse_open_minute: int = 30
    sync_tse_close_hour: int = 14
    sync_tse_close_minute: int = 30

    # Admin / auth (gate dangerous endpoints)
    admin_token: Optional[str] = None
    require_admin_token: bool = True       # set false in local dev to disable gate

    # Rate-limit cooldowns (seconds)
    cooldown_cache_clear: int = 60
    cooldown_data_refresh: int = 120
    cooldown_sync: int = 300

    # Screen API request caps (DoS protection)
    max_rules_per_request: int = 32
    max_formulas_per_request: int = 8
    max_formula_length: int = 500
    max_formula_tokens: int = 50

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
