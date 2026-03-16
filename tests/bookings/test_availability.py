"""Tests for is_room_available and calculate_total_price.

All tests use real DB (no mocking). Per-test transaction rollback via conftest.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.service import calculate_total_price, is_room_available
from tests.bookings.factories import make_booking
from tests.billing.factories import make_plan, make_subscription
from tests.billing.helpers import make_active_sub_for_user


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def user_with_sub(db_session: AsyncSession):
    """Create a user with an active subscription."""
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
async def prop_and_room(db_session: AsyncSession, user_with_sub):
    """Create a property and an active room."""
    from app.hotels.models import Property, Room

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

    room = Room(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Habitacion", "en": "Room"},
        description={"es": "Desc", "en": "Desc"},
        capacity=2,
        base_price=Decimal("100.00"),
        amenities=[],
        is_active=True,
    )
    db_session.add(room)
    await db_session.flush()
    return prop, room


# ── is_room_available tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_available_when_no_bookings(db_session, prop_and_room):
    """Room with no bookings and no blocks is available."""
    _, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is True


@pytest.mark.asyncio
async def test_unavailable_when_confirmed_booking_overlaps(db_session, prop_and_room):
    """Room is unavailable when a confirmed booking overlaps the requested dates."""
    prop, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is False


@pytest.mark.asyncio
async def test_available_when_canceled_booking_overlaps(db_session, prop_and_room):
    """Canceled bookings do not block availability."""
    prop, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        status="canceled",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is True


@pytest.mark.asyncio
async def test_pending_without_payment_intent_does_not_block(db_session, prop_and_room):
    """PENDING bookings without a stripe_payment_intent_id do NOT block availability."""
    prop, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        status="pending",
        stripe_payment_intent_id=None,
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is True


@pytest.mark.asyncio
async def test_pending_with_payment_intent_blocks(db_session, prop_and_room):
    """PENDING bookings WITH a stripe_payment_intent_id DO block availability (pro plan hold)."""
    prop, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        status="pending",
        stripe_payment_intent_id="pi_test_123",
    )
    db_session.add(booking)
    await db_session.flush()
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is False


@pytest.mark.asyncio
async def test_unavailable_when_room_availability_blocked(db_session, prop_and_room):
    """Manual RoomAvailability block makes room unavailable."""
    from app.hotels.models import RoomAvailability

    _, room = prop_and_room
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    # Block the first night
    block = RoomAvailability(
        room_id=room.id,
        date=check_in,
        is_blocked=True,
    )
    db_session.add(block)
    await db_session.flush()
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is False


@pytest.mark.asyncio
async def test_unavailable_when_room_inactive(db_session, prop_and_room):
    """Inactive rooms are never available."""
    _, room = prop_and_room
    room.is_active = False
    await db_session.flush()
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    result = await is_room_available(db_session, room.id, check_in, check_out)
    assert result is False


@pytest.mark.asyncio
async def test_check_out_must_be_after_check_in(db_session, prop_and_room):
    """check_out <= check_in returns False immediately."""
    _, room = prop_and_room
    same_day = date.today() + timedelta(days=5)
    result = await is_room_available(db_session, room.id, same_day, same_day)
    assert result is False


@pytest.mark.asyncio
async def test_adjacent_bookings_do_not_overlap(db_session, prop_and_room):
    """A booking check_out date = next booking check_in date does not overlap."""
    prop, room = prop_and_room
    # Existing: nights 10-13
    check_in_a = date.today() + timedelta(days=10)
    check_out_a = check_in_a + timedelta(days=3)
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in_a,
        check_out=check_out_a,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    # New: nights 13-15 (starts exactly when old ends)
    result = await is_room_available(db_session, room.id, check_out_a, check_out_a + timedelta(days=2))
    assert result is True


# ── calculate_total_price tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_base_price_no_promotion(db_session, prop_and_room):
    """Price = base_price * nights when no promotion."""
    _, room = prop_and_room  # base_price = 100.00
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=3)  # 3 nights
    total = await calculate_total_price(db_session, room, check_in, check_out, promotion_id=None, promotions_enabled=False)
    assert total == Decimal("300.00")


@pytest.mark.asyncio
async def test_percent_discount_applied(db_session, prop_and_room):
    """Percent discount promotion reduces total correctly."""
    from app.hotels.models import Promotion
    prop, room = prop_and_room
    promo = Promotion(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Desc", "en": "Discount"},
        discount_type="percent",
        discount_value=Decimal("10"),  # 10%
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        min_nights=2,
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=3)  # 3 nights, base = 300
    total = await calculate_total_price(db_session, room, check_in, check_out, promotion_id=promo.id, promotions_enabled=True)
    assert total == Decimal("270.00")  # 300 - 10%


@pytest.mark.asyncio
async def test_fixed_discount_applied(db_session, prop_and_room):
    """Fixed discount promotion reduces total by flat amount."""
    from app.hotels.models import Promotion
    prop, room = prop_and_room
    promo = Promotion(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Desc", "en": "Discount"},
        discount_type="fixed",
        discount_value=Decimal("50"),
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        min_nights=1,
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)  # 2 nights, base = 200
    total = await calculate_total_price(db_session, room, check_in, check_out, promotion_id=promo.id, promotions_enabled=True)
    assert total == Decimal("150.00")


@pytest.mark.asyncio
async def test_promotion_ignored_when_not_enabled(db_session, prop_and_room):
    """Promotion is silently ignored when promotions_enabled=False."""
    from app.hotels.models import Promotion
    prop, room = prop_and_room
    promo = Promotion(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Desc", "en": "Discount"},
        discount_type="percent",
        discount_value=Decimal("20"),
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        min_nights=1,
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    total = await calculate_total_price(db_session, room, check_in, check_out, promotion_id=promo.id, promotions_enabled=False)
    assert total == Decimal("200.00")  # no discount


@pytest.mark.asyncio
async def test_promotion_not_applied_when_min_nights_not_met(db_session, prop_and_room):
    """Promotion requires min_nights — not applied when stay is shorter."""
    from app.hotels.models import Promotion
    prop, room = prop_and_room
    promo = Promotion(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Desc", "en": "Discount"},
        discount_type="percent",
        discount_value=Decimal("15"),
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        min_nights=5,  # requires 5 nights
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=3)  # only 3 nights
    total = await calculate_total_price(db_session, room, check_in, check_out, promotion_id=promo.id, promotions_enabled=True)
    assert total == Decimal("300.00")  # no discount applied
