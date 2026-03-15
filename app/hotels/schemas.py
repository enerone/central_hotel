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
