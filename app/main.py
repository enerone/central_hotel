from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.auth.dependencies import NotAuthenticated
from app.auth.router import router as auth_router
from app.billing.dependencies import SubscriptionInactive, require_active_subscription
from app.billing.router import router as billing_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.dashboard.router import router as dashboard_router
from app.hotels.router import router as hotels_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    if not settings.is_test:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Sistema Hotel",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=604800)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(SubscriptionInactive)
async def subscription_inactive_handler(request: Request, exc: SubscriptionInactive):
    return RedirectResponse(url="/dashboard/billing", status_code=303)


# Billing router: no subscription dependency — billing routes always accessible
app.include_router(billing_router)

# Auth router: no subscription dependency
app.include_router(auth_router)

# Dashboard and hotels routers: require active subscription
app.include_router(
    dashboard_router,
    dependencies=[Depends(require_active_subscription)],
)
app.include_router(
    hotels_router,
    dependencies=[Depends(require_active_subscription)],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
