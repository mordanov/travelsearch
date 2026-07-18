import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.providers.base import PropertyListing

log = structlog.get_logger(__name__)


async def upsert_property(db: AsyncSession, listing: PropertyListing) -> Property:
    stmt = (
        insert(Property)
        .values(
            provider=listing.provider,
            provider_property_id=listing.provider_property_id,
            name=listing.name,
            url=listing.url,
            location=listing.location,
            latitude=listing.latitude,
            longitude=listing.longitude,
            bedrooms=listing.bedrooms,
            bathrooms=listing.bathrooms,
            amenities={"items": listing.amenities} if listing.amenities else None,
        )
        .on_conflict_do_update(
            constraint="uq_property_identity",
            set_={
                "name": listing.name,
                "url": listing.url,
                "location": listing.location,
                "latitude": listing.latitude,
                "longitude": listing.longitude,
                "bedrooms": listing.bedrooms,
                "bathrooms": listing.bathrooms,
                "amenities": {"items": listing.amenities} if listing.amenities else None,
            },
        )
        .returning(Property)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row is None:
        msg = "upsert_property returned no row"
        raise RuntimeError(msg)
    prop: Property = row[0]
    return prop


async def get_by_id(db: AsyncSession, property_id: uuid.UUID) -> Property | None:
    result = await db.execute(select(Property).where(Property.id == property_id))
    return result.scalar_one_or_none()


async def get_amenities(prop: Property) -> list[str]:
    if prop.amenities and isinstance(prop.amenities, dict):
        items = prop.amenities.get("items", [])
        if isinstance(items, list):
            return [str(i) for i in items]
    return []
