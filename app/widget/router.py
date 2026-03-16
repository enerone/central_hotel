"""Public booking widget routes. No authentication required."""
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.templates import templates
from app.rentals.service import is_rental_available
from app.amenities.service import is_amenity_available
from app.bookings.service import is_room_available
from app.widget.service import (
    assert_section_enabled,
    assert_widget_accessible,
    get_active_amenity_items,
    get_active_rental_items,
    get_active_rooms,
    get_published_property,
)

router = APIRouter()


# ── Input schemas ──────────────────────────────────────────────────────────────


class RoomAvailabilityRequest(BaseModel):
    check_in: date
    check_out: date


class RentalAvailabilityRequest(BaseModel):
    check_in: date
    check_out: date
    quantity: int = 1


class AmenityAvailabilityRequest(BaseModel):
    date: date
    quantity: int = 1


# ── Main widget ────────────────────────────────────────────────────────────────


@router.get("/w/{slug}", response_class=HTMLResponse)
async def widget_main(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    rooms = await get_active_rooms(db, prop.id)
    return templates.TemplateResponse(
        request,
        "widget/rooms.html",
        {"prop": prop, "rooms": rooms},
    )


@router.post("/w/{slug}/availability")
async def room_availability(
    slug: str,
    body: RoomAvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    rooms = await get_active_rooms(db, prop.id)
    result = []
    for room in rooms:
        available = await is_room_available(db, room.id, body.check_in, body.check_out)
        locale = prop.locale or "es"
        name = room.name.get(locale) or room.name.get("es") or list(room.name.values())[0]
        result.append({
            "room_id": str(room.id),
            "name": name,
            "capacity": room.capacity,
            "base_price": str(room.base_price),
            "currency": prop.currency,
            "available": available,
        })
    return JSONResponse(result)


# ── Rentals widget ─────────────────────────────────────────────────────────────


@router.get("/w/{slug}/rentals", response_class=HTMLResponse)
async def widget_rentals(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "rentals")
    items = await get_active_rental_items(db, prop.id)
    return templates.TemplateResponse(
        request,
        "widget/rentals.html",
        {"prop": prop, "items": items},
    )


@router.post("/w/{slug}/rentals/availability")
async def rental_availability(
    slug: str,
    body: RentalAvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "rentals")
    items = await get_active_rental_items(db, prop.id)
    result = []
    for item in items:
        available = await is_rental_available(
            db, item.id, body.check_in, body.check_out, body.quantity
        )
        locale = prop.locale or "es"
        name = item.name.get(locale) or item.name.get("es") or list(item.name.values())[0]
        result.append({
            "rental_item_id": str(item.id),
            "name": name,
            "price_per_day": str(item.price_per_day),
            "quantity_available": item.quantity_available,
            "currency": prop.currency,
            "available": available,
        })
    return JSONResponse(result)


# ── Amenities widget ───────────────────────────────────────────────────────────


@router.get("/w/{slug}/amenities", response_class=HTMLResponse)
async def widget_amenities(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "amenities")
    items = await get_active_amenity_items(db, prop.id)
    return templates.TemplateResponse(
        request,
        "widget/amenities.html",
        {"prop": prop, "items": items},
    )


@router.post("/w/{slug}/amenities/availability")
async def amenity_availability(
    slug: str,
    body: AmenityAvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "amenities")
    items = await get_active_amenity_items(db, prop.id)
    result = []
    for item in items:
        available = await is_amenity_available(db, item.id, body.date, body.quantity)
        locale = prop.locale or "es"
        name = item.name.get(locale) or item.name.get("es") or list(item.name.values())[0]
        result.append({
            "amenity_item_id": str(item.id),
            "name": name,
            "price_per_person": str(item.price_per_person),
            "daily_capacity": item.daily_capacity,
            "currency": prop.currency,
            "available": available,
        })
    return JSONResponse(result)
