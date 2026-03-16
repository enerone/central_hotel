"""Rental service layer.

Availability rule for rentals:
  SUM(quantity of active bookings overlapping the date range) must be < item.quantity_available.
  Active = all bookings where status != canceled.
  Overlap (half-open): existing.check_in < new.check_out AND existing.check_out > new.check_in.
"""
import uuid
from datetime import date
from decimal import Decimal

import anyio
import stripe
from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Plan
from app.core.config import settings
from app.hotels.models import Property as PropertyModel
from app.rentals.models import RentalBooking, RentalItem
from app.rentals.schemas import RentalBookingCreate


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


async def _validate_guest_only(
    db: AsyncSession,
    room_booking_id: uuid.UUID | None,
    property_id: uuid.UUID,
    check_in: date,
    check_out: date,
) -> None:
    """Validate guest_only constraint: room_booking_id must be confirmed,
    same property, and date range must overlap.
    Raises HTTP 422 on failure.
    """
    from app.bookings.models import Booking

    if room_booking_id is None:
        raise HTTPException(
            status_code=422,
            detail="Este ítem es solo para huéspedes. Debes proporcionar tu reserva de habitación.",
        )
    result = await db.execute(
        select(Booking).where(Booking.id == room_booking_id)
    )
    rb = result.scalar_one_or_none()
    if rb is None or rb.property_id != property_id or rb.status != "confirmed":
        raise HTTPException(status_code=422, detail="Reserva de habitación inválida o no confirmada.")
    # Rental range must overlap with room booking range
    if not (rb.check_in < check_out and rb.check_out > check_in):
        raise HTTPException(
            status_code=422,
            detail="Las fechas del alquiler no coinciden con tu reserva de habitación.",
        )


async def create_rental_booking(
    db: AsyncSession,
    property_id: uuid.UUID,
    form: RentalBookingCreate,
    plan: Plan,
) -> RentalBooking:
    """Create a rental booking, enforcing availability and plan rules."""
    # Load item
    item_result = await db.execute(
        select(RentalItem).where(RentalItem.id == form.rental_item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Ítem de alquiler no encontrado.")

    # guest_only check
    if item.guest_only:
        await _validate_guest_only(
            db, form.room_booking_id, property_id, form.check_in, form.check_out
        )

    available = await is_rental_available(
        db, form.rental_item_id, form.check_in, form.check_out, form.quantity
    )
    if not available:
        raise HTTPException(
            status_code=422, detail="El ítem no está disponible para esas fechas y cantidad."
        )

    total_price = await calculate_rental_price(item, form.check_in, form.check_out, form.quantity)

    # Load property for currency
    prop_result = await db.execute(
        select(PropertyModel).where(PropertyModel.id == property_id)
    )
    prop = prop_result.scalar_one_or_none()
    currency = prop.currency if prop else "USD"

    stripe_payment_intent_id: str | None = None
    if plan.online_payments:
        stripe.api_key = settings.stripe_secret_key
        amount_cents = int(total_price * 100)

        def _create_pi():
            return stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata={"property_id": str(property_id)},
            )

        pi = await anyio.to_thread.run_sync(_create_pi)
        stripe_payment_intent_id = pi.id

    initial_status = "pending"

    booking = RentalBooking(
        property_id=property_id,
        rental_item_id=form.rental_item_id,
        guest_name=form.guest_name,
        guest_email=form.guest_email,
        room_booking_id=form.room_booking_id,
        check_in=form.check_in,
        check_out=form.check_out,
        quantity=form.quantity,
        total_price=total_price,
        currency=currency,
        status=initial_status,
        payment_status="unpaid",
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
    db.add(booking)
    await db.flush()
    return booking


async def get_rental_items_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[RentalItem]:
    result = await db.execute(
        select(RentalItem)
        .where(RentalItem.property_id == property_id)
        .order_by(RentalItem.is_active.desc())
    )
    return list(result.scalars().all())


async def get_rental_bookings_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[RentalBooking]:
    result = await db.execute(
        select(RentalBooking)
        .where(RentalBooking.property_id == property_id)
        .order_by(RentalBooking.check_in.desc(), RentalBooking.created_at.desc())
    )
    return list(result.scalars().all())


async def get_rental_booking_by_id(
    db: AsyncSession, booking_id: uuid.UUID
) -> RentalBooking | None:
    result = await db.execute(
        select(RentalBooking).where(RentalBooking.id == booking_id)
    )
    return result.scalar_one_or_none()


async def get_rental_booking_by_payment_intent(
    db: AsyncSession, stripe_payment_intent_id: str
) -> RentalBooking | None:
    result = await db.execute(
        select(RentalBooking).where(
            RentalBooking.stripe_payment_intent_id == stripe_payment_intent_id
        )
    )
    return result.scalar_one_or_none()


async def confirm_rental_booking(db: AsyncSession, booking: RentalBooking) -> RentalBooking:
    booking.status = "confirmed"
    await db.flush()
    return booking


async def cancel_rental_booking(db: AsyncSession, booking: RentalBooking) -> RentalBooking:
    booking.status = "canceled"
    await db.flush()
    return booking
