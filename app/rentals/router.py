"""Rental dashboard routes.

All routes require auth + active subscription (set in main.py).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.core.database import get_db
from app.core.templates import templates
from app.hotels.models import Property
from app.hotels.service import get_property_by_id
from app.rentals.models import RentalBooking
from app.rentals.service import (
    cancel_rental_booking,
    confirm_rental_booking,
    get_rental_bookings_by_property,
    get_rental_booking_by_id,
    get_rental_items_by_property,
)

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


async def _get_rental_booking_or_404(
    bid: uuid.UUID,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
) -> RentalBooking:
    booking = await get_rental_booking_by_id(db, bid)
    if not booking or booking.property_id != prop.id:
        raise HTTPException(status_code=404)
    return booking


@router.get("/dashboard/properties/{id}/rentals", response_class=HTMLResponse)
async def rental_items_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    items = await get_rental_items_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rentals/list.html",
        {"user": user, "prop": prop, "items": items},
    )


@router.get("/dashboard/properties/{id}/rentals/bookings", response_class=HTMLResponse)
async def rental_bookings_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    bookings = await get_rental_bookings_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rentals/bookings.html",
        {"user": user, "prop": prop, "bookings": bookings},
    )


@router.post("/dashboard/properties/{id}/rentals/bookings/{bid}/confirm")
async def confirm_rental_booking_route(
    booking: RentalBooking = Depends(_get_rental_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await confirm_rental_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/rentals/bookings", status_code=303
    )


@router.post("/dashboard/properties/{id}/rentals/bookings/{bid}/reject")
async def reject_rental_booking_route(
    booking: RentalBooking = Depends(_get_rental_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await cancel_rental_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/rentals/bookings", status_code=303
    )


@router.post("/dashboard/properties/{id}/rentals/bookings/{bid}/cancel")
async def cancel_rental_booking_route(
    booking: RentalBooking = Depends(_get_rental_booking_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await cancel_rental_booking(db, booking)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/rentals/bookings", status_code=303
    )
