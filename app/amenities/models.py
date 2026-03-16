"""Amenity item and amenity booking models."""
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AmenityItem(Base):
    __tablename__ = "amenity_items"

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
    price_per_person: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    daily_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    guest_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AmenityBooking(Base):
    __tablename__ = "amenity_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    amenity_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("amenity_items.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False)
    room_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True
    )
    date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
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
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
