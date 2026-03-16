"""Rental service layer.

Availability rule for rentals:
  SUM(quantity of active bookings overlapping the date range) must be < item.quantity_available.
  Active = all bookings where status != canceled.
  Overlap (half-open): existing.check_in < new.check_out AND existing.check_out > new.check_in.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rentals.models import RentalBooking, RentalItem


async def is_rental_available(
    db: AsyncSession,
    rental_item_id: uuid.UUID,
    check_in: date,
    check_out: date,
    quantity: int,
) -> bool:
    """Return True if `quantity` units of the rental item are free for the date range."""
    if check_out <= check_in or quantity < 1:
        return False

    item_result = await db.execute(
        select(RentalItem).where(RentalItem.id == rental_item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None or not item.is_active:
        return False

    # All non-canceled bookings block inventory (spec: status != canceled)
    active_filter = and_(
        RentalBooking.rental_item_id == rental_item_id,
        RentalBooking.check_in < check_out,
        RentalBooking.check_out > check_in,
        RentalBooking.status != "canceled",
    )
    result = await db.execute(
        select(func.coalesce(func.sum(RentalBooking.quantity), 0)).where(active_filter)
    )
    used: int = result.scalar_one()
    return (used + quantity) <= item.quantity_available


async def calculate_rental_price(
    item: RentalItem,
    check_in: date,
    check_out: date,
    quantity: int,
) -> Decimal:
    """price_per_day * nights * quantity."""
    nights = (check_out - check_in).days
    return item.price_per_day * nights * quantity
