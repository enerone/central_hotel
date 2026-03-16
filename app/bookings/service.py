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

import anyio
import stripe
from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Plan
from app.bookings.models import Booking
from app.bookings.schemas import BookingCreate
from app.core.config import settings
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


async def create_booking(
    db: AsyncSession,
    property_id: uuid.UUID,
    form: BookingCreate,
    plan: Plan,
) -> Booking:
    """Create a booking, enforcing availability and plan rules.

    Plan enforcement:
    - promotions_enabled: if False, promotion_id is silently ignored
    - online_payments: if True, creates a Stripe PaymentIntent (anyio.to_thread.run_sync)
    - auto_confirm: if True AND online_payments is False, sets status=confirmed immediately
      (when online_payments=True, confirmation happens via webhook)

    Raises HTTP 422 if room is not available.
    """
    available = await is_room_available(db, form.room_id, form.check_in, form.check_out)
    if not available:
        raise HTTPException(status_code=422, detail="La habitación no está disponible para esas fechas.")

    # Load room for price calculation
    room_result = await db.execute(select(Room).where(Room.id == form.room_id))
    room = room_result.scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Habitación no encontrada.")

    # Always load property for currency
    from app.hotels.models import Property as PropertyModel
    prop_result = await db.execute(
        select(PropertyModel).where(PropertyModel.id == property_id)
    )
    prop = prop_result.scalar_one_or_none()
    prop_currency = (prop.currency if prop else "USD")

    total_price = await calculate_total_price(
        db,
        room,
        form.check_in,
        form.check_out,
        promotion_id=form.promotion_id,
        promotions_enabled=plan.promotions_enabled,
    )

    # Determine promotion_id to store (silently ignore if plan doesn't allow)
    stored_promotion_id = form.promotion_id if plan.promotions_enabled else None

    stripe_payment_intent_id: str | None = None

    if plan.online_payments:
        stripe.api_key = settings.stripe_secret_key
        amount_cents = int(total_price * 100)

        def _create_pi():
            return stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=prop_currency.lower(),
                metadata={"property_id": str(property_id)},
            )

        pi = await anyio.to_thread.run_sync(_create_pi)
        stripe_payment_intent_id = pi.id

    # Determine initial status
    if plan.online_payments:
        # Pro plan: stay PENDING until payment_intent.succeeded webhook
        initial_status = "pending"
    elif plan.auto_confirm:
        initial_status = "confirmed"
    else:
        initial_status = "pending"

    booking = Booking(
        property_id=property_id,
        room_id=form.room_id,
        guest_name=form.guest_name,
        guest_email=form.guest_email,
        check_in=form.check_in,
        check_out=form.check_out,
        adults=form.adults,
        children=form.children,
        total_price=total_price,
        currency=prop_currency,
        status=initial_status,
        payment_status="unpaid",
        stripe_payment_intent_id=stripe_payment_intent_id,
        promotion_id=stored_promotion_id,
    )
    db.add(booking)
    await db.flush()
    return booking


async def get_bookings_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Booking]:
    """Return all bookings for a property, ordered by check_in descending."""
    result = await db.execute(
        select(Booking)
        .where(Booking.property_id == property_id)
        .order_by(Booking.check_in.desc(), Booking.created_at.desc())
    )
    return list(result.scalars().all())


async def get_booking_by_id(
    db: AsyncSession, booking_id: uuid.UUID
) -> Booking | None:
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    return result.scalar_one_or_none()


async def get_booking_by_payment_intent(
    db: AsyncSession, stripe_payment_intent_id: str
) -> Booking | None:
    """Look up booking by stripe_payment_intent_id for webhook processing."""
    result = await db.execute(
        select(Booking).where(
            Booking.stripe_payment_intent_id == stripe_payment_intent_id
        )
    )
    return result.scalar_one_or_none()


async def confirm_booking(db: AsyncSession, booking: Booking) -> Booking:
    """Set booking status to confirmed."""
    booking.status = "confirmed"
    await db.flush()
    return booking


async def cancel_booking(db: AsyncSession, booking: Booking) -> Booking:
    """Set booking status to canceled."""
    booking.status = "canceled"
    await db.flush()
    return booking
