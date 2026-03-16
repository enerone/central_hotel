"""Rental item and rental booking models."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class RentalItem(Base):
    __tablename__ = "rental_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[dict] = mapped_column(JSON, nullable=False)
    photos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    price_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    guest_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RentalBooking(Base):
    __tablename__ = "rental_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    rental_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rental_items.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False)
    room_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True
    )
    check_in: Mapped[date] = mapped_column(nullable=False)
    check_out: Mapped[date] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / confirmed / canceled
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unpaid"
    )  # unpaid / paid / refunded
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    stripe_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
