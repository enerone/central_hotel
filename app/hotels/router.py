import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.core.database import get_db
from app.core.templates import templates
from app.hotels.models import Property
from app.hotels.schemas import PropertyCreate, PropertyUpdate
from app.hotels.service import (
    create_property,
    delete_property,
    get_properties_by_user,
    get_property_by_id,
    get_property_by_slug,
    update_property,
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
