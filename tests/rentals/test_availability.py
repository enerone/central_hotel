"""Tests for is_rental_available and calculate_rental_price.

All tests use real DB (no mocking). Per-test transaction rollback via conftest.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rentals.service import calculate_rental_price, is_rental_available
from tests.rentals.factories import make_rental_booking, make_rental_item
from tests.billing.helpers import make_active_sub_for_user


# ── Fixtures ──────────────────────────────────────────────────────────────────


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
async def prop_and_item(db_session: AsyncSession, user_with_sub):
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

    item = make_rental_item(property_id=prop.id, quantity_available=3)
    db_session.add(item)
    await db_session.flush()
    return prop, item


# ── is_rental_available tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rental_available_when_no_bookings(db_session, prop_and_item):
    """Item with no bookings is available for any quantity <= quantity_available."""
    _, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=2)
    assert result is True


@pytest.mark.asyncio
async def test_rental_unavailable_when_fully_booked(db_session, prop_and_item):
    """Unavailable when existing confirmed bookings use all units."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    # Fill all 3 units
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_out,
        quantity=3,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=1)
    assert result is False


@pytest.mark.asyncio
async def test_rental_available_when_partial_units_free(db_session, prop_and_item):
    """Available if requested quantity fits within remaining inventory."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_out,
        quantity=2,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    # 1 unit still free
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=1)
    assert result is True


@pytest.mark.asyncio
async def test_rental_canceled_booking_does_not_block(db_session, prop_and_item):
    """Canceled bookings do not count toward used inventory."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_out,
        quantity=3,
        status="canceled",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=3)
    assert result is True


@pytest.mark.asyncio
async def test_rental_pending_blocks_regardless_of_payment_intent(db_session, prop_and_item):
    """PENDING bookings (basic plan, no PI) also block inventory — spec: status != canceled."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_out,
        quantity=3,
        status="pending",
        stripe_payment_intent_id=None,  # basic plan, no PaymentIntent
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=1)
    assert result is False


@pytest.mark.asyncio
async def test_rental_pending_with_intent_blocks(db_session, prop_and_item):
    """PENDING bookings with a payment_intent also block inventory."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_out,
        quantity=3,
        status="pending",
        stripe_payment_intent_id="pi_test_123",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=1)
    assert result is False


@pytest.mark.asyncio
async def test_rental_non_overlapping_dates_do_not_block(db_session, prop_and_item):
    """Bookings for non-overlapping dates do not affect availability."""
    prop, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    # Book completely different dates
    other_booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in + timedelta(days=10),
        check_out=check_in + timedelta(days=15),
        quantity=3,
        status="confirmed",
    )
    db_session.add(other_booking)
    await db_session.flush()
    result = await is_rental_available(db_session, item.id, check_in, check_out, quantity=3)
    assert result is True


# ── calculate_rental_price tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calculate_rental_price_basic(db_session, prop_and_item):
    """price_per_day * nights * quantity."""
    _, item = prop_and_item
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)  # 3 nights
    price = await calculate_rental_price(item, check_in, check_out, quantity=2)
    assert price == Decimal("300.00")  # 50.00 * 3 * 2
