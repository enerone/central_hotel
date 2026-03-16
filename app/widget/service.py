"""Widget service helpers.

All public — no auth. Raises HTTP 402 if subscription inactive or plan_blocked.
Raises HTTP 404 if section disabled in widget_config.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.service import get_active_subscription
from app.hotels.models import Property, Room
from app.rentals.models import RentalItem
from app.amenities.models import AmenityItem


async def get_published_property(db: AsyncSession, slug: str) -> Property:
    """Return published property by slug. Raises 404 if not found or not published."""
    result = await db.execute(
        select(Property).where(Property.slug == slug, Property.is_published == True)
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Hotel no encontrado.")
    return prop


async def assert_widget_accessible(db: AsyncSession, prop: Property) -> None:
    """Raise 402 if subscription inactive or property is plan_blocked."""
    if prop.is_plan_blocked:
        raise HTTPException(
            status_code=402,
            detail="El sistema de reservas está temporalmente no disponible.",
        )
    sub = await get_active_subscription(db, prop.user_id)
    if sub is None:
        raise HTTPException(
            status_code=402,
            detail="El sistema de reservas está temporalmente no disponible.",
        )


def assert_section_enabled(prop: Property, section: str) -> None:
    """Raise 404 if the given section is disabled in widget_config."""
    sections = (prop.widget_config or {}).get("sections", {})
    section_cfg = sections.get(section, {})
    if not section_cfg.get("enabled", False):
        raise HTTPException(status_code=404, detail="Sección no disponible.")


async def get_active_rooms(db: AsyncSession, property_id: uuid.UUID) -> list[Room]:
    result = await db.execute(
        select(Room)
        .where(Room.property_id == property_id, Room.is_active == True)
        .order_by(Room.base_price)
    )
    return list(result.scalars().all())


async def get_active_rental_items(db: AsyncSession, property_id: uuid.UUID) -> list[RentalItem]:
    result = await db.execute(
        select(RentalItem)
        .where(RentalItem.property_id == property_id, RentalItem.is_active == True)
    )
    return list(result.scalars().all())


async def get_active_amenity_items(db: AsyncSession, property_id: uuid.UUID) -> list[AmenityItem]:
    result = await db.execute(
        select(AmenityItem)
        .where(AmenityItem.property_id == property_id, AmenityItem.is_active == True)
    )
    return list(result.scalars().all())
