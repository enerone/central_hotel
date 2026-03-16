"""Amenity service layer."""
import uuid
from datetime import date
from decimal import Decimal

import anyio
import stripe
from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amenities.models import AmenityBooking, AmenityItem
from app.amenities.schemas import AmenityBookingCreate
from app.billing.models import Plan
from app.core.config import settings
from app.hotels.models import Property as PropertyModel


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


async def _validate_guest_only_amenity(
    db: AsyncSession,
    room_booking_id: uuid.UUID | None,
    property_id: uuid.UUID,
    booking_date: date,
) -> None:
    """Validate guest_only: room_booking_id must be confirmed, same property,
    and booking_date must fall within [check_in, check_out).
    """
    from app.bookings.models import Booking

    if room_booking_id is None:
        raise HTTPException(
            status_code=422,
            detail="Esta amenidad es solo para huéspedes. Debes proporcionar tu reserva de habitación.",
        )
    result = await db.execute(select(Booking).where(Booking.id == room_booking_id))
    rb = result.scalar_one_or_none()
    if rb is None or rb.property_id != property_id or rb.status != "confirmed":
        raise HTTPException(status_code=422, detail="Reserva de habitación inválida o no confirmada.")
    if not (rb.check_in <= booking_date < rb.check_out):
        raise HTTPException(
            status_code=422,
            detail="La fecha de la amenidad no cae dentro de tu reserva de habitación.",
        )


async def create_amenity_booking(
    db: AsyncSession,
    property_id: uuid.UUID,
    form: AmenityBookingCreate,
    plan: Plan,
) -> AmenityBooking:
    """Create an amenity booking."""
    item_result = await db.execute(
        select(AmenityItem).where(AmenityItem.id == form.amenity_item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Amenidad no encontrada.")

    if item.guest_only:
        await _validate_guest_only_amenity(
            db, form.room_booking_id, property_id, form.date
        )

    available = await is_amenity_available(db, form.amenity_item_id, form.date, form.quantity)
    if not available:
        raise HTTPException(
            status_code=422, detail="La amenidad no tiene capacidad disponible para esa fecha."
        )

    total_price = await calculate_amenity_price(item, form.quantity)

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

    booking = AmenityBooking(
        property_id=property_id,
        amenity_item_id=form.amenity_item_id,
        guest_name=form.guest_name,
        guest_email=form.guest_email,
        room_booking_id=form.room_booking_id,
        date=form.date,
        quantity=form.quantity,
        total_price=total_price,
        currency=currency,
        status="pending",
        payment_status="unpaid",
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
    db.add(booking)
    await db.flush()
    return booking


async def get_amenity_items_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[AmenityItem]:
    result = await db.execute(
        select(AmenityItem)
        .where(AmenityItem.property_id == property_id)
        .order_by(AmenityItem.is_active.desc())
    )
    return list(result.scalars().all())


async def get_amenity_bookings_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[AmenityBooking]:
    result = await db.execute(
        select(AmenityBooking)
        .where(AmenityBooking.property_id == property_id)
        .order_by(AmenityBooking.date.desc(), AmenityBooking.created_at.desc())
    )
    return list(result.scalars().all())


async def get_amenity_booking_by_id(
    db: AsyncSession, booking_id: uuid.UUID
) -> AmenityBooking | None:
    result = await db.execute(
        select(AmenityBooking).where(AmenityBooking.id == booking_id)
    )
    return result.scalar_one_or_none()


async def get_amenity_booking_by_payment_intent(
    db: AsyncSession, stripe_payment_intent_id: str
) -> AmenityBooking | None:
    result = await db.execute(
        select(AmenityBooking).where(
            AmenityBooking.stripe_payment_intent_id == stripe_payment_intent_id
        )
    )
    return result.scalar_one_or_none()


async def confirm_amenity_booking(db: AsyncSession, booking: AmenityBooking) -> AmenityBooking:
    booking.status = "confirmed"
    await db.flush()
    return booking


async def cancel_amenity_booking(db: AsyncSession, booking: AmenityBooking) -> AmenityBooking:
    booking.status = "canceled"
    await db.flush()
    return booking
