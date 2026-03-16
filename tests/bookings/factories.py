"""Test factories for bookings module."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.bookings.models import Booking


def make_booking(
    property_id: uuid.UUID,
    room_id: uuid.UUID,
    check_in: date | None = None,
    check_out: date | None = None,
    status: str = "confirmed",
    payment_status: str = "unpaid",
    stripe_payment_intent_id: str | None = None,
    **kwargs,
) -> Booking:
    today = date.today()
    return Booking(
        id=uuid.uuid4(),
        property_id=property_id,
        room_id=room_id,
        guest_name=kwargs.get("guest_name", "Test Guest"),
        guest_email=kwargs.get("guest_email", "guest@example.com"),
        check_in=check_in or today + timedelta(days=1),
        check_out=check_out or today + timedelta(days=3),
        adults=kwargs.get("adults", 2),
        children=kwargs.get("children", 0),
        total_price=kwargs.get("total_price", Decimal("200.00")),
        currency=kwargs.get("currency", "USD"),
        status=status,
        payment_status=payment_status,
        stripe_payment_intent_id=stripe_payment_intent_id,
        promotion_id=kwargs.get("promotion_id", None),
    )
