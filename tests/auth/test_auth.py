import pytest


@pytest.mark.asyncio
async def test_register_page_renders(async_client):
    response = await async_client.get("/register")
    assert response.status_code == 200
    assert "Crear cuenta" in response.text


@pytest.mark.asyncio
async def test_register_creates_user_and_redirects(async_client):
    response = await async_client.post(
        "/register",
        data={"email": "newuser@example.com", "password": "password123", "full_name": "New User"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_error(async_client, db_session):
    from tests.auth.factories import make_user
    u = make_user(email="taken@example.com")
    db_session.add(u)
    await db_session.flush()

    response = await async_client.post(
        "/register",
        data={"email": "taken@example.com", "password": "password123", "full_name": "User"},
    )
    assert response.status_code == 400
    assert "Email" in response.text or "email" in response.text


@pytest.mark.asyncio
async def test_register_short_password_returns_error(async_client):
    response = await async_client.post(
        "/register",
        data={"email": "user@example.com", "password": "short", "full_name": "User"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_page_renders(async_client):
    response = await async_client.get("/login")
    assert response.status_code == 200
    assert "Iniciar sesión" in response.text


@pytest.mark.asyncio
async def test_login_valid_credentials_redirects(async_client, db_session):
    from app.auth.service import create_user
    from app.auth.schemas import RegisterForm
    form = RegisterForm(email="logintest@example.com", password="mypassword", full_name="Login User")
    await create_user(db_session, form)
    await db_session.flush()

    response = await async_client.post(
        "/login",
        data={"email": "logintest@example.com", "password": "mypassword"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_error(async_client, db_session):
    from app.auth.service import create_user
    from app.auth.schemas import RegisterForm
    form = RegisterForm(email="badlogin@example.com", password="correctpw", full_name="User")
    await create_user(db_session, form)
    await db_session.flush()

    response = await async_client.post(
        "/login",
        data={"email": "badlogin@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.text or "incorrecta" in response.text.lower() or "inválid" in response.text.lower()


@pytest.mark.asyncio
async def test_logout_clears_session_and_redirects(async_client):
    response = await async_client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
