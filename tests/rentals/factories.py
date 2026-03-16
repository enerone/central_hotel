"""Test factories for rentals module."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.rentals.models import RentalBooking, RentalItem


def make_rental_item(
    property_id: uuid.UUID,
    quantity_available: int = 3,
    price_per_day: Decimal = Decimal("50.00"),
    guest_only: bool = False,
    is_active: bool = True,
    **kwargs,
) -> RentalItem:
    return RentalItem(
        id=uuid.uuid4(),
        property_id=property_id,
        name=kwargs.get("name", {"es": "Bicicleta", "en": "Bicycle"}),
        description=kwargs.get("description", {"es": "Desc", "en": "Desc"}),
        photos=kwargs.get("photos", []),
        price_per_day=price_per_day,
        quantity_available=quantity_available,
        guest_only=guest_only,
        is_active=is_active,
    )


def make_rental_booking(
    property_id: uuid.UUID,
    rental_item_id: uuid.UUID,
    check_in: date | None = None,
    check_out: date | None = None,
    quantity: int = 1,
    status: str = "confirmed",
    payment_status: str = "unpaid",
    stripe_payment_intent_id: str | None = None,
    room_booking_id: uuid.UUID | None = None,
    **kwargs,
) -> RentalBooking:
    today = date.today()
    return RentalBooking(
        id=uuid.uuid4(),
        property_id=property_id,
        rental_item_id=rental_item_id,
        guest_name=kwargs.get("guest_name", "Test Guest"),
        guest_email=kwargs.get("guest_email", "guest@example.com"),
        room_booking_id=room_booking_id,
        check_in=check_in or today + timedelta(days=1),
        check_out=check_out or today + timedelta(days=3),
        quantity=quantity,
        total_price=kwargs.get("total_price", Decimal("100.00")),
        currency=kwargs.get("currency", "USD"),
        status=status,
        payment_status=payment_status,
        stripe_payment_intent_id=stripe_payment_intent_id,
    )
