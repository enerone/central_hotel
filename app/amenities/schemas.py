"""Amenity booking input schema."""
import uuid
from datetime import date

from pydantic import BaseModel, EmailStr


class AmenityBookingCreate(BaseModel):
    amenity_item_id: uuid.UUID
    guest_name: str
    guest_email: EmailStr
    date: date
    quantity: int = 1
    room_booking_id: uuid.UUID | None = None
