import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from app.hotels.models import Property, Room, RoomAvailability
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_promotion, make_room, make_service


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


async def test_create_service(db_session):
    user = make_user(email="owner4@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="service-hotel")
    db_session.add(prop)
    await db_session.flush()

    svc = make_service(property_id=prop.id)
    db_session.add(svc)
    await db_session.flush()

    assert svc.id is not None
    assert svc.property_id == prop.id
    assert svc.is_active is True


async def test_create_promotion(db_session):
    user = make_user(email="owner5@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="promo-hotel")
    db_session.add(prop)
    await db_session.flush()

    promo = make_promotion(property_id=prop.id)
    db_session.add(promo)
    await db_session.flush()

    assert promo.id is not None
    assert promo.discount_type == "percent"
    assert promo.min_nights == 2


async def test_room_availability_unique_constraint(db_session):
    user = make_user(email="owner6@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="avail-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    avail1 = RoomAvailability(room_id=room.id, date=date(2026, 6, 1), is_blocked=True)
    avail2 = RoomAvailability(room_id=room.id, date=date(2026, 6, 1), is_blocked=False)
    db_session.add(avail1)
    db_session.add(avail2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
