import calendar as calendar_module
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.templates import templates
from app.hotels.models import Promotion, Property, Room, Service
from app.hotels.schemas import (
    PromotionCreate,
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    RoomUpdate,
    ServiceCreate,
)
from app.hotels.service import (
    create_promotion,
    create_property,
    create_room,
    create_service,
    delete_promotion,
    delete_property,
    delete_room,
    delete_service_item,
    get_availability_for_month,
    get_promotions_by_property,
    get_properties_by_user,
    get_property_by_id,
    get_property_by_slug,
    get_room_by_id,
    get_rooms_by_property,
    get_services_by_property,
    update_property,
    update_room,
    update_widget_config,
    upsert_availability,
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


async def _get_room_or_404(
    rid: uuid.UUID,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
) -> Room:
    room = await get_room_by_id(db, rid)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)
    return room


# ── Properties ────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties", response_class=HTMLResponse)
async def properties_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    props = await get_properties_by_user(db, user.id)
    return templates.TemplateResponse(
        request, "dashboard/properties/list.html", {"user": user, "properties": props}
    )


@router.get("/dashboard/properties/new", response_class=HTMLResponse)
async def new_property_page(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        request, "dashboard/properties/form.html", {"user": user, "prop": None}
    )


@router.post("/dashboard/properties/new", response_class=HTMLResponse)
async def create_property_route(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description_es: str = Form(""),
    description_en: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    country: str = Form(""),
    currency: str = Form("USD"),
    locale: str = Form("es"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = PropertyCreate(
            name=name,
            slug=slug,
            description_es=description_es,
            description_en=description_en,
            address=address or None,
            city=city or None,
            country=country or None,
            currency=currency,
            locale=locale,
        )
    except ValidationError as e:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/form.html",
            {"user": user, "prop": None, "error": e.errors()[0]["msg"]},
            status_code=422,
        )

    existing = await get_property_by_slug(db, form.slug)
    if existing:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/form.html",
            {"user": user, "prop": None, "error": "Ese slug ya está en uso"},
            status_code=400,
        )

    prop = await create_property(db, user.id, form)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/edit", status_code=303
    )


@router.get("/dashboard/properties/{id}/edit", response_class=HTMLResponse)
async def edit_property_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request, "dashboard/properties/form.html", {"user": user, "prop": prop}
    )


