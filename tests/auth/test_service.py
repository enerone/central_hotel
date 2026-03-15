import pytest

from app.auth.models import User
from app.auth.service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from app.auth.schemas import RegisterForm
from tests.auth.factories import make_user


@pytest.mark.asyncio
async def test_create_user(db_session):
    form = RegisterForm(email="newuser@example.com", password="password123", full_name="New User")
    user = await create_user(db_session, form)
    await db_session.flush()
    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.hashed_password != "password123"  # must be hashed
    assert user.full_name == "New User"


@pytest.mark.asyncio
async def test_get_user_by_email_found(db_session):
    u = make_user(email="find@example.com")
    db_session.add(u)
    await db_session.flush()

    found = await get_user_by_email(db_session, "find@example.com")
    assert found is not None
    assert found.email == "find@example.com"


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session):
    result = await get_user_by_email(db_session, "nobody@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_id(db_session):
    u = make_user(email="byid@example.com")
    db_session.add(u)
    await db_session.flush()

    found = await get_user_by_id(db_session, u.id)
    assert found is not None
    assert found.email == "byid@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session):
    form = RegisterForm(email="auth@example.com", password="secret123", full_name="Auth User")
    user = await create_user(db_session, form)
    await db_session.flush()

    authenticated = await authenticate_user(db_session, "auth@example.com", "secret123")
    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session):
    form = RegisterForm(email="wrongpw@example.com", password="correct1", full_name="User")
    await create_user(db_session, form)
    await db_session.flush()

    result = await authenticate_user(db_session, "wrongpw@example.com", "incorrect")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_inactive(db_session):
    u = make_user(email="inactive@example.com", is_active=False)
    db_session.add(u)
    await db_session.flush()

    result = await authenticate_user(db_session, "inactive@example.com", "password123")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_unknown_email(db_session):
    result = await authenticate_user(db_session, "ghost@example.com", "password")
    assert result is None
