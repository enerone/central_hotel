import pytest
from decimal import Decimal
from datetime import date

from app.hotels.schemas import (
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    ServiceCreate,
    PromotionCreate,
)
from app.hotels.service import (
    create_property,
    get_properties_by_user,
    get_property_by_id,
    get_property_by_slug,
    update_property,
    delete_property,
    create_room,
    get_rooms_by_property,
    get_room_by_id,
    update_room,
    delete_room,
    create_service,
    get_services_by_property,
    delete_service_item,
    create_promotion,
    get_promotions_by_property,
    upsert_availability,
    get_availability_for_month,
    get_blocked_dates_in_range,
)
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_create_property(db_session):
    user = make_user(email="svc_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    form = PropertyCreate(name="Mi Hotel", slug="mi-hotel-svc", city="Mendoza", currency="ARS")
    prop = await create_property(db_session, user.id, form)

    assert prop.id is not None
    assert prop.slug == "mi-hotel-svc"
    assert prop.description == {"es": "", "en": ""}
    assert prop.widget_config["primary_color"] == "#3B82F6"


async def test_get_properties_by_user(db_session):
    user = make_user(email="multi_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    p1 = make_property(user_id=user.id, slug="hotel-a")
    p2 = make_property(user_id=user.id, slug="hotel-b")
    db_session.add_all([p1, p2])
    await db_session.flush()

    props = await get_properties_by_user(db_session, user.id)
    assert len(props) == 2


async def test_get_property_by_slug(db_session):
    user = make_user(email="slug_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="slug-lookup")
    db_session.add(prop)
    await db_session.flush()

    found = await get_property_by_slug(db_session, "slug-lookup")
    assert found is not None
    assert found.id == prop.id

    missing = await get_property_by_slug(db_session, "nonexistent")
    assert missing is None


async def test_update_property(db_session):
    user = make_user(email="upd_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="update-me")
    db_session.add(prop)
    await db_session.flush()

    form = PropertyUpdate(name="New Name", is_published=True)
    updated = await update_property(db_session, prop, form)

    assert updated.name == "New Name"
    assert updated.is_published is True


async def test_delete_property(db_session):
    user = make_user(email="del_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="delete-me")
    db_session.add(prop)
    await db_session.flush()

    await delete_property(db_session, prop)

    found = await get_property_by_id(db_session, prop.id)
    assert found is None


async def test_create_room(db_session):
    user = make_user(email="room_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="room-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = RoomCreate(name_es="Suite", base_price=Decimal("200.00"), capacity=3)
    room = await create_room(db_session, prop.id, form)

    assert room.id is not None
    assert room.name == {"es": "Suite", "en": ""}
    assert room.base_price == Decimal("200.00")
    assert room.capacity == 3


async def test_create_service(db_session):
    user = make_user(email="svc2_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="svc-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = ServiceCreate(name_es="Desayuno", price=Decimal("10.00"), is_included=False)
    svc = await create_service(db_session, prop.id, form)

    assert svc.id is not None
    assert svc.name["es"] == "Desayuno"


async def test_create_promotion(db_session):
    user = make_user(email="promo_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="promo-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = PromotionCreate(
        name_es="Verano",
        discount_type="percent",
        discount_value=Decimal("15.00"),
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 3, 31),
        min_nights=2,
    )
    promo = await create_promotion(db_session, prop.id, form)

    assert promo.id is not None
    assert promo.discount_type == "percent"
    assert promo.min_nights == 2


async def test_upsert_availability_and_get_blocked_dates(db_session):
    user = make_user(email="avail_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="avail-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    # Block two dates
    await upsert_availability(db_session, room.id, date(2026, 6, 10), is_blocked=True)
    await upsert_availability(db_session, room.id, date(2026, 6, 11), is_blocked=True)

    blocked = await get_blocked_dates_in_range(
        db_session, room.id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert date(2026, 6, 10) in blocked
    assert date(2026, 6, 11) in blocked
    assert date(2026, 6, 12) not in blocked


async def test_upsert_availability_updates_existing(db_session):
    user = make_user(email="avail2_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="avail2-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    avail_date = date(2026, 7, 15)
    await upsert_availability(db_session, room.id, avail_date, is_blocked=True)
    # Upsert again to unblock
    await upsert_availability(db_session, room.id, avail_date, is_blocked=False)

    blocked = await get_blocked_dates_in_range(
        db_session, room.id, date(2026, 7, 1), date(2026, 7, 31)
    )
    assert avail_date not in blocked
