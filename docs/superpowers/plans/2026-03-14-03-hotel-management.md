# Hotel Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the hotel management module — owners create properties, configure rooms with availability and pricing, add services and promotions — plus the full dashboard CRUD UI.

**Architecture:** New `app/hotels/` domain module (models, schemas, service, router) following the same pattern as `app/auth/`. All hotel dashboard routes live in `app/hotels/router.py`. I18n fields (name/description) are stored as JSON `{"es": "...", "en": "..."}` and forms use `_es`/`_en` fields that the service combines. Delete operations use `POST /…/delete` (HTML forms don't support DELETE).

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, Jinja2 + TailwindCSS CDN, pytest + httpx.

**Deferred to Plan 4 (Billing):** Subscription enforcement on dashboard routes (requires Subscription model).
**Deferred to Plan 5 (Room Bookings):** `is_room_available()` combining RoomAvailability blocks + confirmed bookings.

---

## Chunk 1: Models, Migration, and Service Layer

### File Map

| File | Responsibility |
|---|---|
| `app/hotels/__init__.py` | Empty package marker |
| `app/hotels/models.py` | Property, Room, RoomAvailability, Service, Promotion SQLAlchemy models |
| `app/models.py` | Add hotel model imports |
| `app/hotels/schemas.py` | Pydantic schemas for all models (Create/Update) |
| `app/hotels/service.py` | CRUD service functions for all entities |
| `tests/hotels/__init__.py` | Empty |
| `tests/hotels/factories.py` | make_property, make_room, make_service, make_promotion |
| `tests/hotels/test_models.py` | Model integration tests |
| `tests/hotels/test_service.py` | Service layer integration tests |

---

### Task 1: Hotel models + model registry + migration

**Files:**
- Create: `app/hotels/__init__.py`
- Create: `app/hotels/models.py`
- Modify: `app/models.py`
- Create: `tests/hotels/__init__.py`

- [ ] **Step 1: Create `app/hotels/__init__.py` and `tests/hotels/__init__.py`** (both empty)

- [ ] **Step 2: Create `app/hotels/models.py`**

```python
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
```

- [ ] **Step 3: Update `app/models.py`**

Add hotel model imports so Alembic autogenerate and test `create_test_tables` pick them up:

```python
# Central model registry.
# Import every model module here so that:
#   1. tests/conftest.py picks them up for Base.metadata.create_all
#   2. alembic/env.py picks them up for autogenerate
# Add one line per plan as new models are created.
from app.auth.models import User  # noqa: F401
from app.hotels.models import Property, Promotion, Room, RoomAvailability, Service  # noqa: F401
```

- [ ] **Step 4: Create `tests/hotels/factories.py`**

```python
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
```

- [ ] **Step 5: Write failing model tests**

Create `tests/hotels/test_models.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.hotels.models import Property, Room
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_create_property(db_session):
    user = make_user(email="owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="mi-hotel")
    db_session.add(prop)
    await db_session.flush()

    assert prop.id is not None
    assert prop.slug == "mi-hotel"
    assert prop.user_id == user.id
    assert prop.is_published is False
    assert prop.is_plan_blocked is False


async def test_property_slug_unique(db_session):
    user = make_user(email="owner2@example.com")
    db_session.add(user)
    await db_session.flush()

    p1 = make_property(user_id=user.id, slug="unique-slug")
    p2 = make_property(user_id=user.id, slug="unique-slug")
    db_session.add(p1)
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_create_room(db_session):
    user = make_user(email="owner3@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id)
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    assert room.id is not None
    assert room.property_id == prop.id
    assert room.is_active is True
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_models.py -v --no-cov 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.hotels'`

- [ ] **Step 7: Generate and apply Alembic migration**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && alembic revision --autogenerate -m "add hotel management tables" && alembic upgrade head
```

Expected: Migration file created, applied with tables: properties, rooms, room_availability, services, promotions.

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_models.py -v --no-cov 2>&1
```

Expected: `3 passed`

- [ ] **Step 9: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/ app/models.py tests/hotels/ alembic/versions/ && git commit -m "feat: add hotel management models and migration"
```

---

### Task 2: Hotel schemas + service layer

**Files:**
- Create: `app/hotels/schemas.py`
- Create: `app/hotels/service.py`
- Create: `tests/hotels/test_service.py`

- [ ] **Step 1: Create `app/hotels/schemas.py`**

```python
import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class PropertyCreate(BaseModel):
    name: str
    slug: str
    description_es: str = ""
    description_en: str = ""
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str = "USD"
    locale: str = "es"

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", v):
            raise ValueError(
                "El slug debe tener al menos 3 caracteres: minúsculas, números y guiones"
            )
        return v

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()[:3]


class PropertyUpdate(BaseModel):
    name: str | None = None
    description_es: str | None = None
    description_en: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    currency: str | None = None
    locale: str | None = None
    is_published: bool | None = None


class RoomCreate(BaseModel):
    name_es: str
    name_en: str = ""
    description_es: str = ""
    description_en: str = ""
    capacity: int = 2
    base_price: Decimal
    amenities: list[str] = []

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("La capacidad debe ser al menos 1")
        return v

    @field_validator("base_price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("El precio no puede ser negativo")
        return v


class RoomUpdate(BaseModel):
    name_es: str | None = None
    name_en: str | None = None
    description_es: str | None = None
    description_en: str | None = None
    capacity: int | None = None
    base_price: Decimal | None = None
    amenities: list[str] | None = None
    is_active: bool | None = None


class ServiceCreate(BaseModel):
    name_es: str
    name_en: str = ""
    description_es: str = ""
    description_en: str = ""
    price: Decimal = Decimal("0.00")
    is_included: bool = False

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("El precio no puede ser negativo")
        return v


class PromotionCreate(BaseModel):
    name_es: str
    name_en: str = ""
    discount_type: Literal["percent", "fixed"]
    discount_value: Decimal
    valid_from: date
    valid_until: date
    min_nights: int = 1

    @field_validator("discount_value")
    @classmethod
    def value_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("El valor del descuento no puede ser negativo")
        return v

    @model_validator(mode="after")
    def valid_until_after_valid_from(self) -> "PromotionCreate":
        if self.valid_until < self.valid_from:
            raise ValueError("La fecha de fin debe ser posterior a la de inicio")
        return self

    @field_validator("min_nights")
    @classmethod
    def min_nights_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("El mínimo de noches debe ser al menos 1")
        return v
```

- [ ] **Step 2: Create `app/hotels/service.py`**

```python
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.hotels.models import Promotion, Property, Room, RoomAvailability, Service
from app.hotels.schemas import (
    PromotionCreate,
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    RoomUpdate,
    ServiceCreate,
)

_DEFAULT_WIDGET_CONFIG = {
    "primary_color": "#3B82F6",
    "font": "inter",
    "button_style": "rounded",
    "sections": {
        "rooms": {"enabled": True, "standalone": False},
        "rentals": {"enabled": True, "standalone": False},
        "amenities": {"enabled": False, "standalone": False},
    },
}


# ── Property ──────────────────────────────────────────────────────────────────


async def create_property(
    db: AsyncSession, user_id: uuid.UUID, form: PropertyCreate
) -> Property:
    prop = Property(
        user_id=user_id,
        slug=form.slug,
        name=form.name,
        description={"es": form.description_es, "en": form.description_en},
        address=form.address,
        city=form.city,
        country=form.country,
        currency=form.currency,
        locale=form.locale,
        widget_config=dict(_DEFAULT_WIDGET_CONFIG),
    )
    db.add(prop)
    await db.flush()
    return prop


async def get_properties_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Property]:
    result = await db.execute(
        select(Property).where(Property.user_id == user_id).order_by(Property.created_at)
    )
    return list(result.scalars().all())


async def get_property_by_id(
    db: AsyncSession, property_id: uuid.UUID
) -> Property | None:
    result = await db.execute(select(Property).where(Property.id == property_id))
    return result.scalar_one_or_none()


async def get_property_by_slug(db: AsyncSession, slug: str) -> Property | None:
    result = await db.execute(select(Property).where(Property.slug == slug))
    return result.scalar_one_or_none()


async def update_property(
    db: AsyncSession, prop: Property, form: PropertyUpdate
) -> Property:
    if form.name is not None:
        prop.name = form.name
    if form.description_es is not None:
        desc = dict(prop.description)
        desc["es"] = form.description_es
        prop.description = desc
    if form.description_en is not None:
        desc = dict(prop.description)
        desc["en"] = form.description_en
        prop.description = desc
    if form.address is not None:
        prop.address = form.address
    if form.city is not None:
        prop.city = form.city
    if form.country is not None:
        prop.country = form.country
    if form.currency is not None:
        prop.currency = form.currency.upper()[:3]
    if form.locale is not None:
        prop.locale = form.locale
    if form.is_published is not None:
        prop.is_published = form.is_published
    await db.flush()
    return prop


async def delete_property(db: AsyncSession, prop: Property) -> None:
    await db.delete(prop)
    await db.flush()


# ── Room ──────────────────────────────────────────────────────────────────────


async def create_room(
    db: AsyncSession, property_id: uuid.UUID, form: RoomCreate
) -> Room:
    room = Room(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        description={"es": form.description_es, "en": form.description_en},
        capacity=form.capacity,
        base_price=form.base_price,
        amenities=list(form.amenities),
    )
    db.add(room)
    await db.flush()
    return room


async def get_rooms_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Room]:
    result = await db.execute(
        select(Room).where(Room.property_id == property_id).order_by(Room.created_at)
    )
    return list(result.scalars().all())


