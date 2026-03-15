import pytest
from sqlalchemy.exc import IntegrityError

from app.hotels.models import Property, Room
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_create_property(db_session):
    user = make_user(email="owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="mi-hotel")
    db_session.add(prop)
    await db_session.flush()

    assert prop.id is not None
    assert prop.slug == "mi-hotel"
    assert prop.user_id == user.id
    assert prop.is_published is False
    assert prop.is_plan_blocked is False


async def test_property_slug_unique(db_session):
    user = make_user(email="owner2@example.com")
    db_session.add(user)
    await db_session.flush()

    p1 = make_property(user_id=user.id, slug="unique-slug")
    p2 = make_property(user_id=user.id, slug="unique-slug")
    db_session.add(p1)
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_create_room(db_session):
    user = make_user(email="owner3@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id)
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    assert room.id is not None
    assert room.property_id == prop.id
    assert room.is_active is True
