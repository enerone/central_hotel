"""Tests for is_amenity_available and calculate_amenity_price.

All tests use real DB (no mocking). Per-test transaction rollback via conftest.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.amenities.service import calculate_amenity_price, is_amenity_available
from tests.amenities.factories import make_amenity_booking, make_amenity_item
from tests.billing.helpers import make_active_sub_for_user


@pytest.fixture
async def user_with_sub(db_session: AsyncSession):
    from app.auth.models import User
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Test Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)
    return user


@pytest.fixture
async def prop_and_amenity(db_session: AsyncSession, user_with_sub):
    from app.hotels.models import Property

    prop = Property(
        id=uuid.uuid4(),
        user_id=user_with_sub.id,
        slug=f"test-prop-{uuid.uuid4().hex[:8]}",
        name="Test Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    item = make_amenity_item(property_id=prop.id, daily_capacity=10)
    db_session.add(item)
    await db_session.flush()
    return prop, item


@pytest.mark.asyncio
async def test_amenity_available_when_no_bookings(db_session, prop_and_amenity):
    """Amenity with no bookings is available."""
    _, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=5)
    assert result is True


@pytest.mark.asyncio
async def test_amenity_unavailable_when_capacity_full(db_session, prop_and_amenity):
    """Unavailable when daily capacity is reached."""
    prop, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=booking_date,
        quantity=10,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=1)
    assert result is False


@pytest.mark.asyncio
async def test_amenity_available_partial_capacity(db_session, prop_and_amenity):
    """Available if requested quantity fits within remaining capacity."""
    prop, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=booking_date,
        quantity=7,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=3)
    assert result is True


@pytest.mark.asyncio
async def test_amenity_unlimited_capacity_always_available(db_session, user_with_sub):
    """Amenity with daily_capacity=None (unlimited) is always available."""
    from app.hotels.models import Property

    prop = Property(
        id=uuid.uuid4(),
        user_id=user_with_sub.id,
        slug=f"test-prop-{uuid.uuid4().hex[:8]}",
        name="Test Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    item = make_amenity_item(property_id=prop.id, daily_capacity=None)
    db_session.add(item)
    await db_session.flush()

    booking_date = date.today() + timedelta(days=5)
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=9999)
    assert result is True


@pytest.mark.asyncio
async def test_amenity_pending_without_intent_blocks(db_session, prop_and_amenity):
    """PENDING amenity bookings without a PI also count toward daily capacity."""
    prop, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=booking_date,
        quantity=10,
        status="pending",
        stripe_payment_intent_id=None,
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=1)
    assert result is False


@pytest.mark.asyncio
async def test_amenity_canceled_does_not_count(db_session, prop_and_amenity):
    """Canceled amenity bookings do not count toward daily capacity."""
    prop, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=booking_date,
        quantity=10,
        status="canceled",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=10)
    assert result is True


@pytest.mark.asyncio
async def test_amenity_different_date_does_not_block(db_session, prop_and_amenity):
    """Bookings on other dates do not affect availability for the requested date."""
    prop, item = prop_and_amenity
    booking_date = date.today() + timedelta(days=5)
    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=booking_date + timedelta(days=1),
        quantity=10,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_amenity_available(db_session, item.id, booking_date, quantity=10)
    assert result is True


# ── calculate_amenity_price tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calculate_amenity_price(db_session, prop_and_amenity):
    """price_per_person * quantity."""
    _, item = prop_and_amenity
    price = await calculate_amenity_price(item, quantity=3)
    assert price == Decimal("60.00")  # 20.00 * 3
