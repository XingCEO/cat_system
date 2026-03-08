"""
TWSE Stock Filter - Database Configuration
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

settings = get_settings()


def _resolve_database_url() -> str:
    """
    自動解析資料庫 URL，支援多種部署平台的環境變數格式：
    1. 優先使用 config.database_url (DATABASE_URL 環境變數)
    2. 若未設定，嘗試從 POSTGRES_URI / POSTGRES_HOST 等組合
    3. 自動將 postgres:// / postgresql:// 轉為 postgresql+asyncpg://
    """
    url = settings.database_url

    # Zeabur 可能注入 POSTGRES_URI 而非 DATABASE_URL
    if url == "sqlite+aiosqlite:///./twse_filter.db":
        zeabur_uri = os.getenv("POSTGRES_URI") or os.getenv("POSTGRES_URL")
        if zeabur_uri:
            url = zeabur_uri
        else:
            # 嘗試從個別環境變數組合
            host = os.getenv("POSTGRES_HOST")
            if host:
                port = os.getenv("POSTGRES_PORT", "5432")
                user = os.getenv("POSTGRES_USERNAME") or os.getenv("POSTGRES_USER", "postgres")
                password = os.getenv("POSTGRES_PASSWORD", "")
                db = os.getenv("POSTGRES_DATABASE") or os.getenv("POSTGRES_DB", "postgres")
                url = f"postgresql://{user}:{password}@{host}:{port}/{db}"

    # 將同步 driver 轉為 async driver
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


db_url = _resolve_database_url()

# Create async engine
engine = create_async_engine(
    db_url,
    echo=settings.debug,
    future=True
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Initialize database tables and run column migrations for existing DBs"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # SQLite: add new columns to existing tables that may not have them yet
    if "sqlite" in db_url:
        await _migrate_sqlite_columns()


async def close_db():
    """Close database connection"""
    await engine.dispose()


async def _migrate_sqlite_columns():
    """
    SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS.
    We query pragma and add missing columns manually.
    """
    import logging
    logger = logging.getLogger(__name__)

    # New columns for daily_prices table
    new_daily_price_cols = [
        ("turnover",                  "REAL"),
        ("avg_volume_20",             "REAL"),
        ("avg_turnover_20",           "REAL"),
        ("lower_shadow",              "REAL"),
        ("lowest_lower_shadow_20",    "REAL"),
        ("wma10",                     "REAL"),
        ("wma20",                     "REAL"),
        ("wma60",                     "REAL"),
        ("market_ok",                 "INTEGER"),  # Boolean as INTEGER in SQLite
    ]

    async with engine.begin() as conn:
        # Get existing columns for daily_prices
        pragma_result = await conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(daily_prices)")
        )
        existing = {row[1] for row in pragma_result.fetchall()}

        for col_name, col_type in new_daily_price_cols:
            if col_name not in existing:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE daily_prices ADD COLUMN {col_name} {col_type}"
                    )
                )
                logger.info(f"Migration: added column daily_prices.{col_name}")

    logger.info("SQLite column migration complete")
