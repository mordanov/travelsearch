from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class NotificationType(str, Enum):
    NEW_LISTING = "new_listing"
    PRICE_DROP = "price_drop"


@dataclass
class NotificationMessage:
    type: NotificationType
    property_name: str
    property_url: str
    price_after: Decimal
    price_before: Optional[Decimal] = None  # None for new_listing


class Notifier(ABC):

    @abstractmethod
    async def send(
        self,
        telegram_chat_id: int,
        message: NotificationMessage,
    ) -> bool:
        """
        Send a notification to the user's Telegram chat.
        Returns True on success, False on delivery failure.
        MUST NOT raise — encode failure in return value.
        """
        ...
