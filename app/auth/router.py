import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginForm, RegisterForm
from app.auth.service import authenticate_user, create_user, get_or_create_oauth_user, get_user_by_email
from app.core.config import settings
from app.core.database import get_db
from app.core.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


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
    return RedirectResponse(url="/dashboard/billing", status_code=303)


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


@router.get("/auth/google")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.warning("Google OAuth error: %s", exc, exc_info=True)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=303)

    user_info = token.get("userinfo")
    if not user_info:
        return RedirectResponse(url="/login?error=oauth_failed", status_code=303)

    user = await get_or_create_oauth_user(
        db,
        email=user_info["email"],
        full_name=user_info.get("name", ""),
        oauth_provider="google",
        oauth_id=user_info["sub"],
    )
    if user is None:
        return RedirectResponse(url="/login?error=account_disabled", status_code=303)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=303)
