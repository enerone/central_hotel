"""Pydantic schemas for bookings."""
import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, field_validator


class BookingCreate(BaseModel):
    room_id: uuid.UUID
    guest_name: str
    guest_email: EmailStr
    check_in: date
    check_out: date
    adults: int = 1
    children: int = 0
    promotion_id: uuid.UUID | None = None

    @field_validator("adults")
    @classmethod
    def adults_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("adults must be at least 1")
        return v

    @field_validator("children")
    @classmethod
    def children_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("children cannot be negative")
        return v
