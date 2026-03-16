"""Rental booking input schema."""
import uuid
from datetime import date

from pydantic import BaseModel, EmailStr


class RentalBookingCreate(BaseModel):
    rental_item_id: uuid.UUID
    guest_name: str
    guest_email: EmailStr
    check_in: date
    check_out: date
    quantity: int = 1
    room_booking_id: uuid.UUID | None = None
