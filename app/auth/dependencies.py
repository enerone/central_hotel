import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_user_by_id
from app.core.database import get_db


class NotAuthenticated(Exception):
    """Raised by require_auth when no valid session is present.
    Handled by the exception handler registered in app/main.py — redirects to /login."""
    pass


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns the current user or None if not authenticated."""
    user_id_str = request.session.get("user_id")
    if not user_id_str:
        return None
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        request.session.clear()
        return None
    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        request.session.clear()
        return None
    return user


async def require_auth(
    user: User | None = Depends(get_optional_user),
) -> User:
    """Redirects to /login if not authenticated. Use as Depends() on any protected route.
    Raises NotAuthenticated, which is handled in app/main.py with a 303 RedirectResponse."""
    if user is None:
        raise NotAuthenticated()
    return user
