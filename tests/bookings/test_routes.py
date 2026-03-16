"""Integration tests for booking dashboard routes.

All tests use real DB + httpx AsyncClient.
Every test that hits dashboard routes must call make_active_sub_for_user.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.billing.helpers import make_active_sub_for_user
from tests.bookings.factories import make_booking


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def auth_client_with_booking(async_client: AsyncClient, db_session: AsyncSession):
    """Authenticated client + property + room + one pending booking."""
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
        name="Hotel Test",
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

    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=date.today() + timedelta(days=5),
        check_out=date.today() + timedelta(days=7),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    # Log in
    resp = await async_client.post(
        "/login",
        data={"email": user.email, "password": "pw"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    return async_client, prop, booking, room


# ── GET /dashboard/properties/{id}/bookings ───────────────────────────────────


@pytest.mark.asyncio
async def test_bookings_list_renders(auth_client_with_booking):
    client, prop, booking, _ = auth_client_with_booking
    resp = await client.get(f"/dashboard/properties/{prop.id}/bookings")
    assert resp.status_code == 200
    assert booking.guest_name in resp.text


@pytest.mark.asyncio
async def test_bookings_list_requires_auth(async_client: AsyncClient, db_session: AsyncSession):
    """Unauthenticated access to bookings list redirects to login."""
    fake_id = uuid.uuid4()
    resp = await async_client.get(f"/dashboard/properties/{fake_id}/bookings", follow_redirects=False)
    assert resp.status_code in (302, 303)


@pytest.mark.asyncio
async def test_bookings_list_404_for_other_user_property(auth_client_with_booking, db_session: AsyncSession):
    """Bookings list returns 404 if the property belongs to a different user."""
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    client, _, _, _ = auth_client_with_booking

    # Create a property belonging to another user
    hashed = bcrypt.hashpw(b"pw2", bcrypt.gensalt()).decode()
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Other",
    )
    db_session.add(other_user)
    await db_session.flush()

    other_prop = Property(
        id=uuid.uuid4(),
        user_id=other_user.id,
        slug=f"other-hotel-{uuid.uuid4().hex[:8]}",
        name="Other Hotel",
        description={"es": "X", "en": "X"},
        currency="USD",
        locale="es",
    )
    db_session.add(other_prop)
    await db_session.flush()

    resp = await client.get(f"/dashboard/properties/{other_prop.id}/bookings")
    assert resp.status_code == 404


# ── POST confirm ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_booking_route(auth_client_with_booking, db_session: AsyncSession):
    """POST confirm changes booking status to confirmed and redirects."""
    client, prop, booking, _ = auth_client_with_booking
    resp = await client.post(
        f"/dashboard/properties/{prop.id}/bookings/{booking.id}/confirm",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_confirm_booking_404_wrong_property(auth_client_with_booking, db_session: AsyncSession):
    """Cannot confirm a booking that belongs to another property."""
    client, _, booking, _ = auth_client_with_booking
    fake_prop_id = uuid.uuid4()
    resp = await client.post(
        f"/dashboard/properties/{fake_prop_id}/bookings/{booking.id}/confirm"
    )
    assert resp.status_code == 404


# ── POST reject ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_booking_route(auth_client_with_booking, db_session: AsyncSession):
    """POST reject changes booking status to canceled."""
    client, prop, booking, _ = auth_client_with_booking
    resp = await client.post(
        f"/dashboard/properties/{prop.id}/bookings/{booking.id}/reject",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "canceled"


# ── POST cancel ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_confirmed_booking_route(auth_client_with_booking, db_session: AsyncSession):
    """POST cancel changes a confirmed booking to canceled."""
    client, prop, booking, _ = auth_client_with_booking
    booking.status = "confirmed"
    await db_session.flush()

    resp = await client.post(
        f"/dashboard/properties/{prop.id}/bookings/{booking.id}/cancel",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "canceled"
