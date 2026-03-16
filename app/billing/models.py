import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDMixin


class Plan(Base):
    """Subscription tier reference data. Seeded via scripts/seed_plans.py.

    max_properties / max_rooms: -1 means unlimited.
    stripe_price_id: populated after creating Stripe products; can be empty in dev.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_properties: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    online_payments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_confirm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promotions_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Subscription(Base, UUIDMixin, TimestampMixin):
    """One subscription per user. Created/updated by Stripe webhooks.

    status values: 'active', 'past_due', 'canceled'
    """

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | past_due | canceled
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
