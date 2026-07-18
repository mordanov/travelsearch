"""Integration tests for Telegram linking flow."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User


@pytest.fixture
async def link_user(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="linktest@example.com", hashed_password=hash_password("testpass"))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def link_token(client: AsyncClient, link_user: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "linktest@example.com", "password": "testpass"},
    )
    return resp.json()["access_token"]


class TestTelegramLinking:

    @pytest.mark.asyncio
    async def test_generate_link_code(
        self, client: AsyncClient, link_user: User, link_token: str, redis_mock: AsyncMock
    ) -> None:
        redis_mock.setex = AsyncMock(return_value=True)
        resp = await client.post(
            "/api/v1/telegram/link-code",
            headers={"Authorization": f"Bearer {link_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "code" in data
        assert len(data["code"]) == 8
        assert data["expires_in_seconds"] == 900
        assert "deep_link" in data

    @pytest.mark.asyncio
    async def test_unlink_telegram(
        self, client: AsyncClient, link_user: User, link_token: str
    ) -> None:
        resp = await client.delete(
            "/api/v1/telegram/link",
            headers={"Authorization": f"Bearer {link_token}"},
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_start_links_account(
        self, client: AsyncClient, link_user: User, redis_mock: AsyncMock
    ) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        webhook_secret = settings.telegram_webhook_secret or "test-secret"

        code = "testcode"
        chat_id = 77777

        redis_mock.get = AsyncMock(return_value=str(link_user.id))
        redis_mock.delete = AsyncMock(return_value=1)

        with (
            patch("app.core.config.get_settings") as mock_settings,
            patch("app.services.telegram_bot_service._send_reply", AsyncMock()),
        ):
            mock_settings.return_value.telegram_webhook_secret = webhook_secret
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_bot_name = "testbot"

            resp = await client.post(
                "/api/v1/telegram/webhook",
                json={
                    "update_id": 1,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": chat_id, "type": "private"},
                        "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
                        "text": f"/start {code}",
                        "date": 1700000000,
                    },
                },
                headers={"X-Telegram-Bot-Api-Secret-Token": webhook_secret},
            )
        assert resp.status_code == 200
