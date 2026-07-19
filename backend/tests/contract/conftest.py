"""Contract-test conftest: no live DB needed."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def create_tables() -> None:  # type: ignore[override]
    """No-op: contract tests use mocked HTTP and recorded fixtures, no DB."""
    yield  # type: ignore[misc]
