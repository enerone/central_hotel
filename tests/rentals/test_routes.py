"""Integration tests for rental dashboard routes."""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.billing.helpers import make_active_sub_for_user
from tests.rentals.factories import make_rental_item, make_rental_booking


@pytest.fixture
async def logged_in_client(async_client: AsyncClient, db_session):
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"rental-owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Rental Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"rental-prop-{uuid.uuid4().hex[:8]}",
        name="Rental Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    # Log in
    resp = await async_client.post("/login", data={
        "email": user.email, "password": "pw"
    }, follow_redirects=True)
    assert resp.status_code == 200

    return async_client, user, prop


@pytest.mark.asyncio
async def test_rental_items_list_200(logged_in_client, db_session):
    client, user, prop = logged_in_client
    resp = await client.get(f"/dashboard/properties/{prop.id}/rentals")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rental_bookings_list_200(logged_in_client, db_session):
    client, user, prop = logged_in_client
    resp = await client.get(f"/dashboard/properties/{prop.id}/rentals/bookings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_rental_booking(logged_in_client, db_session):
    client, user, prop = logged_in_client
    item = make_rental_item(property_id=prop.id)
    db_session.add(item)
    await db_session.flush()

    check_in = date.today() + timedelta(days=5)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_in + timedelta(days=2),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    resp = await client.post(
        f"/dashboard/properties/{prop.id}/rentals/bookings/{booking.id}/confirm",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_reject_rental_booking(logged_in_client, db_session):
    client, user, prop = logged_in_client
    item = make_rental_item(property_id=prop.id)
    db_session.add(item)
    await db_session.flush()

    check_in = date.today() + timedelta(days=5)
    booking = make_rental_booking(
        property_id=prop.id,
        rental_item_id=item.id,
        check_in=check_in,
        check_out=check_in + timedelta(days=2),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    resp = await client.post(
        f"/dashboard/properties/{prop.id}/rentals/bookings/{booking.id}/reject",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "canceled"


@pytest.mark.asyncio
async def test_rental_booking_404_cross_property_isolation(logged_in_client, db_session):
    """Owner cannot confirm a booking belonging to another owner's property."""
    client, user, prop = logged_in_client

    # Create a second user with their own property and booking
    from app.auth.models import User as UserModel
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw2", bcrypt.gensalt()).decode()
    other_user = UserModel(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Other Owner",
    )
    db_session.add(other_user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, other_user.id)

    other_prop = Property(
        id=uuid.uuid4(),
        user_id=other_user.id,
        slug=f"other-prop-{uuid.uuid4().hex[:8]}",
        name="Other Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
    )
    db_session.add(other_prop)
    await db_session.flush()

    other_item = make_rental_item(property_id=other_prop.id)
    db_session.add(other_item)
    await db_session.flush()

    check_in = date.today() + timedelta(days=5)
    other_booking = make_rental_booking(
        property_id=other_prop.id,
        rental_item_id=other_item.id,
        check_in=check_in,
        check_out=check_in + timedelta(days=2),
        status="pending",
    )
    db_session.add(other_booking)
    await db_session.flush()

    # First user tries to confirm a booking under the other property
    resp = await client.post(
        f"/dashboard/properties/{other_prop.id}/rentals/bookings/{other_booking.id}/confirm",
        follow_redirects=False,
    )
    assert resp.status_code == 404
