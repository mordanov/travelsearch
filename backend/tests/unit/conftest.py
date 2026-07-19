"""Unit-test conftest: no live DB needed."""

import pytest_asyncio


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> None:  # type: ignore[override]
    """No-op: unit tests use mocked DB sessions."""
    yield  # type: ignore[misc]
