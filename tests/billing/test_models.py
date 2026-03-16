"""Tests for billing models: Plan and Subscription."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.billing.models import Plan, Subscription
from tests.auth.factories import make_user
from tests.billing.factories import make_plan, make_subscription


@pytest.mark.asyncio
async def test_plan_can_be_saved(db_session):
    plan = make_plan(id=100, name="test_plan_save")
    db_session.add(plan)
    await db_session.flush()

    result = await db_session.execute(select(Plan).where(Plan.id == 100))
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.name == "test_plan_save"
    assert fetched.max_properties == 1
    assert fetched.online_payments is False


@pytest.mark.asyncio
async def test_subscription_can_be_saved(db_session):
    plan = make_plan(id=101, name="test_plan_sub")
    user = make_user(email="sub_save@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=101)
    db_session.add(sub)
    await db_session.flush()

    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.status == "active"
    assert fetched.plan_id == 101


@pytest.mark.asyncio
async def test_subscription_user_id_unique(db_session):
    """Only one subscription per user."""
    plan = make_plan(id=102, name="test_plan_unique")
    user = make_user(email="sub_unique@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub1 = make_subscription(
        user_id=user.id,
        plan_id=102,
        stripe_subscription_id="sub_unique_1",
    )
    sub2 = make_subscription(
        user_id=user.id,
        plan_id=102,
        stripe_subscription_id="sub_unique_2",
    )
    db_session.add(sub1)
    await db_session.flush()

    db_session.add(sub2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_subscription_stripe_id_unique(db_session):
    """stripe_subscription_id must be unique across subscriptions."""
    plan = make_plan(id=103, name="test_plan_stripe_unique")
    user1 = make_user(email="sub_stripe1@example.com")
    user2 = make_user(email="sub_stripe2@example.com")
    db_session.add(plan)
    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()

    shared_stripe_id = "sub_shared_stripe_id"
    sub1 = make_subscription(
        user_id=user1.id,
        plan_id=103,
        stripe_subscription_id=shared_stripe_id,
    )
    sub2 = make_subscription(
        user_id=user2.id,
        plan_id=103,
        stripe_subscription_id=shared_stripe_id,
    )
    db_session.add(sub1)
    await db_session.flush()

    db_session.add(sub2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
