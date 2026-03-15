from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginForm, RegisterForm
from app.auth.service import authenticate_user, create_user, get_user_by_email
from app.core.database import get_db
from app.core.templates import templates

router = APIRouter()


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html", {})


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing = await get_user_by_email(db, email)
    if existing:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Email ya registrado"},
            status_code=400,
        )
    try:
        form = RegisterForm(email=email, password=password, full_name=full_name)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"] if e.errors() else "Datos inválidos"
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": error_msg},
            status_code=422,
        )
    user = await create_user(db, form)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        form = LoginForm(email=email, password=password)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"] if e.errors() else "Datos inválidos"
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": error_msg},
            status_code=422,
        )
    user = await authenticate_user(db, form.email, form.password)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Email o contraseña inválidos"},
            status_code=401,
        )
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