async def get_room_by_id(db: AsyncSession, room_id: uuid.UUID) -> Room | None:
    result = await db.execute(select(Room).where(Room.id == room_id))
    return result.scalar_one_or_none()


async def update_room(db: AsyncSession, room: Room, form: RoomUpdate) -> Room:
    if form.name_es is not None:
        name = dict(room.name)
        name["es"] = form.name_es
        room.name = name
    if form.name_en is not None:
        name = dict(room.name)
        name["en"] = form.name_en
        room.name = name
    if form.description_es is not None:
        desc = dict(room.description)
        desc["es"] = form.description_es
        room.description = desc
    if form.description_en is not None:
        desc = dict(room.description)
        desc["en"] = form.description_en
        room.description = desc
    if form.capacity is not None:
        room.capacity = form.capacity
    if form.base_price is not None:
        room.base_price = form.base_price
    if form.amenities is not None:
        room.amenities = list(form.amenities)
    if form.is_active is not None:
        room.is_active = form.is_active
    await db.flush()
    return room


async def delete_room(db: AsyncSession, room: Room) -> None:
    await db.delete(room)
    await db.flush()


# ── Service (hotel service items) ─────────────────────────────────────────────


async def create_service(
    db: AsyncSession, property_id: uuid.UUID, form: ServiceCreate
) -> Service:
    svc = Service(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        description={"es": form.description_es, "en": form.description_en},
        price=form.price,
        is_included=form.is_included,
    )
    db.add(svc)
    await db.flush()
    return svc


async def get_services_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(Service.property_id == property_id)
        .order_by(Service.created_at)
    )
    return list(result.scalars().all())


async def delete_service_item(db: AsyncSession, svc: Service) -> None:
    await db.delete(svc)
    await db.flush()


# ── Promotion ─────────────────────────────────────────────────────────────────


async def create_promotion(
    db: AsyncSession, property_id: uuid.UUID, form: PromotionCreate
) -> Promotion:
    promo = Promotion(
        property_id=property_id,
        name={"es": form.name_es, "en": form.name_en},
        discount_type=form.discount_type,
        discount_value=form.discount_value,
        valid_from=form.valid_from,
        valid_until=form.valid_until,
        min_nights=form.min_nights,
    )
    db.add(promo)
    await db.flush()
    return promo


async def get_promotions_by_property(
    db: AsyncSession, property_id: uuid.UUID
) -> list[Promotion]:
    result = await db.execute(
        select(Promotion)
        .where(Promotion.property_id == property_id)
        .order_by(Promotion.created_at)
    )
    return list(result.scalars().all())


async def delete_promotion(db: AsyncSession, promo: Promotion) -> None:
    await db.delete(promo)
    await db.flush()


# ── Room Availability ─────────────────────────────────────────────────────────


async def upsert_availability(
    db: AsyncSession,
    room_id: uuid.UUID,
    avail_date: date,
    is_blocked: bool,
    override_price: Decimal | None = None,
) -> None:
    """Insert or update a RoomAvailability record for (room_id, date)."""
    stmt = (
        pg_insert(RoomAvailability)
        .values(
            room_id=room_id,
            date=avail_date,
            is_blocked=is_blocked,
            override_price=override_price,
        )
        .on_conflict_do_update(
            index_elements=["room_id", "date"],
            set_={"is_blocked": is_blocked, "override_price": override_price},
        )
    )
    await db.execute(stmt)


async def get_availability_for_month(
    db: AsyncSession, room_id: uuid.UUID, year: int, month: int
) -> list[RoomAvailability]:
    """Return all RoomAvailability records for the given room and calendar month."""
    from calendar import monthrange
    from datetime import date as date_type

    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, monthrange(year, month)[1])
    result = await db.execute(
        select(RoomAvailability)
        .where(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date >= first_day,
            RoomAvailability.date <= last_day,
        )
        .order_by(RoomAvailability.date)
    )
    return list(result.scalars().all())


async def get_blocked_dates_in_range(
    db: AsyncSession, room_id: uuid.UUID, start_date: date, end_date: date
) -> list[date]:
    """Return list of dates in [start_date, end_date) that are manually blocked.
    Used by Plan 5 (bookings) to check availability.
    """
    result = await db.execute(
        select(RoomAvailability.date).where(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date >= start_date,
            RoomAvailability.date < end_date,
            RoomAvailability.is_blocked.is_(True),
        )
    )
    return list(result.scalars().all())
```

- [ ] **Step 3: Write failing tests**

Create `tests/hotels/test_service.py`:

```python
import pytest
from decimal import Decimal
from datetime import date

