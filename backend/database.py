"""
TWSE Stock Filter - Database Configuration
"""
import os
from sqlalchemy import inspect, text
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
    # First normalise any postgresql+<other-driver>:// to bare postgresql://
    if url.startswith("postgresql+") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url.split("://", 1)[1]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
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
        await _migrate_existing_schema(conn)


async def close_db():
    """Close database connection"""
    await engine.dispose()


async def _migrate_existing_schema(conn):
    """
    Add columns that create_all() cannot add to already-existing tables.

    This is intentionally narrow and additive: it covers production databases
    that were created by older app versions and would otherwise fail at runtime
    when newer ORM models select or insert these columns.
    """
    daily_price_cols = [
        ("turnover",                  "REAL"),
        ("avg_volume_20",             "REAL"),
        ("avg_turnover_20",           "REAL"),
        ("lower_shadow",              "REAL"),
        ("lowest_lower_shadow_20",    "REAL"),
        ("wma10",                     "REAL"),
        ("wma20",                     "REAL"),
        ("wma60",                     "REAL"),
        ("market_ok",                 "INTEGER"),
    ]
    backtest_result_cols = [
        ("filter_conditions", "JSON"),
        ("start_date", "VARCHAR(10)"),
        ("end_date", "VARCHAR(10)"),
        ("lookback_days", "INTEGER"),
        ("total_signals", "INTEGER"),
        ("unique_stocks", "INTEGER"),
        ("win_rate", "FLOAT"),
        ("avg_return_1d", "FLOAT"),
        ("avg_return_3d", "FLOAT"),
        ("avg_return_5d", "FLOAT"),
        ("avg_return_10d", "FLOAT"),
        ("max_gain", "FLOAT"),
        ("max_loss", "FLOAT"),
        ("expected_value", "FLOAT"),
        ("detailed_results", "TEXT"),
        ("created_at", "DATETIME" if conn.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"),
    ]
    user_strategy_cols = [
        ("line_notify_token", "TEXT"),
    ]

    await _add_missing_columns(conn, "daily_prices", daily_price_cols)
    await _add_missing_columns(conn, "backtest_results", backtest_result_cols)
    await _add_missing_columns(conn, "user_strategies", user_strategy_cols)


async def _add_missing_columns(conn, table_name: str, columns: list[tuple[str, str]]):
    import logging
    logger = logging.getLogger(__name__)

    def get_existing_columns(sync_conn):
        inspector = inspect(sync_conn)
        if table_name not in inspector.get_table_names():
            return None
        return {col["name"] for col in inspector.get_columns(table_name)}

    existing = await conn.run_sync(get_existing_columns)
    if existing is None:
        return

    for col_name, col_type in columns:
        if col_name not in existing:
            await conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
            )
            logger.info(f"Migration: added column {table_name}.{col_name}")


async def _migrate_sqlite_columns():
    """
    SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS.
    We query pragma and add missing columns manually.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Compatibility wrapper for older callers/tests; init_db uses the generic
    # migration path above for both SQLite and PostgreSQL.
    async with engine.begin() as conn:
        await _migrate_existing_schema(conn)

    logger.info("SQLite column migration complete")
