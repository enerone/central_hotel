from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterForm
from app.auth.service import authenticate_user, create_user, get_user_by_email
from app.core.database import get_db
from app.core.templates import templates

router = APIRouter()


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
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
            "auth/register.html",
            {"request": request, "error": "Email ya registrado"},
            status_code=400,
        )
    try:
        form = RegisterForm(email=email, password=password, full_name=full_name)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"] if e.errors() else "Datos inválidos"
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": error_msg},
            status_code=422,
        )
    user = await create_user(db, form)
    await db.commit()
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Email o contraseña inválidos"},
            status_code=401,
        )
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
