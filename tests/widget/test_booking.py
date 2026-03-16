"""Tests for widget booking creation endpoints (POST /w/{slug}/book etc.)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.billing.helpers import make_active_sub_for_user
from tests.billing.factories import make_plan


@pytest.fixture
async def widget_setup(db_session: AsyncSession):
    """Published property + active sub + 1 room + 1 rental item + 1 amenity item."""
    from app.auth.models import User
    from app.hotels.models import Property, Room
    from tests.rentals.factories import make_rental_item
    from tests.amenities.factories import make_amenity_item
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"book-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Booking Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(
        db_session, user.id,
        plan_kwargs={"id": 9910, "name": "widget_basic", "online_payments": False, "auto_confirm": False},
    )

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"book-hotel-{uuid.uuid4().hex[:8]}",
        name="Book Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=False,
        widget_config={
            "sections": {
                "rooms": {"enabled": True},
                "rentals": {"enabled": True},
                "amenities": {"enabled": True},
            }
        },
    )
    db_session.add(prop)
    await db_session.flush()

    room = Room(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "Suite", "en": "Suite"},
        description={"es": "Desc", "en": "Desc"},
        capacity=2,
        base_price=Decimal("100.00"),
        amenities=[],
        is_active=True,
    )
    db_session.add(room)

    rental_item = make_rental_item(property_id=prop.id, quantity_available=3)
    db_session.add(rental_item)

    amenity_item = make_amenity_item(property_id=prop.id, daily_capacity=10)
    db_session.add(amenity_item)

    await db_session.flush()
    return prop, room, rental_item, amenity_item


# ── Room booking ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_book_room_basic_plan(async_client: AsyncClient, widget_setup):
    prop, room, _, _ = widget_setup
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    resp = await async_client.post(
        f"/w/{prop.slug}/book",
        json={
            "room_id": str(room.id),
            "guest_name": "Ana García",
            "guest_email": "ana@example.com",
            "check_in": str(check_in),
            "check_out": str(check_out),
            "adults": 2,
            "children": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "booking_id" in data
    assert data["status"] == "pending"
    assert data.get("payment_intent_client_secret") is None


@pytest.mark.asyncio
async def test_book_room_422_when_unavailable(async_client: AsyncClient, widget_setup, db_session):
    """Second booking for same room/dates returns 422."""
    from tests.bookings.factories import make_booking
    prop, room, _, _ = widget_setup
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    # Pre-book the room
    existing = make_booking(property_id=prop.id, room_id=room.id, check_in=check_in, check_out=check_out, status="confirmed")
    db_session.add(existing)
    await db_session.flush()

    resp = await async_client.post(
        f"/w/{prop.slug}/book",
        json={
            "room_id": str(room.id),
            "guest_name": "Bob",
            "guest_email": "bob@example.com",
            "check_in": str(check_in),
            "check_out": str(check_out),
            "adults": 1,
            "children": 0,
        },
    )
    assert resp.status_code == 422


# ── Rental booking ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_book_rental(async_client: AsyncClient, widget_setup):
    prop, _, rental_item, _ = widget_setup
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    resp = await async_client.post(
        f"/w/{prop.slug}/rentals/book",
        json={
            "rental_item_id": str(rental_item.id),
            "guest_name": "Carol",
            "guest_email": "carol@example.com",
            "check_in": str(check_in),
            "check_out": str(check_out),
            "quantity": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "booking_id" in data
    assert data["status"] == "pending"


# ── Amenity booking ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_book_amenity(async_client: AsyncClient, widget_setup):
    prop, _, _, amenity_item = widget_setup
    booking_date = date.today() + timedelta(days=3)
    resp = await async_client.post(
        f"/w/{prop.slug}/amenities/book",
        json={
            "amenity_item_id": str(amenity_item.id),
            "guest_name": "Dave",
            "guest_email": "dave@example.com",
            "date": str(booking_date),
            "quantity": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "booking_id" in data
    assert data["status"] == "pending"


# ── embed.js ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_js_returns_javascript(async_client: AsyncClient, widget_setup):
    prop, _, _, _ = widget_setup
    resp = await async_client.get(f"/w/{prop.slug}/embed.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert prop.slug in resp.text


@pytest.mark.asyncio
async def test_rentals_embed_js(async_client: AsyncClient, widget_setup):
    prop, _, _, _ = widget_setup
    resp = await async_client.get(f"/w/{prop.slug}/rentals/embed.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
