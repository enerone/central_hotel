"""Tests for the Stripe webhook endpoint."""

import json
from unittest.mock import patch, MagicMock

import pytest

from tests.auth.factories import make_user
from tests.billing.factories import make_plan, make_subscription


def _fake_event(event_type: str, data_object: dict) -> MagicMock:
    event = MagicMock()
    event.type = event_type
    event.data.object = data_object
    return event


@pytest.mark.asyncio
async def test_webhook_returns_200_for_valid_signature(async_client, db_session):
    plan = make_plan(id=300, name="wh_route_plan", stripe_price_id="price_wh_route")
    user = make_user(email="wh_route@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    fake_event_obj = _fake_event(
        "customer.subscription.created",
        {
            "id": "sub_route_test_abc",
            "customer": "cus_route_test",
            "status": "active",
            "current_period_end": 1893456000,
            "items": {"data": [{"price": {"id": "price_wh_route"}}]},
            "metadata": {"user_id": str(user.id)},
        },
    )

    with patch("stripe.Webhook.construct_event", return_value=fake_event_obj):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{"type": "customer.subscription.created"}',
            headers={"stripe-signature": "fake_sig"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_returns_400_for_invalid_signature(async_client):
    import stripe as stripe_module

    with patch(
        "stripe.Webhook.construct_event",
        side_effect=stripe_module.error.SignatureVerificationError("bad sig", "sig_header"),
    ):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "invalid"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_subscription_created_persists(async_client, db_session):
    from sqlalchemy import select
    from app.billing.models import Subscription

    plan = make_plan(id=301, name="wh_create_persist", stripe_price_id="price_create_persist")
    user = make_user(email="wh_create_persist@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    fake_event_obj = _fake_event(
        "customer.subscription.created",
        {
            "id": "sub_persist_abc",
            "customer": "cus_persist_abc",
            "status": "active",
            "current_period_end": 1893456000,
            "items": {"data": [{"price": {"id": "price_create_persist"}}]},
            "metadata": {"user_id": str(user.id)},
        },
    )

    with patch("stripe.Webhook.construct_event", return_value=fake_event_obj):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "fake_sig"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    assert sub is not None
    assert sub.stripe_subscription_id == "sub_persist_abc"
    assert sub.status == "active"


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_blocks_properties(async_client, db_session):
    from sqlalchemy import select
    from app.billing.models import Subscription
    from app.hotels.models import Property
    from tests.hotels.factories import make_property

    plan = make_plan(id=302, name="wh_delete_plan", stripe_price_id="price_delete_plan")
    user = make_user(email="wh_delete@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=302,
        stripe_subscription_id="sub_delete_route_abc",
        stripe_customer_id="cus_delete_route",
        status="active",
    )
    prop = make_property(user_id=user.id, slug="wh-delete-prop")
    db_session.add(sub)
    db_session.add(prop)
    await db_session.flush()

    fake_event_obj = _fake_event(
        "customer.subscription.deleted",
        {
            "id": "sub_delete_route_abc",
            "customer": "cus_delete_route",
            "metadata": {},
        },
    )

    with patch("stripe.Webhook.construct_event", return_value=fake_event_obj):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "fake_sig"},
        )

    assert response.status_code == 200

    await db_session.refresh(sub)
    await db_session.refresh(prop)
    assert sub.status == "canceled"
    assert prop.is_plan_blocked is True


@pytest.mark.asyncio
async def test_webhook_payment_failed_sets_past_due(async_client, db_session):
    from sqlalchemy import select
    from app.billing.models import Subscription

    plan = make_plan(id=303, name="wh_pf_plan", stripe_price_id="price_pf_plan")
    user = make_user(email="wh_pf@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=303,
        stripe_subscription_id="sub_pf_route_abc",
        stripe_customer_id="cus_pf_route",
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    fake_event_obj = _fake_event(
        "invoice.payment_failed",
        {
            "subscription": "sub_pf_route_abc",
            "customer": "cus_pf_route",
        },
    )

    with patch("stripe.Webhook.construct_event", return_value=fake_event_obj):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "fake_sig"},
        )

    assert response.status_code == 200

    await db_session.refresh(sub)
    assert sub.status == "past_due"


@pytest.mark.asyncio
async def test_webhook_unknown_event_returns_200(async_client):
    fake_event_obj = _fake_event("some.unknown.event", {})

    with patch("stripe.Webhook.construct_event", return_value=fake_event_obj):
        response = await async_client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "fake_sig"},
        )

    assert response.status_code == 200
