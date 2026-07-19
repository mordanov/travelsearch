import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app

TEST_DATABASE_URL = (
    os.getenv("DATABASE_URL_TEST")
    or os.getenv("DATABASE_URL")
    or "postgresql+asyncpg://postgres:postgres@localhost:5432/travelsearch_test"
)

_TABLE_NAMES = [t.name for t in reversed(Base.metadata.sorted_tables)]

# One NullPool engine shared across the session — all tests share the same event loop,
# so there is no cross-loop issue with NullPool (each operation opens+closes its connection).
_async_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_async_factory = async_sessionmaker(bind=_async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None]:
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def truncate_tables(create_tables: Any) -> AsyncGenerator[None]:
    yield
    async with _async_engine.begin() as conn:
        for table in _TABLE_NAMES:
            await conn.execute(text(f'DELETE FROM "{table}"'))


@pytest_asyncio.fixture
async def db_session(truncate_tables: Any) -> AsyncGenerator[AsyncSession]:
    async with _async_factory() as session:
        yield session


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
