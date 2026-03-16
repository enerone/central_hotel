"""Public booking widget routes. No authentication required."""
import uuid as _uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amenities.schemas import AmenityBookingCreate
from app.amenities.service import create_amenity_booking, is_amenity_available
from app.billing.models import Plan, Subscription
from app.bookings.schemas import BookingCreate
from app.bookings.service import create_booking, is_room_available
from app.core.config import settings
from app.core.database import get_db
from app.core.templates import templates
from app.rentals.schemas import RentalBookingCreate
from app.rentals.service import create_rental_booking, is_rental_available
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


# ── Booking request schemas ────────────────────────────────────────────────────


class RoomBookingRequest(BaseModel):
    room_id: _uuid.UUID
    guest_name: str
    guest_email: EmailStr
    check_in: date
    check_out: date
    adults: int = 1
    children: int = 0
    promotion_id: _uuid.UUID | None = None


class RentalBookingRequest(BaseModel):
    rental_item_id: _uuid.UUID
    guest_name: str
    guest_email: EmailStr
    check_in: date
    check_out: date
    quantity: int = 1
    room_booking_id: _uuid.UUID | None = None


class AmenityBookingRequest(BaseModel):
    amenity_item_id: _uuid.UUID
    guest_name: str
    guest_email: EmailStr
    date: date
    quantity: int = 1
    room_booking_id: _uuid.UUID | None = None


# ── Plan helper ────────────────────────────────────────────────────────────────


async def _get_plan_for_property(db: AsyncSession, prop) -> Plan:
    """Look up the active subscription's plan for a property."""
    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == prop.user_id,
            Subscription.status == "active",
        )
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=402, detail="Sin suscripción activa.")
    plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=500, detail="Plan no encontrado.")
    return plan


# ── Booking creation endpoints ─────────────────────────────────────────────────


@router.post("/w/{slug}/book")
async def book_room(slug: str, body: RoomBookingRequest, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    plan = await _get_plan_for_property(db, prop)
    form = BookingCreate(
        room_id=body.room_id,
        guest_name=body.guest_name,
        guest_email=body.guest_email,
        check_in=body.check_in,
        check_out=body.check_out,
        adults=body.adults,
        children=body.children,
        promotion_id=body.promotion_id,
    )
    booking = await create_booking(db, prop.id, form, plan)
    response: dict = {
        "booking_id": str(booking.id),
        "status": booking.status,
        "total_price": str(booking.total_price),
        "currency": booking.currency,
    }
    if booking.stripe_payment_intent_id:
        response["payment_intent_client_secret"] = booking.stripe_payment_intent_id
    return JSONResponse(response)


@router.post("/w/{slug}/rentals/book")
async def book_rental(slug: str, body: RentalBookingRequest, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "rentals")
    plan = await _get_plan_for_property(db, prop)
    form = RentalBookingCreate(
        rental_item_id=body.rental_item_id,
        guest_name=body.guest_name,
        guest_email=body.guest_email,
        check_in=body.check_in,
        check_out=body.check_out,
        quantity=body.quantity,
        room_booking_id=body.room_booking_id,
    )
    booking = await create_rental_booking(db, prop.id, form, plan)
    response: dict = {
        "booking_id": str(booking.id),
        "status": booking.status,
        "total_price": str(booking.total_price),
        "currency": booking.currency,
    }
    if booking.stripe_payment_intent_id:
        response["payment_intent_client_secret"] = booking.stripe_payment_intent_id
    return JSONResponse(response)


@router.post("/w/{slug}/amenities/book")
async def book_amenity(slug: str, body: AmenityBookingRequest, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "amenities")
    plan = await _get_plan_for_property(db, prop)
    form = AmenityBookingCreate(
        amenity_item_id=body.amenity_item_id,
        guest_name=body.guest_name,
        guest_email=body.guest_email,
        date=body.date,
        quantity=body.quantity,
        room_booking_id=body.room_booking_id,
    )
    booking = await create_amenity_booking(db, prop.id, form, plan)
    response: dict = {
        "booking_id": str(booking.id),
        "status": booking.status,
        "total_price": str(booking.total_price),
        "currency": booking.currency,
    }
    if booking.stripe_payment_intent_id:
        response["payment_intent_client_secret"] = booking.stripe_payment_intent_id
    return JSONResponse(response)


# ── embed.js endpoints ─────────────────────────────────────────────────────────


def _embed_js(slug: str, path: str, base_url: str) -> str:
    return f"""(function(){{
  var s=document.currentScript;
  var container=s.getAttribute('data-container')||'#hotel-widget';
  var el=document.querySelector(container);
  if(!el)return;
  var iframe=document.createElement('iframe');
  iframe.src='{base_url}/w/{slug}{path}';
  iframe.style.width='100%';
  iframe.style.height='700px';
  iframe.style.border='none';
  el.appendChild(iframe);
}})();"""


@router.get("/w/{slug}/embed.js")
async def embed_js(slug: str, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    js = _embed_js(slug, "", settings.base_url)
    return Response(content=js, media_type="application/javascript")


@router.get("/w/{slug}/rentals/embed.js")
async def rentals_embed_js(slug: str, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "rentals")
    js = _embed_js(slug, "/rentals", settings.base_url)
    return Response(content=js, media_type="application/javascript")


@router.get("/w/{slug}/amenities/embed.js")
async def amenities_embed_js(slug: str, db: AsyncSession = Depends(get_db)):
    prop = await get_published_property(db, slug)
    await assert_widget_accessible(db, prop)
    assert_section_enabled(prop, "amenities")
    js = _embed_js(slug, "/amenities", settings.base_url)
    return Response(content=js, media_type="application/javascript")
