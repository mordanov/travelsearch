import uuid
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DB, CurrentUser
from app.repositories.property_repository import get_amenities, get_by_id
from app.schemas.search import PropertyListingResponse

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/property", tags=["property"])


@router.get("/{property_id}", response_model=PropertyListingResponse)
async def get_property(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> PropertyListingResponse:
    prop = await get_by_id(db, property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    amenities = await get_amenities(prop)
    return PropertyListingResponse(
        property_id=prop.id,
        provider=prop.provider,
        name=prop.name,
        price_per_night=Decimal("0"),
        total_price=Decimal("0"),
        bedrooms=prop.bedrooms,
        bathrooms=prop.bathrooms,
        amenities=amenities,
        url=prop.url,
        location=prop.location,
    )
