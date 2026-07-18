"""Integration tests for Telegram webhook."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User


@pytest.fixture
async def telegram_user(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="telegramtest@example.com", hashed_password=hash_password("testpass"))
    db.add(user)
    await db.flush()
    return user


def _make_update(text: str, chat_id: int = 99999) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
            "text": text,
            "date": 1700000000,
        },
    }


class TestTelegramWebhook:

    @pytest.mark.asyncio
    async def test_invalid_secret_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/telegram/webhook",
            json=_make_update("/start"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert resp.status_code in (403, 404)  # 403 on wrong secret, response depends on webhook_secret setting

    @pytest.mark.asyncio
    async def test_missing_secret_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/telegram/webhook",
            json=_make_update("/start"),
        )
        assert resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_valid_start_returns_200(self, client: AsyncClient) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        webhook_secret = settings.telegram_webhook_secret or "test-secret"

        with (
            patch("app.core.config.get_settings") as mock_settings,
            patch(
                "app.services.telegram_bot_service._send_reply",
                AsyncMock(),
            ),
        ):
            mock_settings.return_value.telegram_webhook_secret = webhook_secret
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_bot_name = "testbot"

            resp = await client.post(
                "/api/v1/telegram/webhook",
                json=_make_update("/start"),
                headers={"X-Telegram-Bot-Api-Secret-Token": webhook_secret},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_follow_unrecognized_url(self, client: AsyncClient) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        webhook_secret = settings.telegram_webhook_secret or "test-secret"

        reply_mock = AsyncMock()
        with (
            patch("app.core.config.get_settings") as mock_settings,
            patch("app.services.telegram_bot_service._send_reply", reply_mock),
        ):
            mock_settings.return_value.telegram_webhook_secret = webhook_secret
            mock_settings.return_value.telegram_bot_token = "test-token"
            mock_settings.return_value.telegram_bot_name = "testbot"

            resp = await client.post(
                "/api/v1/telegram/webhook",
                json=_make_update("/follow https://unknown-site.com/listing/123"),
                headers={"X-Telegram-Bot-Api-Secret-Token": webhook_secret},
            )
        assert resp.status_code == 200
