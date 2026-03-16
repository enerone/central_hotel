"""Billing service layer.

All Stripe SDK calls live here. Tests mock them via unittest.mock.patch.
DB operations use real SQLAlchemy sessions (tested against real test DB).
"""

import uuid
from datetime import datetime, timezone

import stripe
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import Plan, Subscription
from app.core.config import settings
from app.hotels.models import Property, Room


# ── Read operations ────────────────────────────────────────────────────────────


async def get_active_subscription(
    db: AsyncSession, user_id: uuid.UUID
) -> Subscription | None:
    """Return the user's subscription if status == 'active', else None."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def get_subscription_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> Subscription | None:
    """Return the user's subscription regardless of status."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_plans(db: AsyncSession) -> list[Plan]:
    """Return all plans ordered by price_monthly ascending."""
    result = await db.execute(
        select(Plan).order_by(Plan.price_monthly)
    )
    return list(result.scalars().all())


async def get_plan_by_stripe_price_id(
    db: AsyncSession, stripe_price_id: str
) -> Plan | None:
    result = await db.execute(
        select(Plan).where(Plan.stripe_price_id == stripe_price_id)
    )
    return result.scalar_one_or_none()


# ── Stripe API calls ───────────────────────────────────────────────────────────


async def create_checkout_session(
    db: AsyncSession,
    user: User,
    plan: Plan,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the checkout URL."""
    import anyio
    import functools

    stripe.api_key = settings.stripe_secret_key

    def _create():
        return stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            customer_email=user.email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user.id), "plan_id": str(plan.id)},
        )

    session = await anyio.to_thread.run_sync(_create)
    return session.url


async def create_portal_session(
    subscription: Subscription,
    return_url: str,
) -> str:
    """Create a Stripe Customer Portal session and return the portal URL."""
    import anyio

    stripe.api_key = settings.stripe_secret_key

    def _create():
        return stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

    portal = await anyio.to_thread.run_sync(_create)
    return portal.url


# ── Webhook handlers ───────────────────────────────────────────────────────────


async def handle_subscription_created(
    db: AsyncSession, event_data: dict
) -> None:
    """Handle customer.subscription.created: upsert Subscription row."""
    stripe_sub_id: str = event_data["id"]
    stripe_customer_id: str = event_data["customer"]
    status: str = event_data.get("status", "active")
    period_end_ts: int | None = event_data.get("current_period_end")
    current_period_end: datetime | None = None
    if period_end_ts:
        current_period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)

    user_id_str: str | None = event_data.get("metadata", {}).get("user_id")
    if not user_id_str:
        return
    user_id = uuid.UUID(user_id_str)

    stripe_price_id: str = event_data["items"]["data"][0]["price"]["id"]
    plan = await get_plan_by_stripe_price_id(db, stripe_price_id)
    if plan is None:
        return

    stmt = (
        pg_insert(Subscription)
        .values(
            user_id=user_id,
            plan_id=plan.id,
            stripe_subscription_id=stripe_sub_id,
            stripe_customer_id=stripe_customer_id,
            status=status,
            current_period_end=current_period_end,
        )
        .on_conflict_do_update(
            index_elements=["stripe_subscription_id"],
            set_={
                "plan_id": plan.id,
                "status": status,
                "current_period_end": current_period_end,
                "stripe_customer_id": stripe_customer_id,
            },
        )
    )
    await db.execute(stmt)


async def handle_subscription_updated(
    db: AsyncSession, event_data: dict
) -> None:
    """Handle customer.subscription.updated: update plan_id and status."""
    stripe_sub_id: str = event_data["id"]
    new_status: str = event_data.get("status", "active")
    period_end_ts: int | None = event_data.get("current_period_end")
    current_period_end: datetime | None = None
    if period_end_ts:
        current_period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return

    stripe_price_id: str = event_data["items"]["data"][0]["price"]["id"]
    new_plan = await get_plan_by_stripe_price_id(db, stripe_price_id)
    if new_plan is None:
        return

    old_plan_id = sub.plan_id
    sub.plan_id = new_plan.id
    sub.status = new_status
    sub.current_period_end = current_period_end
    await db.flush()

    if new_plan.id != old_plan_id:
        await _enforce_downgrade_limits(db, sub.user_id, new_plan)


async def _enforce_downgrade_limits(
    db: AsyncSession, user_id: uuid.UUID, new_plan: Plan
) -> None:
    """Block excess properties and deactivate excess rooms after downgrade."""
    props_result = await db.execute(
        select(Property)
        .where(Property.user_id == user_id)
        .order_by(Property.created_at.asc())
    )
    properties = list(props_result.scalars().all())

    if new_plan.max_properties != -1 and len(properties) > new_plan.max_properties:
        to_keep = set(p.id for p in properties[: new_plan.max_properties])
        for prop in properties:
            if prop.id not in to_keep:
                prop.is_plan_blocked = True

    if new_plan.max_rooms != -1:
        for prop in properties:
            rooms_result = await db.execute(
                select(Room)
                .where(Room.property_id == prop.id)
                .order_by(Room.created_at.asc())
            )
            rooms = list(rooms_result.scalars().all())
            if len(rooms) > new_plan.max_rooms:
                to_keep_rooms = set(r.id for r in rooms[: new_plan.max_rooms])
                for room in rooms:
                    if room.id not in to_keep_rooms:
                        room.is_active = False

    await db.flush()


async def handle_subscription_deleted(
    db: AsyncSession, event_data: dict
) -> None:
    """Handle customer.subscription.deleted: set status=canceled, block all properties."""
    stripe_sub_id: str = event_data["id"]

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return

    sub.status = "canceled"
    await db.flush()

    props_result = await db.execute(
        select(Property).where(Property.user_id == sub.user_id)
    )
    for prop in props_result.scalars().all():
        prop.is_plan_blocked = True

    await db.flush()


async def handle_payment_failed(
    db: AsyncSession, event_data: dict
) -> None:
    """Handle invoice.payment_failed: set subscription status=past_due."""
    stripe_sub_id: str | None = event_data.get("subscription")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return

    sub.status = "past_due"
    await db.flush()


# ── Plan enforcement ───────────────────────────────────────────────────────────


async def enforce_property_limit(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    """Raise HTTP 422 if the user has reached their plan's property limit."""
    sub = await get_active_subscription(db, user_id)
    if sub is None:
        return

    plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None or plan.max_properties == -1:
        return

    count_result = await db.execute(
        select(func.count()).select_from(Property).where(Property.user_id == user_id)
    )
    current_count = count_result.scalar_one()

    if current_count >= plan.max_properties:
        raise HTTPException(
            status_code=422,
            detail=f"Has alcanzado el límite de {plan.max_properties} propiedad(es) en tu plan {plan.name}. "
                   f"Actualiza tu plan para agregar más propiedades.",
        )


async def enforce_room_limit(
    db: AsyncSession, user_id: uuid.UUID, property_id: uuid.UUID
) -> None:
    """Raise HTTP 422 if the property has reached the plan's room limit."""
    sub = await get_active_subscription(db, user_id)
    if sub is None:
        return

    plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None or plan.max_rooms == -1:
        return

    count_result = await db.execute(
        select(func.count()).select_from(Room).where(Room.property_id == property_id)
    )
    current_count = count_result.scalar_one()

    if current_count >= plan.max_rooms:
        raise HTTPException(
            status_code=422,
            detail=f"Has alcanzado el límite de {plan.max_rooms} habitación(es) en tu plan {plan.name}. "
                   f"Actualiza tu plan para agregar más habitaciones.",
        )
