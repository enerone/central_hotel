"""Tests for rental CRUD service: create, confirm, cancel, list."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rentals.schemas import RentalBookingCreate
from app.rentals.service import (
    cancel_rental_booking,
    confirm_rental_booking,
    create_rental_booking,
    get_rental_bookings_by_property,
    get_rental_items_by_property,
)
from tests.rentals.factories import make_rental_item
from tests.billing.factories import make_plan
from tests.billing.helpers import make_active_sub_for_user


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def user_and_prop(db_session: AsyncSession):
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"prop-{uuid.uuid4().hex[:8]}",
        name="Test Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()
    return user, prop


@pytest.fixture
async def active_item(db_session: AsyncSession, user_and_prop):
    _, prop = user_and_prop
    item = make_rental_item(property_id=prop.id, quantity_available=3)
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.fixture
def basic_plan():
    return make_plan(
        id=9901,
        name="basic_rental_test",
        online_payments=False,
        auto_confirm=False,
        promotions_enabled=False,
    )


@pytest.fixture
def pro_plan():
    return make_plan(
        id=9902,
        name="pro_rental_test",
        online_payments=True,
        auto_confirm=True,
        promotions_enabled=True,
    )


# ── create_rental_booking tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_rental_booking_basic_plan(db_session, user_and_prop, active_item, basic_plan):
    """Basic plan creates a PENDING rental booking without Stripe."""
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Ana",
        guest_email="ana@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=1,
    )
    booking = await create_rental_booking(db_session, prop.id, form, basic_plan)
    assert booking.status == "pending"
    assert booking.stripe_payment_intent_id is None
    assert booking.total_price == Decimal("100.00")  # 50.00 * 2 days * 1


@pytest.mark.asyncio
async def test_create_rental_booking_422_when_unavailable(db_session, user_and_prop, active_item, basic_plan):
    """Raises 422 if no units available."""
    from fastapi import HTTPException
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Ana",
        guest_email="ana@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=10,  # exceeds quantity_available=3
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_rental_booking(db_session, prop.id, form, basic_plan)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_rental_booking_pro_plan(db_session, user_and_prop, active_item, pro_plan):
    """Pro plan creates a PENDING booking with a Stripe PaymentIntent."""
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Bob",
        guest_email="bob@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=1,
    )
    mock_pi = MagicMock()
    mock_pi.id = "pi_rental_test_123"
    with patch("app.rentals.service.stripe.PaymentIntent.create", return_value=mock_pi):
        booking = await create_rental_booking(db_session, prop.id, form, pro_plan)
    assert booking.status == "pending"
    assert booking.stripe_payment_intent_id == "pi_rental_test_123"


# ── confirm / cancel tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_rental_booking(db_session, user_and_prop, active_item, basic_plan):
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Carol",
        guest_email="carol@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=1,
    )
    booking = await create_rental_booking(db_session, prop.id, form, basic_plan)
    confirmed = await confirm_rental_booking(db_session, booking)
    assert confirmed.status == "confirmed"


@pytest.mark.asyncio
async def test_cancel_rental_booking(db_session, user_and_prop, active_item, basic_plan):
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Dave",
        guest_email="dave@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=1,
    )
    booking = await create_rental_booking(db_session, prop.id, form, basic_plan)
    canceled = await cancel_rental_booking(db_session, booking)
    assert canceled.status == "canceled"


# ── list tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_rental_items_by_property(db_session, user_and_prop, active_item):
    _, prop = user_and_prop
    items = await get_rental_items_by_property(db_session, prop.id)
    assert len(items) >= 1
    assert any(i.id == active_item.id for i in items)


@pytest.mark.asyncio
async def test_get_rental_bookings_by_property(db_session, user_and_prop, active_item, basic_plan):
    _, prop = user_and_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    form = RentalBookingCreate(
        rental_item_id=active_item.id,
        guest_name="Eve",
        guest_email="eve@example.com",
        check_in=check_in,
        check_out=check_out,
        quantity=1,
    )
    await create_rental_booking(db_session, prop.id, form, basic_plan)
    bookings = await get_rental_bookings_by_property(db_session, prop.id)
    assert len(bookings) >= 1
