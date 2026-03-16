"""Test factories for amenities module."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.amenities.models import AmenityBooking, AmenityItem


def make_amenity_item(
    property_id: uuid.UUID,
    daily_capacity: int | None = 10,
    price_per_person: Decimal = Decimal("20.00"),
    guest_only: bool = False,
    is_active: bool = True,
    **kwargs,
) -> AmenityItem:
    return AmenityItem(
        id=uuid.uuid4(),
        property_id=property_id,
        name=kwargs.get("name", {"es": "Piscina", "en": "Pool"}),
        description=kwargs.get("description", {"es": "Desc", "en": "Desc"}),
        photos=kwargs.get("photos", []),
        price_per_person=price_per_person,
        daily_capacity=daily_capacity,
        guest_only=guest_only,
        is_active=is_active,
    )


def make_amenity_booking(
    property_id: uuid.UUID,
    amenity_item_id: uuid.UUID,
    booking_date: date | None = None,
    quantity: int = 2,
    status: str = "confirmed",
    payment_status: str = "unpaid",
    stripe_payment_intent_id: str | None = None,
    room_booking_id: uuid.UUID | None = None,
    **kwargs,
) -> AmenityBooking:
    today = date.today()
    return AmenityBooking(
        id=uuid.uuid4(),
        property_id=property_id,
        amenity_item_id=amenity_item_id,
        guest_name=kwargs.get("guest_name", "Test Guest"),
        guest_email=kwargs.get("guest_email", "guest@example.com"),
        room_booking_id=room_booking_id,
        date=booking_date or today + timedelta(days=1),
        quantity=quantity,
        total_price=kwargs.get("total_price", Decimal("40.00")),
        currency=kwargs.get("currency", "USD"),
        status=status,
        payment_status=payment_status,
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
