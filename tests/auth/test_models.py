import pytest
from sqlalchemy import select
from app.auth.models import User


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(
        email="alice@example.com",
        full_name="Alice Example",
        hashed_password="hashed_pw",
        is_active=True,
        is_superadmin=False,
        preferred_language="es",
    )
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.full_name == "Alice Example"
    assert fetched.is_active is True
    assert fetched.is_superadmin is False
    assert fetched.preferred_language == "es"
    assert fetched.id is not None
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_user_email_is_unique(db_session):
    user1 = User(email="bob@example.com", full_name="Bob", hashed_password="pw")
    user2 = User(email="bob@example.com", full_name="Bob2", hashed_password="pw")
    db_session.add(user1)
    await db_session.flush()
    db_session.add(user2)
    with pytest.raises(Exception):  # IntegrityError on unique constraint
        await db_session.flush()
