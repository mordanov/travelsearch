"""Unit-test conftest: override the session-scoped create_tables fixture.

Unit tests mock all DB calls and do not need a live PostgreSQL connection.
This override prevents the root conftest from attempting to connect.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def create_tables() -> None:  # type: ignore[override]
    """No-op: unit tests use mocked DB sessions."""
    yield  # type: ignore[misc]
