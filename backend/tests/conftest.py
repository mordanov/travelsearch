import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app

TEST_DATABASE_URL = (
    os.getenv("DATABASE_URL_TEST")
    or os.getenv("DATABASE_URL")
    or "postgresql+asyncpg://postgres:postgres@localhost:5432/travelsearch_test"
)

_SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
_TABLE_NAMES = [t.name for t in reversed(Base.metadata.sorted_tables)]


@pytest.fixture(scope="session", autouse=True)
def create_tables() -> Any:
    engine = create_engine(_SYNC_URL)
    Base.metadata.create_all(engine)
    engine.dispose()
    yield
    engine = create_engine(_SYNC_URL)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def db_session(create_tables: Any) -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    # Wipe all rows after the test using an independent sync connection
    sync_engine = create_engine(_SYNC_URL)
    with sync_engine.begin() as conn:
        for table in _TABLE_NAMES:
            conn.execute(text(f'DELETE FROM "{table}"'))
    sync_engine.dispose()
    await engine.dispose()


@pytest.fixture
def redis_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_mock: AsyncMock) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    async def override_get_redis() -> AsyncGenerator[Any]:
        yield redis_mock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