from app.hotels.schemas import (
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    ServiceCreate,
    PromotionCreate,
)
from app.hotels.service import (
    create_property,
    get_properties_by_user,
    get_property_by_id,
    get_property_by_slug,
    update_property,
    delete_property,
    create_room,
    get_rooms_by_property,
    get_room_by_id,
    update_room,
    delete_room,
    create_service,
    get_services_by_property,
    delete_service_item,
    create_promotion,
    get_promotions_by_property,
    upsert_availability,
    get_availability_for_month,
    get_blocked_dates_in_range,
)
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_create_property(db_session):
    user = make_user(email="svc_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    form = PropertyCreate(name="Mi Hotel", slug="mi-hotel-svc", city="Mendoza", currency="ARS")
    prop = await create_property(db_session, user.id, form)

    assert prop.id is not None
    assert prop.slug == "mi-hotel-svc"
    assert prop.description == {"es": "", "en": ""}
    assert prop.widget_config["primary_color"] == "#3B82F6"


async def test_get_properties_by_user(db_session):
    user = make_user(email="multi_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    p1 = make_property(user_id=user.id, slug="hotel-a")
    p2 = make_property(user_id=user.id, slug="hotel-b")
    db_session.add_all([p1, p2])
    await db_session.flush()

    props = await get_properties_by_user(db_session, user.id)
    assert len(props) == 2


async def test_get_property_by_slug(db_session):
    user = make_user(email="slug_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="slug-lookup")
    db_session.add(prop)
    await db_session.flush()

    found = await get_property_by_slug(db_session, "slug-lookup")
    assert found is not None
    assert found.id == prop.id

    missing = await get_property_by_slug(db_session, "nonexistent")
    assert missing is None


async def test_update_property(db_session):
    user = make_user(email="upd_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="update-me")
    db_session.add(prop)
    await db_session.flush()

    form = PropertyUpdate(name="New Name", is_published=True)
    updated = await update_property(db_session, prop, form)

    assert updated.name == "New Name"
    assert updated.is_published is True


async def test_delete_property(db_session):
    user = make_user(email="del_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="delete-me")
    db_session.add(prop)
    await db_session.flush()

    await delete_property(db_session, prop)

    found = await get_property_by_id(db_session, prop.id)
    assert found is None


async def test_create_room(db_session):
    user = make_user(email="room_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="room-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = RoomCreate(name_es="Suite", base_price=Decimal("200.00"), capacity=3)
    room = await create_room(db_session, prop.id, form)

    assert room.id is not None
    assert room.name == {"es": "Suite", "en": ""}
    assert room.base_price == Decimal("200.00")
    assert room.capacity == 3


async def test_create_service(db_session):
    user = make_user(email="svc2_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="svc-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = ServiceCreate(name_es="Desayuno", price=Decimal("10.00"), is_included=False)
    svc = await create_service(db_session, prop.id, form)

    assert svc.id is not None
    assert svc.name["es"] == "Desayuno"


async def test_create_promotion(db_session):
    user = make_user(email="promo_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="promo-hotel")
    db_session.add(prop)
    await db_session.flush()

    form = PromotionCreate(
        name_es="Verano",
        discount_type="percent",
        discount_value=Decimal("15.00"),
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 3, 31),
        min_nights=2,
    )
    promo = await create_promotion(db_session, prop.id, form)

    assert promo.id is not None
    assert promo.discount_type == "percent"
    assert promo.min_nights == 2


async def test_upsert_availability_and_get_blocked_dates(db_session):
    user = make_user(email="avail_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="avail-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    # Block two dates
    await upsert_availability(db_session, room.id, date(2026, 6, 10), is_blocked=True)
    await upsert_availability(db_session, room.id, date(2026, 6, 11), is_blocked=True)

    blocked = await get_blocked_dates_in_range(
        db_session, room.id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert date(2026, 6, 10) in blocked
    assert date(2026, 6, 11) in blocked
    assert date(2026, 6, 12) not in blocked


async def test_upsert_availability_updates_existing(db_session):
    user = make_user(email="avail2_owner@example.com")
    db_session.add(user)
    await db_session.flush()

    prop = make_property(user_id=user.id, slug="avail2-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    avail_date = date(2026, 7, 15)
    await upsert_availability(db_session, room.id, avail_date, is_blocked=True)
    # Upsert again to unblock
    await upsert_availability(db_session, room.id, avail_date, is_blocked=False)

    blocked = await get_blocked_dates_in_range(
        db_session, room.id, date(2026, 7, 1), date(2026, 7, 31)
    )
    assert avail_date not in blocked
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_service.py -v --no-cov 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.hotels.schemas'`

- [ ] **Step 5: Run all tests to verify they pass**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/ -v --no-cov 2>&1
```

Expected: all tests pass (3 model tests + ~10 service tests).

- [ ] **Step 6: Run full suite regression**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest --no-cov -q 2>&1
```

Expected: all existing 33 tests + new hotel tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/ tests/hotels/ && git commit -m "feat: add hotel schemas and service layer"
```

---

## Chunk 2: Property and Room Dashboard Routes

### File Map

| File | Responsibility |
|---|---|
| `app/hotels/router.py` | Dashboard routes: properties + rooms CRUD |
| `app/main.py` | Include hotels router |
| `app/templates/dashboard/index.html` | Update to link to properties |
| `app/templates/dashboard/properties/list.html` | Properties list |
| `app/templates/dashboard/properties/form.html` | Create/edit property form |
| `app/templates/dashboard/properties/rooms/list.html` | Rooms list |
| `app/templates/dashboard/properties/rooms/form.html` | Create/edit room form |
| `tests/hotels/test_property_routes.py` | Property route tests |
| `tests/hotels/test_room_routes.py` | Room route tests |

---

### Task 3: Property dashboard routes + templates

**Files:**
- Create: `app/hotels/router.py`
- Modify: `app/main.py`
- Modify: `app/templates/dashboard/index.html`
- Create: `app/templates/dashboard/properties/list.html`
- Create: `app/templates/dashboard/properties/form.html`
- Create: `tests/hotels/test_property_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hotels/test_property_routes.py`:

```python
import pytest
from tests.auth.factories import make_user
from tests.hotels.factories import make_property


async def test_properties_list_unauthenticated(async_client):
    response = await async_client.get("/dashboard/properties", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_properties_list_authenticated(async_client, db_session):
    user = make_user(email="proplist@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "proplist@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/properties")
    assert response.status_code == 200
    assert "Propiedades" in response.text or "Properties" in response.text


async def test_create_property_page(async_client, db_session):
    user = make_user(email="newprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "newprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/properties/new")
    assert response.status_code == 200
    assert "slug" in response.text.lower() or "nombre" in response.text.lower()


async def test_create_property_success(async_client, db_session):
    user = make_user(email="createprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "createprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        "/dashboard/properties/new",
        data={
            "name": "Hotel Test",
            "slug": "hotel-test-create",
            "currency": "ARS",
            "locale": "es",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/dashboard/properties" in response.headers["location"]


async def test_create_property_invalid_slug(async_client, db_session):
    user = make_user(email="badsluq@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "badsluq@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        "/dashboard/properties/new",
        data={"name": "Hotel", "slug": "AB", "currency": "USD"},
    )
    assert response.status_code == 422


async def test_edit_property_page(async_client, db_session):
    user = make_user(email="editprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "editprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="edit-me")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/edit")
    assert response.status_code == 200


async def test_edit_property_other_user_returns_404(async_client, db_session):
    owner = make_user(email="real_owner@example.com")
    other = make_user(email="other_user@example.com")
    db_session.add_all([owner, other])
    await db_session.flush()

    prop = make_property(user_id=owner.id, slug="not-yours")
    db_session.add(prop)
    await db_session.flush()

    # Log in as other user
    await async_client.post(
        "/login",
        data={"email": "other_user@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get(f"/dashboard/properties/{prop.id}/edit")
    assert response.status_code == 404


async def test_delete_property(async_client, db_session):
    user = make_user(email="delprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "delprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="to-delete")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/delete", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/properties"
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p /home/fabi/code/sistemahotel/app/templates/dashboard/properties/rooms
mkdir -p /home/fabi/code/sistemahotel/app/templates/dashboard/properties/services
mkdir -p /home/fabi/code/sistemahotel/app/templates/dashboard/properties/promotions
mkdir -p /home/fabi/code/sistemahotel/app/templates/dashboard/properties/availability
```

- [ ] **Step 3: Create `app/templates/dashboard/properties/list.html`**

```html
{% extends "base.html" %}
{% block title %}Propiedades — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold">Mis propiedades</h1>
    <a href="/dashboard/properties/new"
       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm font-medium">
      + Nueva propiedad
    </a>
  </div>
  {% if properties %}
  <div class="grid gap-4">
    {% for prop in properties %}
    <div class="bg-white rounded-xl shadow p-5 flex justify-between items-start">
      <div>
        <h2 class="text-lg font-semibold">{{ prop.name }}</h2>
        <p class="text-sm text-gray-500">{{ prop.slug }} · {{ prop.city or '' }}</p>
        <span class="text-xs {{ 'text-green-600' if prop.is_published else 'text-gray-400' }}">
          {{ 'Publicado' if prop.is_published else 'No publicado' }}
        </span>
      </div>
      <div class="flex gap-3 text-sm">
        <a href="/dashboard/properties/{{ prop.id }}/rooms" class="text-blue-600 hover:underline">Habitaciones</a>
        <a href="/dashboard/properties/{{ prop.id }}/services" class="text-blue-600 hover:underline">Servicios</a>
        <a href="/dashboard/properties/{{ prop.id }}/promotions" class="text-blue-600 hover:underline">Promociones</a>
        <a href="/dashboard/properties/{{ prop.id }}/availability" class="text-blue-600 hover:underline">Disponibilidad</a>
        <a href="/dashboard/properties/{{ prop.id }}/edit" class="text-gray-600 hover:underline">Editar</a>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <p class="text-gray-500">No tenés propiedades aún. <a href="/dashboard/properties/new" class="text-blue-600 hover:underline">Creá una</a>.</p>
  {% endif %}
  <div class="mt-6">
    <form method="post" action="/logout">
      <button class="text-sm text-red-600 hover:underline">Cerrar sesión</button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Create `app/templates/dashboard/properties/form.html`**

```html
{% extends "base.html" %}
{% block title %}{{ 'Editar' if prop else 'Nueva' }} propiedad — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8 max-w-xl">
  <h1 class="text-2xl font-bold mb-6">{{ 'Editar propiedad' if prop else 'Nueva propiedad' }}</h1>
  {% if error %}
  <div class="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{{ error }}</div>
  {% endif %}
  <form method="post">
    <div class="mb-4">
      <label class="block text-sm font-medium mb-1">Nombre</label>
      <input type="text" name="name" value="{{ prop.name if prop else '' }}" required
             class="w-full border rounded px-3 py-2">
    </div>
    {% if not prop %}
    <div class="mb-4">
      <label class="block text-sm font-medium mb-1">Slug (URL único)</label>
      <input type="text" name="slug" placeholder="mi-hotel" required
             class="w-full border rounded px-3 py-2">
      <p class="text-xs text-gray-500 mt-1">Solo minúsculas, números y guiones. Mínimo 3 caracteres.</p>
    </div>
    {% endif %}
    <div class="mb-4">
      <label class="block text-sm font-medium mb-1">Descripción (Español)</label>
      <textarea name="description_es" rows="2"
                class="w-full border rounded px-3 py-2">{{ prop.description.get('es', '') if prop else '' }}</textarea>
    </div>
    <div class="mb-4">
      <label class="block text-sm font-medium mb-1">Descripción (English)</label>
      <textarea name="description_en" rows="2"
                class="w-full border rounded px-3 py-2">{{ prop.description.get('en', '') if prop else '' }}</textarea>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div>
        <label class="block text-sm font-medium mb-1">Ciudad</label>
        <input type="text" name="city" value="{{ prop.city or '' if prop else '' }}"
               class="w-full border rounded px-3 py-2">
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">País</label>
        <input type="text" name="country" value="{{ prop.country or '' if prop else '' }}"
               class="w-full border rounded px-3 py-2">
      </div>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-6">
      <div>
        <label class="block text-sm font-medium mb-1">Moneda (USD, ARS…)</label>
        <input type="text" name="currency" value="{{ prop.currency if prop else 'USD' }}" maxlength="3"
               class="w-full border rounded px-3 py-2">
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Idioma (es, en)</label>
        <input type="text" name="locale" value="{{ prop.locale if prop else 'es' }}"
               class="w-full border rounded px-3 py-2">
      </div>
    </div>
    {% if prop %}
    <div class="mb-6">
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="is_published" value="1" {{ 'checked' if prop.is_published else '' }}>
        Publicar propiedad
      </label>
    </div>
    {% endif %}
    <div class="flex gap-3">
      <button type="submit"
              class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 font-medium">
        {{ 'Guardar cambios' if prop else 'Crear propiedad' }}
      </button>
      <a href="/dashboard/properties" class="text-gray-600 hover:underline self-center text-sm">Cancelar</a>
    </div>
  </form>
  {% if prop %}
  <div class="mt-8 border-t pt-6">
    <form method="post" action="/dashboard/properties/{{ prop.id }}/delete"
          onsubmit="return confirm('¿Eliminar esta propiedad?')">
      <button class="text-red-600 text-sm hover:underline">Eliminar propiedad</button>
    </form>
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Update `app/templates/dashboard/index.html`**

```html
{% extends "base.html" %}
{% block title %}Dashboard — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <h1 class="text-2xl font-bold mb-2">Bienvenido, {{ user.full_name }}</h1>
  <p class="text-gray-600 mb-6">Panel de administración de tu hotel.</p>
  <div class="flex gap-4">
    <a href="/dashboard/properties"
       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm font-medium">
      Mis propiedades
    </a>
  </div>
  <form method="post" action="/logout" class="mt-6">
    <button type="submit" class="text-sm text-red-600 hover:underline">Cerrar sesión</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Create `app/hotels/router.py`** (properties only for now)

```python
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.core.database import get_db
from app.core.templates import templates
from app.hotels.models import Property
from app.hotels.schemas import PropertyCreate, PropertyUpdate
from app.hotels.service import (
    create_property,
    delete_property,
    get_properties_by_user,
    get_property_by_id,
    get_property_by_slug,
    update_property,
)

router = APIRouter()


async def _get_property_or_404(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
) -> Property:
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    return prop


# ── Properties ────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties", response_class=HTMLResponse)
async def properties_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    props = await get_properties_by_user(db, user.id)
    return templates.TemplateResponse(
        request, "dashboard/properties/list.html", {"user": user, "properties": props}
    )


@router.get("/dashboard/properties/new", response_class=HTMLResponse)
async def new_property_page(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        request, "dashboard/properties/form.html", {"user": user, "prop": None}
    )


@router.post("/dashboard/properties/new", response_class=HTMLResponse)
async def create_property_route(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description_es: str = Form(""),
    description_en: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    country: str = Form(""),
    currency: str = Form("USD"),
    locale: str = Form("es"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        form = PropertyCreate(
            name=name,
            slug=slug,
            description_es=description_es,
            description_en=description_en,
            address=address or None,
            city=city or None,
            country=country or None,
            currency=currency,
            locale=locale,
        )
    except ValidationError as e:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/form.html",
            {"user": user, "prop": None, "error": e.errors()[0]["msg"]},
            status_code=422,
        )

    existing = await get_property_by_slug(db, form.slug)
    if existing:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/form.html",
            {"user": user, "prop": None, "error": "Ese slug ya está en uso"},
            status_code=400,
        )

    prop = await create_property(db, user.id, form)
    return RedirectResponse(
        url=f"/dashboard/properties/{prop.id}/edit", status_code=303
    )


@router.get("/dashboard/properties/{id}/edit", response_class=HTMLResponse)
async def edit_property_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request, "dashboard/properties/form.html", {"user": user, "prop": prop}
    )


@router.post("/dashboard/properties/{id}/edit", response_class=HTMLResponse)
async def update_property_route(
    request: Request,
    id: uuid.UUID,
    name: str = Form(None),
    description_es: str = Form(None),
    description_en: str = Form(None),
    address: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    currency: str = Form(None),
    locale: str = Form(None),
    is_published: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    form = PropertyUpdate(
        name=name or None,
        description_es=description_es,
        description_en=description_en,
        address=address or None,
        city=city or None,
        country=country or None,
        currency=currency or None,
        locale=locale or None,
        is_published=is_published == "1" if is_published is not None else None,
    )
    await update_property(db, prop, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/edit", status_code=303)


@router.post("/dashboard/properties/{id}/delete")
async def delete_property_route(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    await delete_property(db, prop)
    return RedirectResponse(url="/dashboard/properties", status_code=303)
```

- [ ] **Step 7: Update `app/main.py`**

Add the hotels router import and registration. Read the current `app/main.py` first, then add:

```python
from app.hotels.router import router as hotels_router
```

And add `app.include_router(hotels_router)` after the existing router includes.

- [ ] **Step 8: Run property route tests**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_property_routes.py -v --no-cov 2>&1
```

Expected: `8 passed`

- [ ] **Step 9: Run full suite**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest --no-cov -q 2>&1
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/router.py app/main.py app/templates/dashboard/ tests/hotels/test_property_routes.py && git commit -m "feat: add property dashboard routes and templates"
```

---

### Task 4: Room CRUD routes + templates

**Files:**
- Modify: `app/hotels/router.py` (add room routes)
- Create: `app/templates/dashboard/properties/rooms/list.html`
- Create: `app/templates/dashboard/properties/rooms/form.html`
- Create: `tests/hotels/test_room_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hotels/test_room_routes.py`:

```python
import pytest
from decimal import Decimal
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_rooms_list_authenticated(async_client, db_session):
    user = make_user(email="rooms_list@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "rooms_list@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="rooms-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/rooms")
    assert response.status_code == 200
    assert "habitaci" in response.text.lower() or "room" in response.text.lower()


async def test_create_room_success(async_client, db_session):
    user = make_user(email="room_create@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "room_create@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="create-room-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/new",
        data={
            "name_es": "Suite ejecutiva",
            "name_en": "Executive suite",
            "capacity": "2",
            "base_price": "150.00",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


async def test_create_room_other_user_property_returns_404(async_client, db_session):
    owner = make_user(email="owner_rooms@example.com")
    other = make_user(email="other_rooms@example.com")
    db_session.add_all([owner, other])
    await db_session.flush()

    prop = make_property(user_id=owner.id, slug="protected-hotel")
    db_session.add(prop)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "other_rooms@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/new",
        data={"name_es": "Suite", "capacity": "2", "base_price": "100.00"},
    )
    assert response.status_code == 404


async def test_delete_room(async_client, db_session):
    user = make_user(email="del_room@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "del_room@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="del-room-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/rooms/{room.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
```

- [ ] **Step 2: Create `app/templates/dashboard/properties/rooms/list.html`**

```html
{% extends "base.html" %}
{% block title %}Habitaciones — {{ prop.name }} — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <div class="flex justify-between items-center mb-6">
    <div>
      <a href="/dashboard/properties" class="text-sm text-gray-500 hover:underline">← Propiedades</a>
      <h1 class="text-2xl font-bold mt-1">Habitaciones — {{ prop.name }}</h1>
    </div>
    <a href="/dashboard/properties/{{ prop.id }}/rooms/new"
       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm font-medium">
      + Nueva habitación
    </a>
  </div>
  {% if rooms %}
  <div class="grid gap-4">
    {% for room in rooms %}
    <div class="bg-white rounded-xl shadow p-5 flex justify-between items-start">
      <div>
        <h2 class="text-lg font-semibold">{{ room.name.get('es', '') }}</h2>
        <p class="text-sm text-gray-500">Capacidad: {{ room.capacity }} · Precio base: {{ room.base_price }} {{ prop.currency }}</p>
        <span class="text-xs {{ 'text-green-600' if room.is_active else 'text-gray-400' }}">
          {{ 'Activa' if room.is_active else 'Inactiva' }}
        </span>
      </div>
      <div class="flex gap-3 text-sm">
        <a href="/dashboard/properties/{{ prop.id }}/rooms/{{ room.id }}/edit"
           class="text-gray-600 hover:underline">Editar</a>
        <a href="/dashboard/properties/{{ prop.id }}/availability?room_id={{ room.id }}"
           class="text-blue-600 hover:underline">Disponibilidad</a>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <p class="text-gray-500">No hay habitaciones aún.</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Create `app/templates/dashboard/properties/rooms/form.html`**

```html
{% extends "base.html" %}
{% block title %}{{ 'Editar' if room else 'Nueva' }} habitación — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8 max-w-xl">
  <a href="/dashboard/properties/{{ prop.id }}/rooms" class="text-sm text-gray-500 hover:underline">← Habitaciones</a>
  <h1 class="text-2xl font-bold mt-2 mb-6">{{ 'Editar habitación' if room else 'Nueva habitación' }}</h1>
  {% if error %}
  <div class="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{{ error }}</div>
  {% endif %}
  <form method="post">
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div>
        <label class="block text-sm font-medium mb-1">Nombre (Español)</label>
        <input type="text" name="name_es" value="{{ room.name.get('es','') if room else '' }}" required
               class="w-full border rounded px-3 py-2">
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Name (English)</label>
        <input type="text" name="name_en" value="{{ room.name.get('en','') if room else '' }}"
               class="w-full border rounded px-3 py-2">
      </div>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div>
        <label class="block text-sm font-medium mb-1">Capacidad (personas)</label>
        <input type="number" name="capacity" min="1"
               value="{{ room.capacity if room else '2' }}"
               class="w-full border rounded px-3 py-2">
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Precio base</label>
        <input type="number" name="base_price" min="0" step="0.01"
               value="{{ room.base_price if room else '' }}" required
               class="w-full border rounded px-3 py-2">
      </div>
    </div>
    <div class="mb-6">
      <label class="block text-sm font-medium mb-1">Amenidades (separadas por comas)</label>
      <input type="text" name="amenities"
             value="{{ room.amenities | join(', ') if room else '' }}"
             placeholder="wifi, ac, tv"
             class="w-full border rounded px-3 py-2">
    </div>
    {% if room %}
    <div class="mb-6">
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="is_active" value="1" {{ 'checked' if room.is_active else '' }}>
        Habitación activa
      </label>
    </div>
    {% endif %}
    <div class="flex gap-3">
      <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 font-medium">
        {{ 'Guardar cambios' if room else 'Crear habitación' }}
      </button>
      <a href="/dashboard/properties/{{ prop.id }}/rooms" class="text-gray-600 hover:underline self-center text-sm">Cancelar</a>
    </div>
  </form>
  {% if room %}
  <div class="mt-8 border-t pt-6">
    <form method="post" action="/dashboard/properties/{{ prop.id }}/rooms/{{ room.id }}/delete"
          onsubmit="return confirm('¿Eliminar esta habitación?')">
      <button class="text-red-600 text-sm hover:underline">Eliminar habitación</button>
    </form>
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 4: Add room routes to `app/hotels/router.py`**

Add these imports at the top:
```python
from app.hotels.schemas import RoomCreate, RoomUpdate
from app.hotels.service import (
    create_room, get_rooms_by_property, get_room_by_id, update_room, delete_room,
)
```

Add these routes at the end of the file:

```python
# ── Rooms ─────────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/rooms", response_class=HTMLResponse)
async def rooms_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    rooms = await get_rooms_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/list.html",
        {"user": user, "prop": prop, "rooms": rooms},
    )


@router.get("/dashboard/properties/{id}/rooms/new", response_class=HTMLResponse)
async def new_room_page(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    user: User = Depends(require_auth),
):
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/form.html",
        {"user": user, "prop": prop, "room": None},
    )


@router.post("/dashboard/properties/{id}/rooms/new", response_class=HTMLResponse)
async def create_room_route(
    request: Request,
    id: uuid.UUID,
    name_es: str = Form(...),
    name_en: str = Form(""),
    description_es: str = Form(""),
    description_en: str = Form(""),
    capacity: int = Form(2),
    base_price: str = Form(...),
    amenities: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    try:
        from decimal import Decimal
        form = RoomCreate(
            name_es=name_es,
            name_en=name_en,
            description_es=description_es,
            description_en=description_en,
            capacity=capacity,
            base_price=Decimal(base_price),
            amenities=[a.strip() for a in amenities.split(",") if a.strip()],
        )
    except (ValidationError, Exception) as e:
        return templates.TemplateResponse(
            request,
            "dashboard/properties/rooms/form.html",
            {"user": user, "prop": prop, "room": None, "error": str(e)},
            status_code=422,
        )

    await create_room(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/rooms", status_code=303)


@router.get("/dashboard/properties/{id}/rooms/{rid}/edit", response_class=HTMLResponse)
async def edit_room_page(
    request: Request,
    id: uuid.UUID,
    rid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    room = await get_room_by_id(db, rid)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/rooms/form.html",
        {"user": user, "prop": prop, "room": room},
    )


@router.post("/dashboard/properties/{id}/rooms/{rid}/edit", response_class=HTMLResponse)
async def update_room_route(
    request: Request,
    id: uuid.UUID,
    rid: uuid.UUID,
    name_es: str = Form(None),
    name_en: str = Form(None),
    capacity: int = Form(None),
    base_price: str = Form(None),
    amenities: str = Form(None),
    is_active: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    room = await get_room_by_id(db, rid)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)

    from decimal import Decimal
    form = RoomUpdate(
        name_es=name_es,
        name_en=name_en,
        capacity=capacity,
        base_price=Decimal(base_price) if base_price else None,
        amenities=[a.strip() for a in amenities.split(",") if a.strip()] if amenities is not None else None,
        is_active=is_active == "1" if is_active is not None else None,
    )
    await update_room(db, room, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/rooms", status_code=303)


@router.post("/dashboard/properties/{id}/rooms/{rid}/delete")
async def delete_room_route(
    id: uuid.UUID,
    rid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    room = await get_room_by_id(db, rid)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)
    await delete_room(db, room)
    return RedirectResponse(url=f"/dashboard/properties/{id}/rooms", status_code=303)
```

- [ ] **Step 5: Run room route tests**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_room_routes.py -v --no-cov 2>&1
```

Expected: `4 passed`

- [ ] **Step 6: Run full suite**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest --no-cov -q 2>&1
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/router.py app/templates/dashboard/properties/rooms/ tests/hotels/test_room_routes.py && git commit -m "feat: add room management routes and templates"
```

---

## Chunk 3: Services, Promotions, and Availability Routes

### File Map

| File | Responsibility |
|---|---|
| `app/hotels/router.py` | Add services, promotions, availability routes |
| `app/templates/dashboard/properties/services/list.html` | Services management |
| `app/templates/dashboard/properties/promotions/list.html` | Promotions management |
| `app/templates/dashboard/properties/availability/calendar.html` | Availability calendar |
| `tests/hotels/test_services_promotions_routes.py` | Services + promotions route tests |
| `tests/hotels/test_availability_routes.py` | Availability route tests |

---

### Task 5: Services + Promotions routes + templates

**Files:**
- Modify: `app/hotels/router.py`
- Create: `app/templates/dashboard/properties/services/list.html`
- Create: `app/templates/dashboard/properties/promotions/list.html`
- Create: `tests/hotels/test_services_promotions_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hotels/test_services_promotions_routes.py`:

```python
import pytest
from tests.auth.factories import make_user
from tests.hotels.factories import make_property


async def test_services_list(async_client, db_session):
    user = make_user(email="svc_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "svc_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="svc-hotel-route")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/services")
    assert response.status_code == 200
    assert "servicio" in response.text.lower() or "service" in response.text.lower()


async def test_create_service(async_client, db_session):
    user = make_user(email="create_svc@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "create_svc@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="svc-create-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/services/new",
        data={"name_es": "Desayuno", "price": "12.00", "is_included": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303


async def test_promotions_list(async_client, db_session):
    user = make_user(email="promo_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "promo_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="promo-hotel-route")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/promotions")
    assert response.status_code == 200
    assert "promoci" in response.text.lower() or "promo" in response.text.lower()


async def test_create_promotion(async_client, db_session):
    user = make_user(email="create_promo@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "create_promo@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="promo-create-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/promotions/new",
        data={
            "name_es": "Verano",
            "discount_type": "percent",
            "discount_value": "10.00",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "min_nights": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
```

- [ ] **Step 2: Create `app/templates/dashboard/properties/services/list.html`**

```html
{% extends "base.html" %}
{% block title %}Servicios — {{ prop.name }} — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <a href="/dashboard/properties" class="text-sm text-gray-500 hover:underline">← Propiedades</a>
  <h1 class="text-2xl font-bold mt-2 mb-6">Servicios — {{ prop.name }}</h1>
  {% if error %}
  <div class="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{{ error }}</div>
  {% endif %}
  <div class="grid grid-cols-2 gap-8">
    <div>
      <h2 class="font-semibold mb-4">Servicios existentes</h2>
      {% if services %}
      <div class="space-y-3">
        {% for svc in services %}
        <div class="bg-white rounded-lg shadow p-4 flex justify-between items-center">
          <div>
            <p class="font-medium">{{ svc.name.get('es', '') }}</p>
            <p class="text-sm text-gray-500">
              {{ 'Incluido' if svc.is_included else svc.price ~ ' ' ~ prop.currency }}
            </p>
          </div>
          <form method="post" action="/dashboard/properties/{{ prop.id }}/services/{{ svc.id }}/delete">
            <button class="text-red-500 text-xs hover:underline">Eliminar</button>
          </form>
        </div>
        {% endfor %}
      </div>
      {% else %}
      <p class="text-gray-500 text-sm">No hay servicios aún.</p>
      {% endif %}
    </div>
    <div>
      <h2 class="font-semibold mb-4">Agregar servicio</h2>
      <form method="post" action="/dashboard/properties/{{ prop.id }}/services/new" class="bg-white rounded-lg shadow p-4">
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Nombre (Español)</label>
          <input type="text" name="name_es" required class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Name (English)</label>
          <input type="text" name="name_en" class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Precio</label>
          <input type="number" name="price" step="0.01" min="0" value="0" class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <div class="mb-4">
          <label class="flex items-center gap-2 text-sm">
            <input type="checkbox" name="is_included" value="1">
            Incluido en la tarifa
          </label>
        </div>
        <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
          Agregar servicio
        </button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create `app/templates/dashboard/properties/promotions/list.html`**

```html
{% extends "base.html" %}
{% block title %}Promociones — {{ prop.name }} — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <a href="/dashboard/properties" class="text-sm text-gray-500 hover:underline">← Propiedades</a>
  <h1 class="text-2xl font-bold mt-2 mb-6">Promociones — {{ prop.name }}</h1>
  {% if error %}
  <div class="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{{ error }}</div>
  {% endif %}
  <div class="grid grid-cols-2 gap-8">
    <div>
      <h2 class="font-semibold mb-4">Promociones activas</h2>
      {% if promotions %}
      <div class="space-y-3">
        {% for promo in promotions %}
        <div class="bg-white rounded-lg shadow p-4 flex justify-between items-center">
          <div>
            <p class="font-medium">{{ promo.name.get('es', '') }}</p>
            <p class="text-sm text-gray-500">
              {{ promo.discount_value }}{{ '%' if promo.discount_type == 'percent' else (' ' ~ prop.currency) }} ·
              Mín. {{ promo.min_nights }} noches ·
              {{ promo.valid_from }} – {{ promo.valid_until }}
            </p>
          </div>
          <form method="post" action="/dashboard/properties/{{ prop.id }}/promotions/{{ promo.id }}/delete">
            <button class="text-red-500 text-xs hover:underline">Eliminar</button>
          </form>
        </div>
        {% endfor %}
      </div>
      {% else %}
      <p class="text-gray-500 text-sm">No hay promociones aún.</p>
      {% endif %}
    </div>
    <div>
      <h2 class="font-semibold mb-4">Agregar promoción</h2>
      <form method="post" action="/dashboard/properties/{{ prop.id }}/promotions/new" class="bg-white rounded-lg shadow p-4">
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Nombre (Español)</label>
          <input type="text" name="name_es" required class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Tipo de descuento</label>
          <select name="discount_type" class="w-full border rounded px-3 py-2 text-sm">
            <option value="percent">Porcentaje (%)</option>
            <option value="fixed">Monto fijo</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="block text-sm font-medium mb-1">Valor del descuento</label>
          <input type="number" name="discount_value" step="0.01" min="0" required class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label class="block text-sm font-medium mb-1">Válido desde</label>
            <input type="date" name="valid_from" required class="w-full border rounded px-3 py-2 text-sm">
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Válido hasta</label>
            <input type="date" name="valid_until" required class="w-full border rounded px-3 py-2 text-sm">
          </div>
        </div>
        <div class="mb-4">
          <label class="block text-sm font-medium mb-1">Mínimo de noches</label>
          <input type="number" name="min_nights" min="1" value="1" class="w-full border rounded px-3 py-2 text-sm">
        </div>
        <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
          Agregar promoción
        </button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Add services + promotions routes to `app/hotels/router.py`**

Add these imports at the top of `app/hotels/router.py`:
```python
from app.hotels.schemas import ServiceCreate, PromotionCreate
from app.hotels.service import (
    create_service, get_services_by_property, delete_service_item,
    create_promotion, get_promotions_by_property, delete_promotion,
)
```

Add these routes at the end of the file:

```python
# ── Services ──────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/services", response_class=HTMLResponse)
async def services_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    svcs = await get_services_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/services/list.html",
        {"user": user, "prop": prop, "services": svcs},
    )


@router.post("/dashboard/properties/{id}/services/new")
async def create_service_route(
    id: uuid.UUID,
    name_es: str = Form(...),
    name_en: str = Form(""),
    description_es: str = Form(""),
    price: str = Form("0.00"),
    is_included: str = Form("0"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    from decimal import Decimal
    form = ServiceCreate(
        name_es=name_es,
        name_en=name_en,
        description_es=description_es,
        price=Decimal(price),
        is_included=is_included == "1",
    )
    await create_service(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/services", status_code=303)


@router.post("/dashboard/properties/{id}/services/{sid}/delete")
async def delete_service_route(
    id: uuid.UUID,
    sid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    from app.hotels.models import Service
    from sqlalchemy import select
    result = await db.execute(select(Service).where(Service.id == sid, Service.property_id == prop.id))
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404)
    await delete_service_item(db, svc)
    return RedirectResponse(url=f"/dashboard/properties/{id}/services", status_code=303)


# ── Promotions ────────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/promotions", response_class=HTMLResponse)
async def promotions_list(
    request: Request,
    prop: Property = Depends(_get_property_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    promos = await get_promotions_by_property(db, prop.id)
    return templates.TemplateResponse(
        request,
        "dashboard/properties/promotions/list.html",
        {"user": user, "prop": prop, "promotions": promos},
    )


@router.post("/dashboard/properties/{id}/promotions/new")
async def create_promotion_route(
    id: uuid.UUID,
    name_es: str = Form(...),
    name_en: str = Form(""),
    discount_type: str = Form(...),
    discount_value: str = Form(...),
    valid_from: str = Form(...),
    valid_until: str = Form(...),
    min_nights: int = Form(1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    from datetime import date
    from decimal import Decimal
    form = PromotionCreate(
        name_es=name_es,
        name_en=name_en,
        discount_type=discount_type,
        discount_value=Decimal(discount_value),
        valid_from=date.fromisoformat(valid_from),
        valid_until=date.fromisoformat(valid_until),
        min_nights=min_nights,
    )
    await create_promotion(db, prop.id, form)
    return RedirectResponse(url=f"/dashboard/properties/{id}/promotions", status_code=303)


@router.post("/dashboard/properties/{id}/promotions/{pid}/delete")
async def delete_promotion_route(
    id: uuid.UUID,
    pid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)
    from app.hotels.models import Promotion
    from sqlalchemy import select
    result = await db.execute(select(Promotion).where(Promotion.id == pid, Promotion.property_id == prop.id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404)
    await delete_promotion(db, promo)
    return RedirectResponse(url=f"/dashboard/properties/{id}/promotions", status_code=303)
```

- [ ] **Step 5: Run services + promotions tests**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_services_promotions_routes.py -v --no-cov 2>&1
```

Expected: `4 passed`

- [ ] **Step 6: Run full suite**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest --no-cov -q 2>&1
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/router.py app/templates/dashboard/properties/services/ app/templates/dashboard/properties/promotions/ tests/hotels/test_services_promotions_routes.py && git commit -m "feat: add services and promotions dashboard routes"
```

---

### Task 6: Availability management routes + templates

**Files:**
- Modify: `app/hotels/router.py`
- Create: `app/templates/dashboard/properties/availability/calendar.html`
- Create: `tests/hotels/test_availability_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hotels/test_availability_routes.py`:

```python
import pytest
from tests.auth.factories import make_user
from tests.hotels.factories import make_property, make_room


async def test_availability_page_renders(async_client, db_session):
    user = make_user(email="avail_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-route-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.get(
        f"/dashboard/properties/{prop.id}/availability?room_id={room.id}&year=2026&month=6"
    )
    assert response.status_code == 200
    assert "disponibilidad" in response.text.lower() or "availability" in response.text.lower()


async def test_availability_page_no_rooms(async_client, db_session):
    user = make_user(email="avail_empty@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_empty@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-empty-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/availability")
    assert response.status_code == 200


async def test_save_availability_blocks(async_client, db_session):
    user = make_user(email="avail_save@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "avail_save@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="avail-save-hotel")
    db_session.add(prop)
    await db_session.flush()

    room = make_room(property_id=prop.id)
    db_session.add(room)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/availability",
        data={
            "room_id": str(room.id),
            "year": "2026",
            "month": "6",
            "blocked_dates": ["2026-06-10", "2026-06-11"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
```

- [ ] **Step 2: Create `app/templates/dashboard/properties/availability/calendar.html`**

```html
{% extends "base.html" %}
{% block title %}Disponibilidad — {{ prop.name }} — Sistema Hotel{% endblock %}
{% block content %}
<div class="p-8">
  <a href="/dashboard/properties/{{ prop.id }}/rooms" class="text-sm text-gray-500 hover:underline">← Habitaciones</a>
  <h1 class="text-2xl font-bold mt-2 mb-2">Disponibilidad — {{ prop.name }}</h1>

  {% if not rooms %}
  <p class="text-gray-500">No hay habitaciones. <a href="/dashboard/properties/{{ prop.id }}/rooms/new" class="text-blue-600 hover:underline">Crear una</a>.</p>
  {% else %}
  <div class="mb-4 flex gap-4 items-end">
    <div>
      <label class="block text-sm font-medium mb-1">Habitación</label>
      <select id="room-select" onchange="location.href='/dashboard/properties/{{ prop.id }}/availability?room_id='+this.value+'&year={{ year }}&month={{ month }}'"
              class="border rounded px-3 py-2 text-sm">
        {% for r in rooms %}
        <option value="{{ r.id }}" {{ 'selected' if r.id == selected_room_id else '' }}>
          {{ r.name.get('es', '') }}
        </option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">Mes</label>
      <div class="flex gap-2">
        <a href="?room_id={{ selected_room_id }}&year={{ prev_year }}&month={{ prev_month }}"
           class="border rounded px-3 py-2 text-sm hover:bg-gray-50">←</a>
        <span class="border rounded px-3 py-2 text-sm bg-white">{{ month_name }} {{ year }}</span>
        <a href="?room_id={{ selected_room_id }}&year={{ next_year }}&month={{ next_month }}"
           class="border rounded px-3 py-2 text-sm hover:bg-gray-50">→</a>
      </div>
    </div>
  </div>

  {% if selected_room_id %}
  <form method="post" action="/dashboard/properties/{{ prop.id }}/availability">
    <input type="hidden" name="room_id" value="{{ selected_room_id }}">
    <input type="hidden" name="year" value="{{ year }}">
    <input type="hidden" name="month" value="{{ month }}">
    <div class="bg-white rounded-xl shadow p-4 mb-4">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-500">
            {% for day_name in ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do'] %}
            <th class="py-2 text-center font-medium">{{ day_name }}</th>
            {% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for week in calendar_weeks %}
          <tr>
            {% for day in week %}
            <td class="py-1 text-center">
              {% if day %}
              <label class="block cursor-pointer">
                <input type="checkbox" name="blocked_dates" value="{{ day.date_str }}"
                       {{ 'checked' if day.is_blocked else '' }}
                       class="sr-only peer">
                <span class="inline-block w-8 h-8 rounded-full flex items-center justify-center text-xs
                             peer-checked:bg-red-500 peer-checked:text-white
                             hover:bg-gray-100">
                  {{ day.day }}
                </span>
              </label>
              {% endif %}
            </td>
            {% endfor %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <p class="text-xs text-gray-500 mb-3">Las fechas marcadas en rojo quedarán bloqueadas.</p>
    <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 font-medium">
      Guardar disponibilidad
    </button>
  </form>
  {% endif %}
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Add availability routes to `app/hotels/router.py`**

Add these imports at the top:
```python
from app.hotels.service import (
    upsert_availability, get_availability_for_month, get_rooms_by_property,
)
```

Add these routes at the end of the file:

```python
# ── Availability ──────────────────────────────────────────────────────────────


@router.get("/dashboard/properties/{id}/availability", response_class=HTMLResponse)
async def availability_page(
    request: Request,
    id: uuid.UUID,
    room_id: uuid.UUID | None = None,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    import calendar
    from datetime import date as date_type

    today = date_type.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    rooms = await get_rooms_by_property(db, prop.id)
    selected_room_id = room_id or (rooms[0].id if rooms else None)

    # Build calendar weeks with availability data
    calendar_weeks = []
    blocked_date_set: set[date_type] = set()

    if selected_room_id:
        avail_records = await get_availability_for_month(db, selected_room_id, year, month)
        blocked_date_set = {r.date for r in avail_records if r.is_blocked}

    if selected_room_id or True:
        cal = calendar.monthcalendar(year, month)
        for week in cal:
            week_days = []
            for day_num in week:
                if day_num == 0:
                    week_days.append(None)
                else:
                    d = date_type(year, month, day_num)
                    week_days.append({
                        "day": day_num,
                        "date_str": d.isoformat(),
                        "is_blocked": d in blocked_date_set,
                    })
            calendar_weeks.append(week_days)

    # Prev/next month navigation
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year = year + 1 if month == 12 else year

    import locale as _locale
    month_names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    month_name = month_names[month - 1]

    return templates.TemplateResponse(
        request,
        "dashboard/properties/availability/calendar.html",
        {
            "user": user,
            "prop": prop,
            "rooms": rooms,
            "selected_room_id": selected_room_id,
            "year": year,
            "month": month,
            "month_name": month_name,
            "calendar_weeks": calendar_weeks,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
        },
    )


@router.post("/dashboard/properties/{id}/availability")
async def save_availability(
    request: Request,
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    prop = await get_property_by_id(db, id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404)

    form_data = await request.form()
    room_id_str = form_data.get("room_id")
    year = int(form_data.get("year", 2026))
    month = int(form_data.get("month", 1))

    if not room_id_str:
        return RedirectResponse(url=f"/dashboard/properties/{id}/availability", status_code=303)

    room_id = uuid.UUID(room_id_str)
    # Verify room belongs to property
    room = await get_room_by_id(db, room_id)
    if not room or room.property_id != prop.id:
        raise HTTPException(status_code=404)

    # All checked dates from the form
    blocked_dates = set(form_data.getlist("blocked_dates"))

    # Process all days in the month
    import calendar
    from datetime import date as date_type

    _, days_in_month = calendar.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date_type(year, month, day)
        is_blocked = d.isoformat() in blocked_dates
        await upsert_availability(db, room_id, d, is_blocked=is_blocked)

    return RedirectResponse(
        url=f"/dashboard/properties/{id}/availability?room_id={room_id}&year={year}&month={month}",
        status_code=303,
    )
```

- [ ] **Step 4: Run availability tests**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest tests/hotels/test_availability_routes.py -v --no-cov 2>&1
```

Expected: `3 passed`

- [ ] **Step 5: Run full suite**

```bash
cd /home/fabi/code/sistemahotel && source venv/bin/activate && pytest --no-cov -q 2>&1
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/fabi/code/sistemahotel && git add app/hotels/router.py app/templates/dashboard/properties/availability/ tests/hotels/test_availability_routes.py && git commit -m "feat: add availability management routes and calendar"
```

---

## Chunk 3 Summary

At the end of Plan 3 you have:

- **5 models:** Property, Room, RoomAvailability, Service, Promotion — with Alembic migration applied
- **Service layer:** full CRUD for all entities + availability block management + `get_blocked_dates_in_range` for Plan 5
- **Dashboard routes:** complete CRUD UI for properties, rooms, services, promotions, and availability calendar
- **Slug-unique properties** per user with i18n description fields
- **Per-room availability blocks** with monthly calendar UI
- All tests green

**Next:** Plan 4 — Billing (Stripe subscriptions, plan enforcement on dashboard)
