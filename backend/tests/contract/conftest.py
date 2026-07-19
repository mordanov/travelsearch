"""Contract-test conftest: no live DB needed."""

import pytest_asyncio


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> None:  # type: ignore[override]
    """No-op: contract tests use mocked HTTP and recorded fixtures, no DB."""
    yield  # type: ignore[misc]
