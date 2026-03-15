from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(application: FastAPI):
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"db": "ok"}
