"""Seed billing plans. Run once per environment:

    source venv/bin/activate
    python scripts/seed_plans.py
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.billing.models import Plan


PLANS = [
    {
        "id": 1,
        "name": "basic",
        "price_monthly": 29.00,
        "max_properties": 1,
        "max_rooms": 10,
        "online_payments": False,
        "auto_confirm": False,
        "promotions_enabled": False,
        "stripe_price_id": None,
    },
    {
        "id": 2,
        "name": "pro",
        "price_monthly": 79.00,
        "max_properties": 5,
        "max_rooms": 50,
        "online_payments": True,
        "auto_confirm": True,
        "promotions_enabled": True,
        "stripe_price_id": None,
    },
    {
        "id": 3,
        "name": "enterprise",
        "price_monthly": 199.00,
        "max_properties": -1,
        "max_rooms": -1,
        "online_payments": True,
        "auto_confirm": True,
        "promotions_enabled": True,
        "stripe_price_id": None,
    },
]


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=True)
    async with engine.begin() as conn:
        for plan_data in PLANS:
            stmt = (
                pg_insert(Plan)
                .values(**plan_data)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={k: plan_data[k] for k in plan_data if k != "id"},
                )
            )
            await conn.execute(stmt)
    await engine.dispose()
    print("Plans seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
