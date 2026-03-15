from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.dashboard.router import router as dashboard_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    if not settings.is_test:
        # Startup: verify DB connection
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    yield
    # Shutdown: nothing needed for now


app = FastAPI(
    title="Sistema Hotel",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=604800)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
