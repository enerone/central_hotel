import pytest


async def test_dashboard_without_session_redirects_to_login(async_client):
    response = await async_client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_dashboard_with_valid_session_returns_200(async_client, db_session):
    from tests.auth.factories import make_user
    user = make_user(email="dashuser@example.com")
    db_session.add(user)
    await db_session.flush()

    # Log in to get a session
    login_response = await async_client.post(
        "/login",
        data={"email": "dashuser@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    # Now access dashboard — the async_client carries cookies
    response = await async_client.get("/dashboard")
    assert response.status_code == 200
    assert "dashuser@example.com" in response.text or "Dashboard" in response.text


async def test_dashboard_with_inactive_user_in_session_redirects(async_client, db_session):
    """get_optional_user must redirect to /login when the user becomes inactive after login."""
    from tests.auth.factories import make_user
    user = make_user(email="inactive_session@example.com", is_active=True)
    db_session.add(user)
    await db_session.flush()

    # Log in while active
    await async_client.post(
        "/login",
        data={"email": "inactive_session@example.com", "password": "password123"},
        follow_redirects=False,
    )

    # Deactivate in-place (same DB session, still visible to get_optional_user)
    user.is_active = False
    await db_session.flush()

    # Dashboard should redirect because get_optional_user sees is_active=False
    response = await async_client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
