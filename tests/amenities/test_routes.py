"""Integration tests for amenity dashboard routes."""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.billing.helpers import make_active_sub_for_user
from tests.amenities.factories import make_amenity_item, make_amenity_booking


@pytest.fixture
async def logged_in_client(async_client: AsyncClient, db_session):
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"amenity-owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Amenity Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"amenity-prop-{uuid.uuid4().hex[:8]}",
        name="Amenity Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.post("/login", data={
        "email": user.email, "password": "pw"
    }, follow_redirects=True)
    assert resp.status_code == 200

    return async_client, user, prop


@pytest.mark.asyncio
async def test_amenity_items_list_200(logged_in_client):
    client, user, prop = logged_in_client
    resp = await client.get(f"/dashboard/properties/{prop.id}/amenities")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_amenity_bookings_list_200(logged_in_client):
    client, user, prop = logged_in_client
    resp = await client.get(f"/dashboard/properties/{prop.id}/amenities/bookings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_amenity_booking(logged_in_client, db_session):
    client, user, prop = logged_in_client
    item = make_amenity_item(property_id=prop.id)
    db_session.add(item)
    await db_session.flush()

    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=date.today() + timedelta(days=3),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    resp = await client.post(
        f"/dashboard/properties/{prop.id}/amenities/bookings/{booking.id}/confirm",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_reject_amenity_booking(logged_in_client, db_session):
    client, user, prop = logged_in_client
    item = make_amenity_item(property_id=prop.id)
    db_session.add(item)
    await db_session.flush()

    booking = make_amenity_booking(
        property_id=prop.id,
        amenity_item_id=item.id,
        booking_date=date.today() + timedelta(days=3),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    resp = await client.post(
        f"/dashboard/properties/{prop.id}/amenities/bookings/{booking.id}/reject",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "canceled"
