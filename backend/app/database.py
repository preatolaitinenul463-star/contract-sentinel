"""Database connection and session management."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# Create async engine with appropriate settings based on database type
is_sqlite = settings.database_url.startswith("sqlite")

if is_sqlite:
    # SQLite doesn't support pool settings
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL with connection pooling
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_lightweight_schema_fixes(conn)


async def _run_lightweight_schema_fixes(conn) -> None:
    """Best-effort schema compatibility fixes for local/dev deployments.

    This keeps existing SQLite/PostgreSQL databases usable when new columns
    are introduced without running Alembic migrations.
    """
    try:
        if is_sqlite:
            # SQLite: check users table columns, add missing is_admin column.
            result = await conn.execute(text("PRAGMA table_info(users)"))
            cols = {row[1] for row in result.fetchall()}  # row[1] = column name
            if "is_admin" not in cols:
                await conn.execute(
                    text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
                )
        else:
            # PostgreSQL: add column if missing.
            await conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
    except Exception:
        # Do not block app startup; this is a compatibility helper only.
        pass


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
