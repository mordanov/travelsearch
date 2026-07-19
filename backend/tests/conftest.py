import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app

TEST_DATABASE_URL = (
    os.getenv("DATABASE_URL_TEST")
    or os.getenv("DATABASE_URL")
    or "postgresql+asyncpg://postgres:postgres@localhost:5432/travelsearch_test"
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None]:
    # Engine created inside the fixture so it shares the session-scoped event loop.
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
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
