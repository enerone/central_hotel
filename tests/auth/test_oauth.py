from unittest.mock import AsyncMock, patch

from fastapi.responses import RedirectResponse


async def test_google_login_redirects(async_client):
    """GET /auth/google should redirect to Google's auth page."""
    with patch(
        "app.auth.router.oauth.google.authorize_redirect",
        new_callable=AsyncMock,
        return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth", status_code=302),
    ):
        response = await async_client.get("/auth/google", follow_redirects=False)
    assert response.status_code in (302, 307)


async def test_google_callback_creates_user_and_redirects(async_client, db_session):
    """Callback with valid token should create user and redirect to /dashboard."""
    mock_token = {
        "userinfo": {
            "email": "oauth@gmail.com",
            "name": "OAuth User",
            "sub": "google_uid_12345",
        }
    }
    with patch(
        "app.auth.router.oauth.google.authorize_access_token",
        new_callable=AsyncMock,
        return_value=mock_token,
    ):
        response = await async_client.get("/auth/google/callback", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


async def test_google_callback_error_redirects_to_login(async_client):
    """Callback that raises an exception should redirect to /login."""
    with patch(
        "app.auth.router.oauth.google.authorize_access_token",
        new_callable=AsyncMock,
        side_effect=Exception("oauth error"),
    ):
        response = await async_client.get("/auth/google/callback", follow_redirects=False)

    assert response.status_code == 303
    assert "/login" in response.headers["location"]
