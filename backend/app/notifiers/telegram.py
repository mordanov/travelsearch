import httpx
import structlog

from app.core.config import get_settings
from app.notifiers.base import NotificationMessage, NotificationType, Notifier

log = structlog.get_logger(__name__)


class TelegramNotifier(Notifier):
    async def send(self, telegram_chat_id: int, message: NotificationMessage) -> bool:
        settings = get_settings()
        if not settings.telegram_bot_token:
            log.warning("telegram_bot_token_not_set")
            return False

        text = self._format(message)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": telegram_chat_id, "text": text, "parse_mode": "HTML"},
                )
            if resp.status_code >= 400:
                log.warning(
                    "telegram_send_failed",
                    status=resp.status_code,
                    chat_id=telegram_chat_id,
                )
                return False
            return True
        except Exception:
            log.exception("telegram_send_error", chat_id=telegram_chat_id)
            return False

    def _format(self, message: NotificationMessage) -> str:
        if message.type == NotificationType.PRICE_DROP:
            return (
                f"📉 <b>Price Drop!</b>\n"
                f"{message.property_name}\n"
                f"Was: {message.price_before} → Now: <b>{message.price_after}</b>\n"
                f'<a href="{message.property_url}">View listing</a>'
            )
        return (
            f"🆕 <b>New Listing!</b>\n"
            f"{message.property_name}\n"
            f"Price: <b>{message.price_after}</b>\n"
            f'<a href="{message.property_url}">View listing</a>'
        )
