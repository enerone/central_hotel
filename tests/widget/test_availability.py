"""Tests for widget availability endpoints.

All use real DB + httpx. No auth required (public routes).
Plan enforcement (402) and section gating (404) are tested here.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.billing.helpers import make_active_sub_for_user
from tests.billing.factories import make_plan, make_subscription


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def published_prop(db_session: AsyncSession):
    """A published property with an active subscription, 1 active room."""
    from app.auth.models import User
    from app.hotels.models import Property, Room
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"widget-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Widget Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"hotel-{uuid.uuid4().hex[:8]}",
        name="Widget Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=False,
        widget_config={
            "primary_color": "#3B82F6",
            "sections": {
                "rooms": {"enabled": True, "standalone": False},
                "rentals": {"enabled": True, "standalone": False},
                "amenities": {"enabled": False, "standalone": False},
            },
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
    await db_session.flush()
    return prop, room


# ── Plan enforcement ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_widget_returns_402_when_plan_blocked(async_client: AsyncClient, db_session):
    """Widget returns 402 when property is plan_blocked."""
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"blocked-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Blocked Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"blocked-{uuid.uuid4().hex[:8]}",
        name="Blocked Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=True,  # <-- blocked
        widget_config={"sections": {"rooms": {"enabled": True}}},
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.get(f"/w/{prop.slug}")
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_widget_returns_402_when_no_active_subscription(async_client: AsyncClient, db_session):
    """Widget returns 402 when property has no active subscription."""
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"nosub-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="No Sub Owner",
    )
    db_session.add(user)
    await db_session.flush()
    # No subscription created for this user

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"nosub-{uuid.uuid4().hex[:8]}",
        name="No Sub Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=False,
        widget_config={"sections": {"rooms": {"enabled": True}}},
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.get(f"/w/{prop.slug}")
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_widget_returns_404_for_unknown_slug(async_client: AsyncClient):
    resp = await async_client.get("/w/this-hotel-does-not-exist")
    assert resp.status_code == 404


# ── Room availability ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_widget_main_page_200(async_client: AsyncClient, published_prop):
    prop, _ = published_prop
    resp = await async_client.get(f"/w/{prop.slug}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_room_availability_returns_available_rooms(async_client: AsyncClient, published_prop):
    prop, room = published_prop
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    resp = await async_client.post(
        f"/w/{prop.slug}/availability",
        json={"check_in": str(check_in), "check_out": str(check_out)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(r["room_id"] == str(room.id) for r in data)
    assert all(r["available"] is True for r in data)


# ── Rentals availability ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rentals_page_200_when_enabled(async_client: AsyncClient, published_prop):
    prop, _ = published_prop
    resp = await async_client.get(f"/w/{prop.slug}/rentals")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rentals_page_404_when_disabled(async_client: AsyncClient, db_session):
    """Rentals page returns 404 when section is disabled in widget_config."""
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"norental-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="No Rental Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"norental-{uuid.uuid4().hex[:8]}",
        name="No Rental Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=False,
        widget_config={"sections": {"rentals": {"enabled": False}}},
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.get(f"/w/{prop.slug}/rentals")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rentals_availability_returns_items(async_client: AsyncClient, published_prop, db_session):
    prop, _ = published_prop
    from tests.rentals.factories import make_rental_item
    item = make_rental_item(property_id=prop.id, quantity_available=3)
    db_session.add(item)
    await db_session.flush()

    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)
    resp = await async_client.post(
        f"/w/{prop.slug}/rentals/availability",
        json={"check_in": str(check_in), "check_out": str(check_out), "quantity": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(r["rental_item_id"] == str(item.id) for r in data)


# ── Amenities availability ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_amenities_page_404_when_disabled(async_client: AsyncClient, published_prop):
    """Amenities section is disabled in fixture (enabled: False) → 404."""
    prop, _ = published_prop
    resp = await async_client.get(f"/w/{prop.slug}/amenities")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_amenities_page_200_when_enabled(async_client: AsyncClient, db_session):
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"amenity-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Amenity Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"amenity-{uuid.uuid4().hex[:8]}",
        name="Amenity Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=True,
        is_plan_blocked=False,
        widget_config={"sections": {"amenities": {"enabled": True}}},
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.get(f"/w/{prop.slug}/amenities")
    assert resp.status_code == 200
