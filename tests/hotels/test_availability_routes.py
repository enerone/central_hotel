from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_availability_page_renders(async_client, db_session):
    user = make_user(email="avail_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-route-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.get(
        f"/dashboard/properties/{prop.id}/availability?room_id={room.id}&year=2026&month=6"
    )
    assert response.status_code == 200
    assert "disponibilidad" in response.text.lower() or "availability" in response.text.lower()


async def test_availability_page_no_rooms(async_client, db_session):
    user = make_user(email="avail_empty@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_empty@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-empty-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/availability")
    assert response.status_code == 200


async def test_save_availability_blocks(async_client, db_session):
    user = make_user(email="avail_save@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_save@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-save-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/availability",
        data={
            "room_id": str(room.id),
            "year": "2026",
            "month": "6",
            "blocked_dates": ["2026-06-10", "2026-06-11"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
