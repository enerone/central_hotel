# Central model registry.
# Import every model module here so that:
#   1. tests/conftest.py picks them up for Base.metadata.create_all
#   2. alembic/env.py picks them up for autogenerate
# Add one line per plan as new models are created.
from app.auth.models import User  # noqa: F401
from app.hotels.models import Property, Promotion, Room, RoomAvailability, Service  # noqa: F401
from app.billing.models import Plan, Subscription  # noqa: F401
from app.bookings.models import Booking  # noqa: F401
from app.rentals.models import RentalItem, RentalBooking  # noqa: F401
from app.amenities.models import AmenityItem, AmenityBooking  # noqa: F401
