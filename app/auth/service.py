import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterForm
from app.auth.security import hash_password, verify_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, form: RegisterForm) -> User:
    user = User(
        email=form.email,
        hashed_password=hash_password(form.password),
        full_name=form.full_name,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not user.hashed_password:
        return None  # OAuth-only user, no password set
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_or_create_oauth_user(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    oauth_provider: str,
    oauth_id: str,
) -> User | None:
    """Returns the user, or None if the account exists but is deactivated."""
    user = await get_user_by_email(db, email)
    if user:
        if not user.is_active:
            return None  # deactivated accounts cannot log in via OAuth
        if not user.oauth_id:
            user.oauth_provider = oauth_provider
            user.oauth_id = oauth_id
            await db.flush()
        return user

    user = User(
        email=email,
        full_name=full_name,
        oauth_provider=oauth_provider,
        oauth_id=oauth_id,
        hashed_password=None,
    )
    db.add(user)
    await db.flush()
    return user
