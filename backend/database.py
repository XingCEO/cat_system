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
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection"""
    await engine.dispose()
