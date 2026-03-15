import pytest
from decimal import Decimal
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_rooms_list_authenticated(async_client, db_session):
    user = make_user(email="rooms_list@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "rooms_list@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="rooms-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/rooms")
    assert response.status_code == 200
    assert "habitaci" in response.text.lower() or "room" in response.text.lower()


async def test_create_room_success(async_client, db_session):
    user = make_user(email="room_create@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "room_create@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="create-room-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/new",
        data={
            "name_es": "Suite ejecutiva",
            "name_en": "Executive suite",
            "capacity": "2",
            "base_price": "150.00",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


async def test_create_room_other_user_property_returns_404(async_client, db_session):
    owner = make_user(email="owner_rooms@example.com")
    other = make_user(email="other_rooms@example.com")
    db_session.add_all([owner, other])
    await db_session.flush()

    prop = make_property(user_id=owner.id, slug="protected-hotel")
    db_session.add(prop)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "other_rooms@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/new",
        data={"name_es": "Suite", "capacity": "2", "base_price": "100.00"},
    )
    assert response.status_code == 404


async def test_delete_room(async_client, db_session):
    user = make_user(email="del_room@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "del_room@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="del-room-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/{room.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
