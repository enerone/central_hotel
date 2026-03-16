"""Tests for amenity CRUD service: create, confirm, cancel, list."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.amenities.schemas import AmenityBookingCreate
from app.amenities.service import (
    cancel_amenity_booking,
    confirm_amenity_booking,
    create_amenity_booking,
    get_amenity_bookings_by_property,
    get_amenity_items_by_property,
)
from tests.amenities.factories import make_amenity_item
from tests.billing.factories import make_plan
from tests.billing.helpers import make_active_sub_for_user


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
async def active_amenity(db_session, user_and_prop):
    _, prop = user_and_prop
    item = make_amenity_item(property_id=prop.id, daily_capacity=10)
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.fixture
def basic_plan():
    return make_plan(id=9903, name="basic_amenity_test", online_payments=False, auto_confirm=False)


@pytest.fixture
def pro_plan():
    return make_plan(id=9904, name="pro_amenity_test", online_payments=True, auto_confirm=True)


@pytest.mark.asyncio
async def test_create_amenity_booking_basic(db_session, user_and_prop, active_amenity, basic_plan):
    _, prop = user_and_prop
    booking_date = date.today() + timedelta(days=3)
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Ana",
        guest_email="ana@example.com",
        date=booking_date,
        quantity=2,
    )
    booking = await create_amenity_booking(db_session, prop.id, form, basic_plan)
    assert booking.status == "pending"
    assert booking.stripe_payment_intent_id is None
    assert booking.total_price == Decimal("40.00")  # 20.00 * 2


@pytest.mark.asyncio
async def test_create_amenity_booking_422_when_full(db_session, user_and_prop, active_amenity, basic_plan):
    from fastapi import HTTPException
    _, prop = user_and_prop
    booking_date = date.today() + timedelta(days=3)
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Bob",
        guest_email="bob@example.com",
        date=booking_date,
        quantity=100,  # exceeds daily_capacity=10
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_amenity_booking(db_session, prop.id, form, basic_plan)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_amenity_booking_pro(db_session, user_and_prop, active_amenity, pro_plan):
    _, prop = user_and_prop
    booking_date = date.today() + timedelta(days=3)
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Carol",
        guest_email="carol@example.com",
        date=booking_date,
        quantity=2,
    )
    mock_pi = MagicMock()
    mock_pi.id = "pi_amenity_test_456"
    with patch("app.amenities.service.stripe.PaymentIntent.create", return_value=mock_pi):
        booking = await create_amenity_booking(db_session, prop.id, form, pro_plan)
    assert booking.stripe_payment_intent_id == "pi_amenity_test_456"


@pytest.mark.asyncio
async def test_confirm_amenity_booking(db_session, user_and_prop, active_amenity, basic_plan):
    _, prop = user_and_prop
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Dave",
        guest_email="dave@example.com",
        date=date.today() + timedelta(days=3),
        quantity=1,
    )
    booking = await create_amenity_booking(db_session, prop.id, form, basic_plan)
    confirmed = await confirm_amenity_booking(db_session, booking)
    assert confirmed.status == "confirmed"


@pytest.mark.asyncio
async def test_cancel_amenity_booking(db_session, user_and_prop, active_amenity, basic_plan):
    _, prop = user_and_prop
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Eve",
        guest_email="eve@example.com",
        date=date.today() + timedelta(days=3),
        quantity=1,
    )
    booking = await create_amenity_booking(db_session, prop.id, form, basic_plan)
    canceled = await cancel_amenity_booking(db_session, booking)
    assert canceled.status == "canceled"


@pytest.mark.asyncio
async def test_get_amenity_items_by_property(db_session, user_and_prop, active_amenity):
    _, prop = user_and_prop
    items = await get_amenity_items_by_property(db_session, prop.id)
    assert any(i.id == active_amenity.id for i in items)


@pytest.mark.asyncio
async def test_get_amenity_bookings_by_property(db_session, user_and_prop, active_amenity, basic_plan):
    _, prop = user_and_prop
    form = AmenityBookingCreate(
        amenity_item_id=active_amenity.id,
        guest_name="Frank",
        guest_email="frank@example.com",
        date=date.today() + timedelta(days=3),
        quantity=1,
    )
    await create_amenity_booking(db_session, prop.id, form, basic_plan)
    bookings = await get_amenity_bookings_by_property(db_session, prop.id)
    assert len(bookings) >= 1
