"""Billing enforcement dependency."""

import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.billing.service import get_active_subscription
from app.core.database import get_db


class SubscriptionInactive(Exception):
    """Raised when a user accesses a protected route without an active subscription."""
    pass


async def require_active_subscription(
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dependency that requires the current user to have an active subscription."""
    sub = await get_active_subscription(db, user.id)
    if sub is None:
        raise SubscriptionInactive()
