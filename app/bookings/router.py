"""Booking dashboard routes.

All routes require authentication (via require_auth dependency) and an active
subscription (router is included with require_active_subscription in main.py).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.bookings.models import Booking
from app.bookings.service import (
    cancel_booking,
    confirm_booking,
    get_booking_by_id,
    get_bookings_by_property,
)
from app.core.database import get_db
from app.core.templates import templates
from app.hotels.models import Property
from app.hotels.service import get_property_by_id

router = APIRouter()


async def _get_property_or_404(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
) -> Property:
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    return prop


async def _get_booking_or_404(
    bid: uuid.UUID,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
) -> Booking:
    booking = await get_booking_by_id(db, bid)
    if not booking or booking.property_id != prop.id:
        raise HTTPException(status_code=404)
    return booking


@router.get("/dashboard/properties/{id}/bookings", response_class=HTMLResponse)
async def bookings_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    bookings = await get_bookings_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/bookings/list.html",
        {"user": user, "prop": prop, "bookings": bookings},
    )


@router.post("/dashboard/properties/{id}/bookings/{bid}/confirm")
async def confirm_booking_route(
    booking: Booking = Depends(_get_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await confirm_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/bookings", status_code=303
    )


@router.post("/dashboard/properties/{id}/bookings/{bid}/reject")
async def reject_booking_route(
    booking: Booking = Depends(_get_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await cancel_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/bookings", status_code=303
    )


@router.post("/dashboard/properties/{id}/bookings/{bid}/cancel")
async def cancel_booking_route(
    booking: Booking = Depends(_get_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await cancel_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/bookings", status_code=303
    )
