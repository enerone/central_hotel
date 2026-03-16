"""Booking service layer.

Availability rules:
  - Room must be is_active=True
  - check_out > check_in
  - No overlapping confirmed bookings (status != 'canceled')
  - Also blocks: PENDING bookings with a non-null stripe_payment_intent_id (pro plan hold)
  - No RoomAvailability records with is_blocked=True for any night in the range

Overlap condition (half-open intervals):
  existing.check_in < new.check_out AND existing.check_out > new.check_in
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking
from app.hotels.models import Promotion, Room
from app.hotels.service import get_blocked_dates_in_range


async def is_room_available(
    db: AsyncSession,
    room_id: uuid.UUID,
    check_in: date,
    check_out: date,
) -> bool:
    """Return True if the room is available for the given date range."""
    if check_out <= check_in:
        return False

    # 1. Room must be active
    room_result = await db.execute(select(Room).where(Room.id == room_id))
    room = room_result.scalar_one_or_none()
    if room is None or not room.is_active:
        return False

    # 2. Check for overlapping active bookings
    # Blocks: confirmed bookings + pending bookings with a payment_intent (pro plan hold)
    overlap_filter = and_(
        Booking.room_id == room_id,
        Booking.check_in < check_out,
        Booking.check_out > check_in,
        or_(
            Booking.status == "confirmed",
            and_(
                Booking.status == "pending",
                Booking.stripe_payment_intent_id.isnot(None),
            ),
        ),
    )
    booking_result = await db.execute(
        select(Booking.id).where(overlap_filter).limit(1)
    )
    if booking_result.scalar_one_or_none() is not None:
        return False

    # 3. Check for manual blocks in RoomAvailability
    blocked = await get_blocked_dates_in_range(db, room_id, check_in, check_out)
    if blocked:
        return False

    return True


async def calculate_total_price(
    db: AsyncSession,
    room: Room,
    check_in: date,
    check_out: date,
    promotion_id: uuid.UUID | None,
    promotions_enabled: bool,
) -> Decimal:
    """Calculate total price applying promotion if valid.

    Rules:
    - Base: room.base_price * nights
    - Promotion applied only if: promotions_enabled=True, promotion_id provided,
      promotion is active, dates are within valid_from/valid_until,
      and nights >= min_nights.
    - Silently ignore promotion if any condition fails.
    """
    nights = (check_out - check_in).days
    base_total = room.base_price * nights

    if not promotions_enabled or promotion_id is None:
        return base_total

    promo_result = await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )
    promo = promo_result.scalar_one_or_none()

    if promo is None or not promo.is_active:
        return base_total

    # Check date validity: check_in must fall within promotion window
    if not (promo.valid_from <= check_in <= promo.valid_until):
        return base_total

    # Check min_nights
    if nights < promo.min_nights:
        return base_total

    # Apply discount
    if promo.discount_type == "percent":
        discount = (base_total * promo.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        return base_total - discount
    elif promo.discount_type == "fixed":
        discounted = base_total - promo.discount_value
        return max(Decimal("0.00"), discounted)

    return base_total
