from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.infrastructure.config.settings import get_settings

settings = get_settings()

# Convert database URL to async format
async_database_url = settings.database_url
if "postgresql+psycopg2://" in async_database_url:
    async_database_url = async_database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
elif async_database_url.startswith("postgresql://"):
    async_database_url = async_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine with connection pooling
# asyncpg handles connection pooling internally, so we don't need NullPool
engine = create_async_engine(
    async_database_url,
    pool_pre_ping=True,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependencies.

    Kept as a thin wrapper so it is easy to mock in tests.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


