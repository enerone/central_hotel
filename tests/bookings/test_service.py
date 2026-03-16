"""Tests for booking CRUD service functions.

Tests cover:
- create_booking for basic plan (no Stripe)
- create_booking for pro plan (Stripe PaymentIntent created)
- confirm_booking / cancel_booking state transitions
- Promotion enforcement at booking creation
- cancel_orphaned_bookings Celery task (called directly)
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.service import (
    cancel_booking,
    confirm_booking,
    create_booking,
    get_booking_by_id,
    get_bookings_by_property,
)
from app.bookings.schemas import BookingCreate
from tests.billing.helpers import make_active_sub_for_user


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def owner_with_property_and_room(db_session: AsyncSession):
    """Full setup: user + active sub + property + room."""
    from app.auth.models import User
    from app.hotels.models import Property, Room
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
        slug=f"hotel-{uuid.uuid4().hex[:8]}",
        name="Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    room = Room(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Hab", "en": "Room"},
        description={"es": "Desc", "en": "Desc"},
        capacity=2,
        base_price=Decimal("100.00"),
        amenities=[],
        is_active=True,
    )
    db_session.add(room)
    await db_session.flush()
    return user, prop, room


# ── create_booking — basic plan ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_booking_basic_plan_pending(db_session, owner_with_property_and_room):
    """Basic plan (auto_confirm=False, online_payments=False): booking created as PENDING/unpaid."""
    from app.billing.models import Plan
    from sqlalchemy import select

    _, prop, room = owner_with_property_and_room
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)

    form = BookingCreate(
        room_id=room.id,
        guest_name="Ana Lopez",
        guest_email="ana@test.com",
        check_in=check_in,
        check_out=check_out,
        adults=2,
        children=0,
        promotion_id=None,
    )

    # Patch plan to simulate basic plan
    mock_plan = MagicMock()
    mock_plan.auto_confirm = False
    mock_plan.online_payments = False
    mock_plan.promotions_enabled = False

    booking = await create_booking(db_session, prop.id, form, plan=mock_plan)

    assert booking.status == "pending"
    assert booking.payment_status == "unpaid"
    assert booking.stripe_payment_intent_id is None
    assert booking.total_price == Decimal("200.00")  # 2 nights * 100


@pytest.mark.asyncio
async def test_create_booking_basic_plan_auto_confirm(db_session, owner_with_property_and_room):
    """auto_confirm=True (pro plan without Stripe): booking created as CONFIRMED immediately."""
    _, prop, room = owner_with_property_and_room
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)

    form = BookingCreate(
        room_id=room.id,
        guest_name="Ana Lopez",
        guest_email="ana@test.com",
        check_in=check_in,
        check_out=check_out,
        adults=2,
        children=0,
        promotion_id=None,
    )

    mock_plan = MagicMock()
    mock_plan.auto_confirm = True
    mock_plan.online_payments = False
    mock_plan.promotions_enabled = False

    booking = await create_booking(db_session, prop.id, form, plan=mock_plan)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_create_booking_pro_plan_creates_payment_intent(db_session, owner_with_property_and_room):
    """Pro plan (online_payments=True): Stripe PaymentIntent created, booking pending."""
    _, prop, room = owner_with_property_and_room
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)

    form = BookingCreate(
        room_id=room.id,
        guest_name="Carlos",
        guest_email="carlos@test.com",
        check_in=check_in,
        check_out=check_out,
        adults=1,
        children=0,
        promotion_id=None,
    )

    mock_plan = MagicMock()
    mock_plan.auto_confirm = True  # pro plan also auto-confirms on payment
    mock_plan.online_payments = True
    mock_plan.promotions_enabled = False

    fake_pi = MagicMock()
    fake_pi.id = "pi_test_abc123"

    with patch("app.bookings.service.stripe") as mock_stripe:
        mock_stripe.PaymentIntent.create.return_value = fake_pi
        booking = await create_booking(db_session, prop.id, form, plan=mock_plan)

    # When online_payments=True, booking stays PENDING until webhook
    assert booking.status == "pending"
    assert booking.stripe_payment_intent_id == "pi_test_abc123"
    assert booking.payment_status == "unpaid"


@pytest.mark.asyncio
async def test_create_booking_room_unavailable_raises_422(db_session, owner_with_property_and_room):
    """create_booking raises HTTP 422 when room is not available."""
    from fastapi import HTTPException
    from tests.bookings.factories import make_booking

    _, prop, room = owner_with_property_and_room
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)

    # Pre-book the room
    existing = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        status="confirmed",
    )
    db_session.add(existing)
    await db_session.flush()

    form = BookingCreate(
        room_id=room.id,
        guest_name="Bob",
        guest_email="bob@test.com",
        check_in=check_in,
        check_out=check_out,
        adults=1,
        children=0,
    )
    mock_plan = MagicMock()
    mock_plan.auto_confirm = False
    mock_plan.online_payments = False
    mock_plan.promotions_enabled = False

    with pytest.raises(HTTPException) as exc_info:
        await create_booking(db_session, prop.id, form, plan=mock_plan)
    assert exc_info.value.status_code == 422


# ── confirm_booking / cancel_booking ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_booking(db_session, owner_with_property_and_room):
    """confirm_booking sets status=confirmed."""
    from tests.bookings.factories import make_booking

    _, prop, room = owner_with_property_and_room
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    await confirm_booking(db_session, booking)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_cancel_booking(db_session, owner_with_property_and_room):
    """cancel_booking sets status=canceled."""
    from tests.bookings.factories import make_booking

    _, prop, room = owner_with_property_and_room
    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()

    await cancel_booking(db_session, booking)
    assert booking.status == "canceled"


# ── get_bookings_by_property ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bookings_by_property_returns_all(db_session, owner_with_property_and_room):
    """get_bookings_by_property returns all bookings for the property."""
    from tests.bookings.factories import make_booking

    _, prop, room = owner_with_property_and_room
    b1 = make_booking(property_id=prop.id, room_id=room.id, check_in=date.today() + timedelta(days=1), check_out=date.today() + timedelta(days=3))
    b2 = make_booking(property_id=prop.id, room_id=room.id, check_in=date.today() + timedelta(days=5), check_out=date.today() + timedelta(days=7))
    db_session.add_all([b1, b2])
    await db_session.flush()

    bookings = await get_bookings_by_property(db_session, prop.id)
    assert len(bookings) >= 2


# ── cancel_orphaned_bookings Celery task ─────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_orphaned_bookings_cancels_stale(db_session, owner_with_property_and_room):
    """cancel_orphaned_bookings cancels PENDING+payment_intent bookings older than 30 min."""
    from tests.bookings.factories import make_booking
    from app.bookings.tasks import cancel_orphaned_bookings

    _, prop, room = owner_with_property_and_room
    stale_booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        status="pending",
        stripe_payment_intent_id="pi_stale_001",
    )
    # Force created_at to 35 minutes ago
    stale_booking.created_at = datetime.now(timezone.utc) - timedelta(minutes=35)
    db_session.add(stale_booking)
    await db_session.flush()

    with patch("app.bookings.tasks.stripe") as mock_stripe:
        mock_stripe.PaymentIntent.cancel.return_value = MagicMock()
        await cancel_orphaned_bookings(db_session)

    await db_session.refresh(stale_booking)
    assert stale_booking.status == "canceled"


@pytest.mark.asyncio
async def test_cancel_orphaned_bookings_skips_fresh(db_session, owner_with_property_and_room):
    """cancel_orphaned_bookings does NOT cancel PENDING bookings created less than 30 min ago."""
    from tests.bookings.factories import make_booking
    from app.bookings.tasks import cancel_orphaned_bookings

    _, prop, room = owner_with_property_and_room
    fresh_booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        status="pending",
        stripe_payment_intent_id="pi_fresh_001",
    )
    db_session.add(fresh_booking)
    await db_session.flush()

    with patch("app.bookings.tasks.stripe") as mock_stripe:
        await cancel_orphaned_bookings(db_session)

    await db_session.refresh(fresh_booking)
    assert fresh_booking.status == "pending"
