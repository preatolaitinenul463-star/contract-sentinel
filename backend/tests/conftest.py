"""Test configuration and fixtures."""
import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a test database session."""
    async with test_session_maker() as session:
        yield session


@pytest.fixture
def app():
    """Create a test FastAPI app with overridden dependencies."""
    from fastapi.testclient import TestClient
    from app.main import app as main_app
    from app.database import get_db

    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    main_app.dependency_overrides[get_db] = override_get_db
    yield main_app
    main_app.dependency_overrides.clear()
