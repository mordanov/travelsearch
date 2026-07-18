"""
arq job: re-run TrackedSearch and diff against baseline.
Safe-discard invariant: never write to DB if scrape status != OK.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models.tracked_search import TrackedSearch, TrackedSearchSeenProperty
from app.notifiers.base import NotificationMessage, NotificationType
from app.notifiers.telegram import TelegramNotifier
from app.providers.base import PropertyListing, ScrapeStatus
from app.repositories import notification_repository, tracking_repository
from app.repositories.property_repository import upsert_property
from app.repositories.search_repository import get_search

log = structlog.get_logger(__name__)


@dataclass
class NewListing:
    listing: PropertyListing
    prop_id: str


@dataclass
class PriceDrop:
    listing: PropertyListing
    prop_id: str
    previous_min: Decimal


DiffEvent = NewListing | PriceDrop


def compute_search_diff(
    listings_by_prop_id: dict[str, PropertyListing],
    seen_by_prop_id: dict[str, TrackedSearchSeenProperty],
) -> list[DiffEvent]:
    """
    Pure diff: given post-upsert DB property UUIDs → listings and the seen-property baseline,
    return NewListing events for first-seen properties and PriceDrop events where
    current total_price < min_price_seen. Empty listings_by_prop_id returns [].
    """
    events: list[DiffEvent] = []
    for prop_id_str, listing in listings_by_prop_id.items():
        if prop_id_str not in seen_by_prop_id:
            events.append(NewListing(listing=listing, prop_id=prop_id_str))
        else:
            sp = seen_by_prop_id[prop_id_str]
            current_price = Decimal(str(listing.total_price))
            min_price = Decimal(str(sp.min_price_seen))
            if current_price < min_price:
                events.append(PriceDrop(listing=listing, prop_id=prop_id_str, previous_min=min_price))
    return events


async def rerun_tracked_search(ctx: dict[str, Any]) -> None:
    # Constitution I: providers injected via arq ctx (populated by scheduler.on_startup)
    provider_map: dict[str, Any] = ctx.get("providers", {})
    factory = get_session_factory()
    async with factory() as db:
        overdue = await tracking_repository.get_overdue_tracked_searches(db)
        log.info("search_worker_tick", overdue_count=len(overdue))

        notifier = TelegramNotifier()

        for ts in overdue:
            await _process_tracked_search(db, ts, notifier, provider_map)


async def _process_tracked_search(
    db: AsyncSession,
    ts: TrackedSearch,
    notifier: TelegramNotifier,
    provider_map: dict[str, Any],
) -> None:
    from app.repositories.user_repository import get_by_id as get_user

    search = await get_search(db, ts.search_id)
    if search is None:
        log.warning("tracked_search_no_source_search", ts_id=ts.id)
        return

    user = await get_user(db, ts.user_id)
    if user is None:
        return

    providers_to_run = list(search.providers) if search.providers else ["booking", "airbnb"]

    all_listings: list[PropertyListing] = []
    any_ok = False

    for pname in providers_to_run:
        prov = provider_map.get(pname)
        if prov is None:
            continue
        try:
            result = await prov.search(
                destination=search.destination,
                check_in=search.check_in.date() if hasattr(search.check_in, "date") else search.check_in,
                check_out=search.check_out.date() if hasattr(search.check_out, "date") else search.check_out,
                guests=search.guests,
                filters=search.filters or {},
            )
        except Exception:
            log.exception("tracked_search_provider_error", ts_id=ts.id, provider=pname)
            continue

        if result.status != ScrapeStatus.OK:
            log.warning(
                "tracked_search_provider_discard",
                ts_id=ts.id,
                provider=pname,
                status=result.status,
            )
            continue

        any_ok = True
        all_listings.extend(result.listings)

    if not any_ok or not all_listings:
        log.warning("tracked_search_cycle_discarded", ts_id=ts.id)
        return

    # Upsert all listings to DB first; build UUID-keyed maps for pure diff
    now = datetime.utcnow()
    listings_by_prop_id: dict[str, PropertyListing] = {}
    prop_objects: dict[str, Any] = {}
    for listing in all_listings:
        prop = await upsert_property(db, listing)
        prop_id_str = str(prop.id)
        listings_by_prop_id[prop_id_str] = listing
        prop_objects[prop_id_str] = prop

    seen_props = await tracking_repository.get_seen_properties(db, ts.id)
    seen_by_prop_id: dict[str, TrackedSearchSeenProperty] = {
        str(sp.property_id): sp for sp in seen_props
    }

    events = compute_search_diff(listings_by_prop_id, seen_by_prop_id)
    events_by_prop_id = {e.prop_id: e for e in events}

    for prop_id_str, listing in listings_by_prop_id.items():
        prop = prop_objects[prop_id_str]
        current_price = Decimal(str(listing.total_price))
        event = events_by_prop_id.get(prop_id_str)

        if isinstance(event, NewListing):
            notification_row = await notification_repository.create_notification_log(
                db=db,
                user_id=ts.user_id,
                notification_type="new_listing",
                property_id=prop.id,
                property_url=listing.url,
                price_after=float(current_price),
                tracked_search_id=ts.id,
                delivery_status="pending",
            )
            if user.telegram_chat_id:
                msg = NotificationMessage(
                    type=NotificationType.NEW_LISTING,
                    property_name=listing.name,
                    property_url=listing.url,
                    price_after=current_price,
                )
                ok = await notifier.send(user.telegram_chat_id, msg)
                notification_row.delivery_status = "sent" if ok else "failed"

        elif isinstance(event, PriceDrop):
            notification_row = await notification_repository.create_notification_log(
                db=db,
                user_id=ts.user_id,
                notification_type="price_drop",
                property_id=prop.id,
                property_url=listing.url,
                price_after=float(current_price),
                price_before=float(event.previous_min),
                tracked_search_id=ts.id,
                delivery_status="pending",
            )
            if user.telegram_chat_id:
                msg = NotificationMessage(
                    type=NotificationType.PRICE_DROP,
                    property_name=listing.name,
                    property_url=listing.url,
                    price_after=current_price,
                    price_before=event.previous_min,
                )
                ok = await notifier.send(user.telegram_chat_id, msg)
                notification_row.delivery_status = "sent" if ok else "failed"

        # Always update the seen-property min price (tracks the running minimum across cycles)
        await tracking_repository.upsert_seen_property(
            db, ts.id, prop.id, float(current_price), now
        )

    next_run_at = now + timedelta(hours=ts.interval_hours)
    await tracking_repository.update_tracked_search_after_run(db, ts, next_run_at)
    await db.commit()
    log.info("tracked_search_cycle_complete", ts_id=ts.id)