@router.post("/dashboard/properties/{id}/edit", response_class=HTMLResponse)
async def update_property_route(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    name: str = Form(None),
    description_es: str = Form(None),
    description_en: str = Form(None),
    address: str | None = Form(None),
    city: str | None = Form(None),
    country: str | None = Form(None),
    currency: str = Form(None),
    locale: str = Form(None),
    is_published: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    id = prop.id
    form = PropertyUpdate(
        name=name or None,
        description_es=description_es,
        description_en=description_en,
        address=address,
        city=city,
        country=country,
        currency=currency or None,
        locale=locale or None,
        is_published=None if is_published is None else (is_published == "1"),
    )
    await update_property(db, prop, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/edit", status_code=303)


@router.post("/dashboard/properties/{id}/delete")
async def delete_property_route(
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await delete_property(db, prop)
    return RedirectResponse(url="/dashboard/properties", status_code=303)


# ── Rooms ─────────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/rooms", response_class=HTMLResponse)
async def rooms_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    rooms = await get_rooms_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/list.html",
        {"user": user, "prop": prop, "rooms": rooms},
    )


@router.get("/dashboard/properties/{id}/rooms/new", response_class=HTMLResponse)
async def new_room_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/form.html",
        {"user": user, "prop": prop, "room": None},
    )


@router.post("/dashboard/properties/{id}/rooms/new", response_class=HTMLResponse)
async def create_room_route(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    name_es: str = Form(...),
    name_en: str = Form(""),
    description_es: str = Form(""),
    description_en: str = Form(""),
    capacity: int = Form(2),
    base_price: str = Form(...),
    amenities: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = RoomCreate(
            name_es=name_es,
            name_en=name_en,
            description_es=description_es,
            description_en=description_en,
            capacity=capacity,
            base_price=Decimal(base_price),
            amenities=[a.strip() for a in amenities.split(",") if a.strip()],
        )
    except (ValidationError, InvalidOperation) as e:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/rooms/form.html",
            {"user": user, "prop": prop, "room": None, "error": str(e)},
            status_code=422,
        )

    await create_room(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/rooms", status_code=303)


@router.get("/dashboard/properties/{id}/rooms/{rid}/edit", response_class=HTMLResponse)
async def edit_room_page(
    request: Request,
    room: Room = Depends(_get_room_or_404),
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/form.html",
        {"user": user, "prop": prop, "room": room},
    )


@router.post("/dashboard/properties/{id}/rooms/{rid}/edit", response_class=HTMLResponse)
async def update_room_route(
    request: Request,
    room: Room = Depends(_get_room_or_404),
    prop: Property = Depends(_get_property_or_404),
    name_es: str = Form(None),
    name_en: str = Form(None),
    capacity: int = Form(None),
    base_price: str = Form(None),
    amenities: str = Form(None),
    is_active: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = RoomUpdate(
            name_es=name_es,
            name_en=name_en,
            capacity=capacity,
            base_price=Decimal(base_price) if base_price else None,
            amenities=[a.strip() for a in amenities.split(",") if a.strip()] if amenities is not None else None,
            is_active=None if is_active is None else (is_active == "1"),
        )
    except (ValidationError, InvalidOperation) as e:
        # Need prop for the template — get it from the room's property_id
        # But we have prop already from the dependency
        room_obj = room  # room is the Room object from Depends(_get_room_or_404)
        return templates.TemplateResponse(
            request,
            "dashboard/properties/rooms/form.html",
            {"user": user, "prop": prop, "room": room_obj, "error": str(e)},
            status_code=422,
        )
    await update_room(db, room, form)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/rooms", status_code=303)


@router.post("/dashboard/properties/{id}/rooms/{rid}/delete")
async def delete_room_route(
    room: Room = Depends(_get_room_or_404),
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await delete_room(db, room)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/rooms", status_code=303)


# ── Services ──────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/services", response_class=HTMLResponse)
async def services_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    svcs = await get_services_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/services/list.html",
        {"user": user, "prop": prop, "services": svcs},
    )


@router.post("/dashboard/properties/{id}/services/new")
async def create_service_route(
    prop: Property = Depends(_get_property_or_404),
    name_es: str = Form(...),
    name_en: str = Form(""),
    description_es: str = Form(""),
    price: str = Form("0.00"),
    is_included: str = Form("0"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = ServiceCreate(
            name_es=name_es,
            name_en=name_en,
            description_es=description_es,
            price=Decimal(price),
            is_included=is_included == "1",
        )
    except (ValidationError, InvalidOperation):
        raise HTTPException(status_code=422)
    await create_service(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/services", status_code=303)


@router.post("/dashboard/properties/{id}/services/{sid}/delete")
async def delete_service_route(
    sid: uuid.UUID,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await db.execute(
        select(Service).where(Service.id == sid, Service.property_id == prop.id)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404)
    await delete_service_item(db, svc)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/services", status_code=303)


# ── Promotions ────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/promotions", response_class=HTMLResponse)
async def promotions_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    promos = await get_promotions_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/promotions/list.html",
        {"user": user, "prop": prop, "promotions": promos},
    )


@router.post("/dashboard/properties/{id}/promotions/new")
async def create_promotion_route(
    prop: Property = Depends(_get_property_or_404),
    name_es: str = Form(...),
    name_en: str = Form(""),
    discount_type: str = Form(...),
    discount_value: str = Form(...),
    valid_from: str = Form(...),
    valid_until: str = Form(...),
    min_nights: int = Form(1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = PromotionCreate(
            name_es=name_es,
            name_en=name_en,
            discount_type=discount_type,
            discount_value=Decimal(discount_value),
            valid_from=date.fromisoformat(valid_from),
            valid_until=date.fromisoformat(valid_until),
            min_nights=min_nights,
        )
    except (ValidationError, InvalidOperation, ValueError):
        raise HTTPException(status_code=422)
    await create_promotion(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/promotions", status_code=303)


@router.post("/dashboard/properties/{id}/promotions/{pid}/delete")
async def delete_promotion_route(
    pid: uuid.UUID,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await db.execute(
        select(Promotion).where(Promotion.id == pid, Promotion.property_id == prop.id)
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404)
    await delete_promotion(db, promo)
    return RedirectResponse(url=f"/dashboard/properties/{prop.id}/promotions", status_code=303)


# ── Availability ──────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/availability", response_class=HTMLResponse)
async def availability_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    room_id: uuid.UUID | None = None,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    rooms = await get_rooms_by_property(db, prop.id)
    selected_room_id = room_id or (rooms[0].id if rooms else None)

    calendar_weeks = []
    blocked_date_set: set[date] = set()

    if selected_room_id:
        avail_records = await get_availability_for_month(db, selected_room_id, year, month)
        blocked_date_set = {r.date for r in avail_records if r.is_blocked}

    cal = calendar_module.monthcalendar(year, month)
    for week in cal:
        week_days = []
        for day_num in week:
            if day_num == 0:
                week_days.append(None)
            else:
                d = date(year, month, day_num)
                week_days.append({
                    "day": day_num,
                    "date_str": d.isoformat(),
                    "is_blocked": d in blocked_date_set,
                })
        calendar_weeks.append(week_days)

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year = year + 1 if month == 12 else year

    month_names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    month_name = month_names[month - 1]

    return templates.TemplateResponse(
        request,
        "dashboard/properties/availability/calendar.html",
        {
            "user": user,
            "prop": prop,
            "rooms": rooms,
            "selected_room_id": selected_room_id,
            "year": year,
            "month": month,
            "month_name": month_name,
            "calendar_weeks": calendar_weeks,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
        },
    )


@router.post("/dashboard/properties/{id}/availability")
async def save_availability(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    form_data = await request.form()
    room_id_str = form_data.get("room_id")
    year = int(form_data.get("year", date.today().year))
    month = int(form_data.get("month", date.today().month))

    if not room_id_str:
        return RedirectResponse(url=f"/dashboard/properties/{prop.id}/availability", status_code=303)

    room_id = uuid.UUID(str(room_id_str))
    room = await get_room_by_id(db, room_id)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)

    blocked_dates = set(form_data.getlist("blocked_dates"))

    _, days_in_month = calendar_module.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        is_blocked = d.isoformat() in blocked_dates
        await upsert_availability(db, room_id, d, is_blocked=is_blocked)

    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/availability?room_id={room_id}&year={year}&month={month}",
        status_code=303,
    )


# ── Widget Config ──────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/widget", response_class=HTMLResponse)
async def widget_config_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    base_url = app_settings.base_url
    return templates.TemplateResponse(
        request,
        "dashboard/properties/widget.html",
        {"user": user, "prop": prop, "base_url": base_url},
    )


@router.post("/dashboard/properties/{id}/widget", response_class=HTMLResponse)
async def widget_config_save(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    primary_color: str = Form(default="#3B82F6"),
    rentals_enabled: str = Form(default="off"),
    amenities_enabled: str = Form(default="off"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    await update_widget_config(
        db,
        prop,
        primary_color=primary_color,
        rentals_enabled=(rentals_enabled == "on"),
        amenities_enabled=(amenities_enabled == "on"),
    )
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/widget", status_code=303
    )
