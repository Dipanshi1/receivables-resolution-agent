"""Database engine creation, session management, and FastAPI dependency.

Provides SQLAlchemy 2.x asynchronous database integration using asyncpg.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


def get_async_database_url(url: str) -> str:
    """Normalize database URL to use the asyncpg dialect driver if needed.

    Args:
        url: Raw database connection string.

    Returns:
        Connection string with asyncpg dialect.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def create_engine_from_settings(settings: Settings | None = None) -> AsyncEngine:
    """Create a configured AsyncEngine from application settings.

    Args:
        settings: Optional Settings instance; defaults to cached get_settings().

    Returns:
        Configured AsyncEngine.
    """
    app_settings = settings or get_settings()
    normalized_url = get_async_database_url(app_settings.database_url)
    is_dev = app_settings.app_env.value == "development"

    return create_async_engine(
        normalized_url,
        echo=is_dev,
        future=True,
        pool_pre_ping=True,
    )


# Module-level engine and session factory
engine: AsyncEngine = create_engine_from_settings()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an asynchronous database session.

    Ensures rollback on unhandled exceptions and proper session closure.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
