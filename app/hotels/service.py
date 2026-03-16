import copy
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.service import enforce_property_limit, enforce_room_limit
from app.hotels.models import Promotion, Property, Room, RoomAvailability, Service
from app.hotels.schemas import (
    PromotionCreate,
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    RoomUpdate,
    ServiceCreate,
)

_DEFAULT_WIDGET_CONFIG = {
    "primary_color": "#3B82F6",
    "font": "inter",
    "button_style": "rounded",
    "sections": {
        "rooms": {"enabled": True, "standalone": False},
        "rentals": {"enabled": True, "standalone": False},
        "amenities": {"enabled": False, "standalone": False},
    },
}


# ── Property ──────────────────────────────────────────────────────────────────


async def create_property(
    db: AsyncSession, user_id: uuid.UUID, form: PropertyCreate
) -> Property:
    await enforce_property_limit(db, user_id)  # raises HTTP 422 if at limit
    prop = Property(
        user_id=user_id,
        slug=form.slug,
        name=form.name,
        description={"es": form.description_es, "en": form.description_en},
        address=form.address,
        city=form.city,
        country=form.country,
        currency=form.currency,
        locale=form.locale,
        widget_config=copy.deepcopy(_DEFAULT_WIDGET_CONFIG),
    )
    db.add(prop)
    await db.flush()
    return prop


async def get_properties_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Property]:
    result = await db.execute(
        select(Property).where(Property.user_id == user_id).order_by(Property.created_at)
    )
    return list(result.scalars().all())


async def get_property_by_id(
    db: AsyncSession, property_id: uuid.UUID
) -> Property | None:
    result = await db.execute(select(Property).where(Property.id == property_id))
    return result.scalar_one_or_none()


async def get_property_by_slug(db: AsyncSession, slug: str) -> Property | None:
    result = await db.execute(select(Property).where(Property.slug == slug))
    return result.scalar_one_or_none()


async def update_property(
    db: AsyncSession, prop: Property, form: PropertyUpdate
) -> Property:
    if form.name is not None:
        prop.name = form.name
    if form.description_es is not None or form.description_en is not None:
        desc = dict(prop.description)
        if form.description_es is not None:
            desc["es"] = form.description_es
        if form.description_en is not None:
            desc["en"] = form.description_en
        prop.description = desc
    if form.address is not None:
        prop.address = form.address or None   # empty string → None
    if form.city is not None:
        prop.city = form.city or None
    if form.country is not None:
        prop.country = form.country or None
    if form.currency is not None:
        prop.currency = form.currency
    if form.locale is not None:
        prop.locale = form.locale
    if form.is_published is not None:
        prop.is_published = form.is_published
    await db.flush()
    return prop


async def delete_property(db: AsyncSession, prop: Property) -> None:
    await db.delete(prop)
    await db.flush()


# ── Room ──────────────────────────────────────────────────────────────────────


async def create_room(
    db: AsyncSession, property_id: uuid.UUID, form: RoomCreate
) -> Room:
    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()
    if prop:
        await enforce_room_limit(db, prop.user_id, property_id)
    room = Room(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        description={"es": form.description_es, "en": form.description_en},
        capacity=form.capacity,
        base_price=form.base_price,
        amenities=list(form.amenities),
    )
    db.add(room)
    await db.flush()
    return room


async def get_rooms_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Room]:
    result = await db.execute(
        select(Room).where(Room.property_id == property_id).order_by(Room.created_at)
    )
    return list(result.scalars().all())


async def get_room_by_id(db: AsyncSession, room_id: uuid.UUID) -> Room | None:
    result = await db.execute(select(Room).where(Room.id == room_id))
    return result.scalar_one_or_none()


