import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDMixin


class Property(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "properties"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    locale: Mapped[str] = mapped_column(String(5), default="es", nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_plan_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    widget_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Room(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rooms"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    description: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    photos: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    amenities: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RoomAvailability(Base):
    __tablename__ = "room_availability"
    __table_args__ = (UniqueConstraint("room_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)


class Service(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "services"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    description: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    is_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Promotion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "promotions"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "percent" | "fixed"
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    min_nights: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
