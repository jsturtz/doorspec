from enum import IntEnum, StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CategoryEnum(StrEnum):
    """Enumeration of product categories."""

    LOCK = "lock"
    HINGE = "hinge"
    CLOSER = "closer"
    EXIT_DEVICE = "exit_device"
    POWER_SUPPLY = "power_supply"


class MaterialEnum(StrEnum):
    """Enumeration of product materials."""

    HOLLOW_METAL = "hollow_metal"
    WOOD = "wood"
    ALUMINUM = "aluminum"
    GLASS = "glass"


class FireRatingMinutesEnum(IntEnum):
    """Enumeration of fire ratings in minutes."""

    NONE = 0
    MIN_20 = 20
    MIN_45 = 45
    MIN_60 = 60
    MIN_90 = 90
    MIN_180 = 180


# Constrained types, defined once and shared by Create and Update so the rules can't drift apart.
Sku = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9-]*$")]
Manufacturer = Annotated[str, Field(min_length=1, max_length=100)]
Finish = Annotated[str, Field(min_length=1, max_length=32)]
Voltage = Annotated[int, Field(gt=0, le=48)]


class ProductBase(BaseModel):
    """Fields shared by every product schema. No config or validators here."""

    sku: Sku
    category: CategoryEnum
    manufacturer: Manufacturer
    fire_rating_minutes: FireRatingMinutesEnum
    material: MaterialEnum
    electrified: bool
    voltage: Voltage | None = None
    finish: Finish


class ProductCreate(ProductBase):
    """Schema for creating a new product."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def check_voltage_matches_electrified(self) -> Self:
        """Electrified products need a voltage; non-electrified products can't have one."""
        if self.electrified and self.voltage is None:
            raise ValueError("Voltage is required for electrified products.")
        if not self.electrified and self.voltage is not None:
            raise ValueError("Voltage must be omitted for non-electrified products.")
        return self


class ProductRead(ProductBase):
    """Schema for reading a product."""

    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductUpdate(BaseModel):
    """Schema for partially updating a product. Only fields the client sends are applied."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: Sku | None = None
    category: CategoryEnum | None = None
    manufacturer: Manufacturer | None = None
    fire_rating_minutes: FireRatingMinutesEnum | None = None
    material: MaterialEnum | None = None
    electrified: bool | None = None
    voltage: Voltage | None = None
    finish: Finish | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        """Reject null on fields that can't be cleared.

        Omitting a field means "leave it alone"; sending null means "clear it",
        which only voltage allows.
        """
        nullable = {"voltage"}
        for name in self.model_fields_set - nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self