async def update_room(db: AsyncSession, room: Room, form: RoomUpdate) -> Room:
    if form.name_es is not None or form.name_en is not None:
        name = dict(room.name)
        if form.name_es is not None:
            name["es"] = form.name_es
        if form.name_en is not None:
            name["en"] = form.name_en
        room.name = name
    if form.description_es is not None or form.description_en is not None:
        desc = dict(room.description)
        if form.description_es is not None:
            desc["es"] = form.description_es
        if form.description_en is not None:
            desc["en"] = form.description_en
        room.description = desc
    if form.capacity is not None:
        room.capacity = form.capacity
    if form.base_price is not None:
        room.base_price = form.base_price
    if form.amenities is not None:
        room.amenities = list(form.amenities)
    if form.is_active is not None:
        room.is_active = form.is_active
    await db.flush()
    return room


async def delete_room(db: AsyncSession, room: Room) -> None:
    await db.delete(room)
    await db.flush()


# ── Service (hotel service items) ─────────────────────────────────────────────


async def create_service(
    db: AsyncSession, property_id: uuid.UUID, form: ServiceCreate
) -> Service:
    svc = Service(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        description={"es": form.description_es, "en": form.description_en},
        price=form.price,
        is_included=form.is_included,
    )
    db.add(svc)
    await db.flush()
    return svc


async def get_services_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(Service.property_id == property_id)
        .order_by(Service.created_at)
    )
    return list(result.scalars().all())


async def delete_service_item(db: AsyncSession, svc: Service) -> None:
    await db.delete(svc)
    await db.flush()


# ── Promotion ─────────────────────────────────────────────────────────────────


async def create_promotion(
    db: AsyncSession, property_id: uuid.UUID, form: PromotionCreate
) -> Promotion:
    promo = Promotion(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        discount_type=form.discount_type,
        discount_value=form.discount_value,
        valid_from=form.valid_from,
        valid_until=form.valid_until,
        min_nights=form.min_nights,
    )
    db.add(promo)
    await db.flush()
    return promo


async def get_promotions_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Promotion]:
    result = await db.execute(
        select(Promotion)
        .where(Promotion.property_id == property_id)
        .order_by(Promotion.created_at)
    )
    return list(result.scalars().all())


async def delete_promotion(db: AsyncSession, promo: Promotion) -> None:
    await db.delete(promo)
    await db.flush()


# ── Room Availability ─────────────────────────────────────────────────────────


async def upsert_availability(
    db: AsyncSession,
    room_id: uuid.UUID,
    avail_date: date,
    is_blocked: bool,
    override_price: Decimal | None = None,
) -> None:
    """Insert or update a RoomAvailability record for (room_id, date)."""
    stmt = (
        pg_insert(RoomAvailability)
        .values(
            room_id=room_id,
            date=avail_date,
            is_blocked=is_blocked,
            override_price=override_price,
        )
        .on_conflict_do_update(
            index_elements=["room_id", "date"],
            set_={"is_blocked": is_blocked, "override_price": override_price},
        )
    )
    await db.execute(stmt)


async def get_availability_for_month(
    db: AsyncSession, room_id: uuid.UUID, year: int, month: int
) -> list[RoomAvailability]:
    """Return all RoomAvailability records for the given room and calendar month."""
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    result = await db.execute(
        select(RoomAvailability)
        .where(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date >= first_day,
            RoomAvailability.date <= last_day,
        )
        .order_by(RoomAvailability.date)
    )
    return list(result.scalars().all())


async def get_blocked_dates_in_range(
    db: AsyncSession, room_id: uuid.UUID, start_date: date, end_date: date
) -> list[date]:
    """Return list of dates in [start_date, end_date) that are manually blocked.
    The range is half-open: start_date is inclusive, end_date is exclusive.
    For bookings: pass check_in as start_date, check_out as end_date.
    Used by Plan 5 (bookings) to check availability.
    """
    result = await db.execute(
        select(RoomAvailability.date).where(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date >= start_date,
            RoomAvailability.date < end_date,
            RoomAvailability.is_blocked.is_(True),
        )
    )
    return list(result.scalars().all())
