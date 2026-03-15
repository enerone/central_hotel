import uuid
from decimal import Decimal

from app.hotels.models import Promotion, Room, Service
from app.hotels.models import Property


def make_property(user_id: uuid.UUID, **kwargs) -> Property:
    """Return an unsaved Property with sensible defaults."""
    defaults = {
        "user_id": user_id,
        "slug": "test-hotel",
        "name": "Test Hotel",
        "description": {"es": "Descripción de prueba", "en": "Test description"},
        "city": "Buenos Aires",
        "country": "Argentina",
        "currency": "ARS",
        "locale": "es",
        "is_published": False,
        "is_plan_blocked": False,
        "widget_config": {
            "primary_color": "#3B82F6",
            "font": "inter",
            "button_style": "rounded",
            "sections": {
                "rooms": {"enabled": True, "standalone": False},
                "rentals": {"enabled": True, "standalone": False},
                "amenities": {"enabled": False, "standalone": False},
            },
        },
    }
    defaults.update(kwargs)
    return Property(**defaults)


def make_room(property_id: uuid.UUID, **kwargs) -> Room:
    """Return an unsaved Room with sensible defaults."""
    defaults = {
        "property_id": property_id,
        "name": {"es": "Habitación estándar", "en": "Standard room"},
        "description": {"es": "Descripción", "en": "Description"},
        "capacity": 2,
        "base_price": Decimal("100.00"),
        "photos": [],
        "amenities": ["wifi", "ac"],
        "is_active": True,
    }
    defaults.update(kwargs)
    return Room(**defaults)


def make_service(property_id: uuid.UUID, **kwargs) -> Service:
    """Return an unsaved Service with sensible defaults."""
    defaults = {
        "property_id": property_id,
        "name": {"es": "Desayuno", "en": "Breakfast"},
        "description": {"es": "Desayuno continental", "en": "Continental breakfast"},
        "price": Decimal("15.00"),
        "is_included": False,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Service(**defaults)


def make_promotion(property_id: uuid.UUID, **kwargs) -> "Promotion":
    """Return an unsaved Promotion with sensible defaults."""
    from datetime import date
    defaults = {
        "property_id": property_id,
        "name": {"es": "Descuento temporada", "en": "Season discount"},
        "discount_type": "percent",
        "discount_value": Decimal("10.00"),
        "valid_from": date(2026, 1, 1),
        "valid_until": date(2026, 12, 31),
        "min_nights": 2,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Promotion(**defaults)
