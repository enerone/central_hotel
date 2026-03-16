"""Test helpers for billing: quickly give a test user an active subscription."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from tests.billing.factories import make_plan, make_subscription


_HELPER_PLAN_ID = 9900  # High ID to avoid seeded plan conflicts


async def make_active_sub_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_kwargs: dict | None = None,
    sub_kwargs: dict | None = None,
) -> None:
    """Create a plan (if not exists) and an active subscription for the given user."""
    from sqlalchemy import select
    from app.billing.models import Plan

    plan_id = (plan_kwargs or {}).get("id", _HELPER_PLAN_ID)

    existing = await db.execute(select(Plan).where(Plan.id == plan_id))
    if existing.scalar_one_or_none() is None:
        pkwargs = {"name": f"helper_plan_{plan_id}"}
        pkwargs.update(plan_kwargs or {})
        pkwargs["id"] = plan_id  # always set id explicitly
        plan = make_plan(**pkwargs)
        db.add(plan)
        await db.flush()

    sub = make_subscription(user_id=user_id, plan_id=plan_id, **(sub_kwargs or {}))
    db.add(sub)
    await db.flush()
