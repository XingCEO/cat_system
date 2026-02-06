"""
TWSE Stock Filter - Database Configuration

Supports both SQLite (local) and PostgreSQL (production).
Connection string is read from DATABASE_URL environment variable.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from config import get_settings

settings = get_settings()

# Configure engine options based on database type
engine_options = {
    "echo": settings.debug,
    "future": True,
}

# PostgreSQL requires different pool settings for async
if settings.is_postgres:
    engine_options["poolclass"] = NullPool  # Recommended for async PostgreSQL

# Create async engine
engine = create_async_engine(
    settings.database_url,
    **engine_options
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
