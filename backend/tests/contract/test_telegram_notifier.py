"""Contract tests for TelegramNotifier — mocked httpx."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.notifiers.base import NotificationMessage, NotificationType
from app.notifiers.telegram import TelegramNotifier


class TestTelegramNotifier:

    @pytest.mark.asyncio
    async def test_sends_price_drop_message(self) -> None:
        notifier = TelegramNotifier()
        msg = NotificationMessage(
            type=NotificationType.PRICE_DROP,
            property_name="Gothic Quarter Apt",
            property_url="https://booking.com/gothic",
            price_after=Decimal("87.00"),
            price_before=Decimal("110.00"),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.notifiers.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await notifier.send(telegram_chat_id=12345, message=msg)

        assert result is True
        mock_client_instance.post.assert_called_once()
        call_kwargs = mock_client_instance.post.call_args.kwargs
        assert call_kwargs["json"]["chat_id"] == 12345
        assert "Price Drop" in call_kwargs["json"]["text"] or "drop" in call_kwargs["json"]["text"].lower()

    @pytest.mark.asyncio
    async def test_sends_new_listing_message(self) -> None:
        notifier = TelegramNotifier()
        msg = NotificationMessage(
            type=NotificationType.NEW_LISTING,
            property_name="New Beachfront Villa",
            property_url="https://airbnb.com/rooms/99999",
            price_after=Decimal("150.00"),
            price_before=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.notifiers.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await notifier.send(telegram_chat_id=12345, message=msg)

        assert result is True
        call_kwargs = mock_client_instance.post.call_args.kwargs
        text = call_kwargs["json"]["text"]
        assert "New" in text or "Listing" in text or "listing" in text

    @pytest.mark.asyncio
    async def test_returns_false_on_api_error(self) -> None:
        notifier = TelegramNotifier()
        msg = NotificationMessage(
            type=NotificationType.PRICE_DROP,
            property_name="Test Hotel",
            property_url="https://booking.com/test",
            price_after=Decimal("80.00"),
            price_before=Decimal("100.00"),
        )

        mock_response = MagicMock()
        mock_response.status_code = 400  # Telegram API error

        with patch("app.notifiers.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await notifier.send(telegram_chat_id=12345, message=msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_not_raises_on_network_error(self) -> None:
        notifier = TelegramNotifier()
        msg = NotificationMessage(
            type=NotificationType.NEW_LISTING,
            property_name="Hotel X",
            property_url="https://booking.com/x",
            price_after=Decimal("100"),
        )

        with patch("app.notifiers.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "test-token"
            with patch("httpx.AsyncClient") as MockClient:
                MockClient.side_effect = Exception("Network failure")

                result = await notifier.send(telegram_chat_id=12345, message=msg)

        assert result is False
