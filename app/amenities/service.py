"""Amenity service layer."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amenities.models import AmenityBooking, AmenityItem


async def is_amenity_available(
    db: AsyncSession,
    amenity_item_id: uuid.UUID,
    booking_date: date,
    quantity: int,
) -> bool:
    """Return True if quantity slots are free for the given date."""
    if quantity < 1:
        return False

    item_result = await db.execute(
        select(AmenityItem).where(AmenityItem.id == amenity_item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None or not item.is_active:
        return False

    if item.daily_capacity is None:
        return True

    active_filter = and_(
        AmenityBooking.amenity_item_id == amenity_item_id,
        AmenityBooking.date == booking_date,
        AmenityBooking.status != "canceled",
    )
    result = await db.execute(
        select(func.coalesce(func.sum(AmenityBooking.quantity), 0)).where(active_filter)
    )
    used: int = result.scalar_one()
    return (used + quantity) <= item.daily_capacity


async def calculate_amenity_price(
    item: AmenityItem,
    quantity: int,
) -> Decimal:
    """price_per_person * quantity."""
    return item.price_per_person * quantity
