"""Tests for app/billing/service.py.

Strategy:
- DB operations (get, upsert, enforce limits) use real test DB via db_session fixture.
- Stripe API calls (checkout, portal) are mocked with unittest.mock.patch.
- Webhook handlers are tested with fake event dicts (no real Stripe calls).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.billing.models import Plan, Subscription
from app.billing.service import (
    create_checkout_session,
    create_portal_session,
    enforce_property_limit,
    enforce_room_limit,
    get_active_subscription,
    get_all_plans,
    handle_payment_failed,
    handle_subscription_created,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from app.hotels.models import Property, Room
from tests.auth.factories import make_user
from tests.billing.factories import make_plan, make_subscription
from tests.hotels.factories import make_property, make_room


# ── get_active_subscription ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_active_subscription_returns_active(db_session):
    plan = make_plan(id=200, name="svc_plan_active")
    user = make_user(email="svc_active@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=200, status="active")
    db_session.add(sub)
    await db_session.flush()

    result = await get_active_subscription(db_session, user.id)
    assert result is not None
    assert result.status == "active"
    assert result.user_id == user.id


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_canceled(db_session):
    plan = make_plan(id=201, name="svc_plan_canceled")
    user = make_user(email="svc_canceled@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=201, status="canceled")
    db_session.add(sub)
    await db_session.flush()

    result = await get_active_subscription(db_session, user.id)
    assert result is None


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_for_no_subscription(db_session):
    user = make_user(email="svc_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    result = await get_active_subscription(db_session, user.id)
    assert result is None


# ── get_all_plans ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_plans_returns_ordered_by_price(db_session):
    p1 = make_plan(id=210, name="plan_cheap", price_monthly=10.00)
    p2 = make_plan(id=211, name="plan_expensive", price_monthly=200.00)
    p3 = make_plan(id=212, name="plan_mid", price_monthly=50.00)
    db_session.add(p1)
    db_session.add(p2)
    db_session.add(p3)
    await db_session.flush()

    plans = await get_all_plans(db_session)
    test_plans = [p for p in plans if p.id in (210, 211, 212)]
    prices = [p.price_monthly for p in test_plans]
    assert prices == sorted(prices)


# ── create_checkout_session ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_checkout_session_calls_stripe_and_returns_url(db_session):
    plan = make_plan(id=220, name="checkout_plan", stripe_price_id="price_checkout")
    user = make_user(email="checkout@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_abc"

    with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
        url = await create_checkout_session(
            db=db_session,
            user=user,
            plan=plan,
            success_url="http://localhost/dashboard/billing?checkout=success",
            cancel_url="http://localhost/dashboard/billing",
        )

    assert url == "https://checkout.stripe.com/pay/cs_test_abc"
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["mode"] == "subscription"
    assert call_kwargs["customer_email"] == user.email
    assert call_kwargs["line_items"][0]["price"] == "price_checkout"
    assert str(user.id) in str(call_kwargs.get("metadata", {}))


# ── create_portal_session ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_portal_session_calls_stripe_and_returns_url(db_session):
    plan = make_plan(id=230, name="portal_plan")
    user = make_user(email="portal@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=230,
        stripe_customer_id="cus_portal_test",
    )
    db_session.add(sub)
    await db_session.flush()

    fake_portal = MagicMock()
    fake_portal.url = "https://billing.stripe.com/session/bps_test_xyz"

    with patch(
        "stripe.billing_portal.Session.create", return_value=fake_portal
    ) as mock_portal:
        url = await create_portal_session(
            subscription=sub,
            return_url="http://localhost/dashboard/billing",
        )

    assert url == "https://billing.stripe.com/session/bps_test_xyz"
    mock_portal.assert_called_once_with(
        customer="cus_portal_test",
        return_url="http://localhost/dashboard/billing",
    )


# ── handle_subscription_created ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_subscription_created_upserts_subscription(db_session):
    plan = make_plan(id=240, name="webhook_create_plan", stripe_price_id="price_wh_create")
    user = make_user(email="wh_created@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    event_data = {
        "id": "sub_wh_create_123",
        "customer": "cus_wh_create_abc",
        "status": "active",
        "current_period_end": 1893456000,
        "items": {
            "data": [{"price": {"id": "price_wh_create"}}]
        },
        "metadata": {"user_id": str(user.id)},
    }

    await handle_subscription_created(db_session, event_data)

    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    assert sub is not None
    assert sub.stripe_subscription_id == "sub_wh_create_123"
    assert sub.stripe_customer_id == "cus_wh_create_abc"
    assert sub.status == "active"
    assert sub.plan_id == plan.id


@pytest.mark.asyncio
async def test_handle_subscription_created_idempotent(db_session):
    """Calling created handler twice does not create a duplicate subscription."""
    plan = make_plan(id=241, name="webhook_create_idempotent", stripe_price_id="price_wh_idem")
    user = make_user(email="wh_idem@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    event_data = {
        "id": "sub_idem_123",
        "customer": "cus_idem_abc",
        "status": "active",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": "price_wh_idem"}}]},
        "metadata": {"user_id": str(user.id)},
    }

    await handle_subscription_created(db_session, event_data)
    await handle_subscription_created(db_session, event_data)  # second call

    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subs = result.scalars().all()
    assert len(subs) == 1


# ── handle_subscription_updated ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_subscription_updated_changes_status(db_session):
    plan = make_plan(id=250, name="update_plan", stripe_price_id="price_update")
    user = make_user(email="wh_updated@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=250,
        stripe_subscription_id="sub_update_abc",
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    event_data = {
        "id": "sub_update_abc",
        "customer": sub.stripe_customer_id,
        "status": "past_due",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": "price_update"}}]},
        "metadata": {},
    }

    await handle_subscription_updated(db_session, event_data)

    await db_session.refresh(sub)
    assert sub.status == "past_due"


@pytest.mark.asyncio
async def test_handle_subscription_updated_downgrade_blocks_excess_properties(db_session):
    """On downgrade to a plan with max_properties=1: block all but the oldest property."""
    small_plan = make_plan(id=251, name="downgrade_small", stripe_price_id="price_small", max_properties=1)
    big_plan = make_plan(id=252, name="downgrade_big", stripe_price_id="price_big", max_properties=5)
    user = make_user(email="wh_downgrade@example.com")
    db_session.add(small_plan)
    db_session.add(big_plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=252,
        stripe_subscription_id="sub_downgrade_abc",
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    # Create 2 properties
    prop1 = make_property(user_id=user.id, slug="downgrade-prop-1")
    prop2 = make_property(user_id=user.id, slug="downgrade-prop-2")
    db_session.add(prop1)
    await db_session.flush()
    db_session.add(prop2)
    await db_session.flush()

    # Downgrade to small plan
    event_data = {
        "id": "sub_downgrade_abc",
        "customer": sub.stripe_customer_id,
        "status": "active",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": "price_small"}}]},
        "metadata": {},
    }

    await handle_subscription_updated(db_session, event_data)

    await db_session.refresh(prop1)
    await db_session.refresh(prop2)

    unblocked = [p for p in [prop1, prop2] if not p.is_plan_blocked]
    blocked = [p for p in [prop1, prop2] if p.is_plan_blocked]
    assert len(unblocked) == 1
    assert len(blocked) == 1
    assert unblocked[0].id == prop1.id


# ── handle_subscription_deleted ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_subscription_deleted_cancels_and_blocks_properties(db_session):
    plan = make_plan(id=260, name="deleted_plan", stripe_price_id="price_deleted")
    user = make_user(email="wh_deleted@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=260,
        stripe_subscription_id="sub_deleted_abc",
        status="active",
    )
    prop = make_property(user_id=user.id, slug="deleted-prop-1")
    db_session.add(sub)
    db_session.add(prop)
    await db_session.flush()

    event_data = {
        "id": "sub_deleted_abc",
        "customer": sub.stripe_customer_id,
        "metadata": {},
    }

    await handle_subscription_deleted(db_session, event_data)

    await db_session.refresh(sub)
    await db_session.refresh(prop)

    assert sub.status == "canceled"
    assert prop.is_plan_blocked is True


# ── handle_payment_failed ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_payment_failed_sets_past_due(db_session):
    plan = make_plan(id=270, name="payment_failed_plan", stripe_price_id="price_pf")
    user = make_user(email="wh_payment_failed@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=270,
        stripe_subscription_id="sub_pf_abc",
        stripe_customer_id="cus_pf_abc",
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    event_data = {
        "subscription": "sub_pf_abc",
        "customer": "cus_pf_abc",
    }

    await handle_payment_failed(db_session, event_data)

    await db_session.refresh(sub)
    assert sub.status == "past_due"


# ── enforce_property_limit ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enforce_property_limit_passes_when_under_limit(db_session):
    plan = make_plan(id=280, name="prop_limit_plan", max_properties=2)
    user = make_user(email="prop_limit_ok@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=280)
    db_session.add(sub)
    prop = make_property(user_id=user.id, slug="prop-limit-existing")
    db_session.add(prop)
    await db_session.flush()

    await enforce_property_limit(db_session, user.id)


@pytest.mark.asyncio
async def test_enforce_property_limit_raises_when_at_limit(db_session):
    plan = make_plan(id=281, name="prop_limit_plan_at", max_properties=1)
    user = make_user(email="prop_limit_at@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=281)
    prop = make_property(user_id=user.id, slug="prop-at-limit")
    db_session.add(sub)
    db_session.add(prop)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await enforce_property_limit(db_session, user.id)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_enforce_property_limit_skips_when_unlimited(db_session):
    plan = make_plan(id=282, name="prop_limit_unlimited", max_properties=-1)
    user = make_user(email="prop_limit_unlimited@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=282)
    for i in range(5):
        prop = make_property(user_id=user.id, slug=f"prop-unlimited-{i}")
        db_session.add(prop)
    db_session.add(sub)
    await db_session.flush()

    await enforce_property_limit(db_session, user.id)


@pytest.mark.asyncio
async def test_enforce_property_limit_passes_when_no_subscription(db_session):
    user = make_user(email="prop_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    await enforce_property_limit(db_session, user.id)


# ── enforce_room_limit ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enforce_room_limit_passes_when_under_limit(db_session):
    plan = make_plan(id=290, name="room_limit_plan", max_rooms=5)
    user = make_user(email="room_limit_ok@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=290)
    prop = make_property(user_id=user.id, slug="room-limit-prop")
    db_session.add(sub)
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    await enforce_room_limit(db_session, user.id, prop.id)


@pytest.mark.asyncio
async def test_enforce_room_limit_raises_when_at_limit(db_session):
    plan = make_plan(id=291, name="room_limit_plan_at", max_rooms=1)
    user = make_user(email="room_limit_at@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=291)
    prop = make_property(user_id=user.id, slug="room-at-limit-prop")
    db_session.add(sub)
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await enforce_room_limit(db_session, user.id, prop.id)
    assert exc_info.value.status_code == 422
