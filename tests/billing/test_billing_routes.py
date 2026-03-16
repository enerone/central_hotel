"""Tests for billing dashboard routes."""

import pytest
from unittest.mock import MagicMock, patch

from tests.auth.factories import make_user
from tests.billing.factories import make_plan, make_subscription


@pytest.mark.asyncio
async def test_billing_page_accessible_without_subscription(async_client, db_session):
    user = make_user(email="billing_page_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "billing_page_no_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/billing")
    assert response.status_code == 200
    assert "plan" in response.text.lower() or "suscripci" in response.text.lower()


@pytest.mark.asyncio
async def test_billing_page_shows_subscription_status(async_client, db_session):
    plan = make_plan(id=400, name="billing_page_plan", price_monthly=29.00)
    user = make_user(email="billing_page_sub@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=400, status="active")
    db_session.add(sub)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "billing_page_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/billing")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_billing_page_unauthenticated_redirects_to_login(async_client):
    response = await async_client.get("/dashboard/billing", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_dashboard_blocked_without_subscription(async_client, db_session):
    user = make_user(email="dashboard_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "dashboard_no_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert "/dashboard/billing" in response.headers["location"]


@pytest.mark.asyncio
async def test_dashboard_accessible_with_active_subscription(async_client, db_session):
    plan = make_plan(id=401, name="dash_access_plan")
    user = make_user(email="dashboard_with_sub@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=401, status="active")
    db_session.add(sub)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "dashboard_with_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_properties_blocked_without_subscription(async_client, db_session):
    user = make_user(email="properties_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "properties_no_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/properties", follow_redirects=False)
    assert response.status_code == 303
    assert "/dashboard/billing" in response.headers["location"]


@pytest.mark.asyncio
async def test_subscription_status_returns_active(async_client, db_session):
    plan = make_plan(id=410, name="status_active_plan")
    user = make_user(email="status_active@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(user_id=user.id, plan_id=410, status="active")
    db_session.add(sub)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "status_active@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/billing/subscription-status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_subscription_status_returns_none(async_client, db_session):
    user = make_user(email="status_none@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "status_none@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/billing/subscription-status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "none"


@pytest.mark.asyncio
async def test_checkout_redirects_to_stripe(async_client, db_session):
    plan = make_plan(id=420, name="checkout_route_plan", stripe_price_id="price_checkout_route")
    user = make_user(email="checkout_route@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "checkout_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_redirect"

    with patch("stripe.checkout.Session.create", return_value=fake_session):
        response = await async_client.post(
            "/dashboard/billing/checkout",
            data={"plan_id": str(plan.id)},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "checkout.stripe.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_checkout_requires_auth(async_client):
    response = await async_client.post(
        "/dashboard/billing/checkout",
        data={"plan_id": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_portal_redirects_to_stripe(async_client, db_session):
    plan = make_plan(id=430, name="portal_route_plan")
    user = make_user(email="portal_route@example.com")
    db_session.add(plan)
    db_session.add(user)
    await db_session.flush()

    sub = make_subscription(
        user_id=user.id,
        plan_id=430,
        stripe_customer_id="cus_portal_route",
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "portal_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    fake_portal = MagicMock()
    fake_portal.url = "https://billing.stripe.com/session/bps_portal_route"

    with patch("stripe.billing_portal.Session.create", return_value=fake_portal):
        response = await async_client.post(
            "/dashboard/billing/portal",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "billing.stripe.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_portal_returns_404_when_no_subscription(async_client, db_session):
    user = make_user(email="portal_no_sub@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "portal_no_sub@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post("/dashboard/billing/portal", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_register_redirects_to_billing(async_client, db_session):
    response = await async_client.post(
        "/register",
        data={
            "email": "new_billing_redirect@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/dashboard/billing" in response.headers["location"]
