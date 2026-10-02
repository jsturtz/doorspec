from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain import (
    CERTIFICATION_MAX_LENGTH,
    FINISH_MAX_LENGTH,
    MANUFACTURER_MAX_LENGTH,
    MAX_CERTIFICATIONS_PER_PRODUCT,
    SKU_MAX_LENGTH,
    SKU_PATTERN,
    VOLTAGE_MAX,
    VOLTAGE_MIN_EXCLUSIVE,
    CategoryEnum,
    FireRatingMinutesEnum,
    MaterialEnum,
)

# Constrained types, defined once and shared by Create and Update so the rules can't drift apart.
Sku = Annotated[str, Field(min_length=1, max_length=SKU_MAX_LENGTH, pattern=SKU_PATTERN)]
Manufacturer = Annotated[str, Field(min_length=1, max_length=MANUFACTURER_MAX_LENGTH)]
Finish = Annotated[str, Field(min_length=1, max_length=FINISH_MAX_LENGTH)]
Voltage = Annotated[int, Field(gt=VOLTAGE_MIN_EXCLUSIVE, le=VOLTAGE_MAX)]
Standard = Annotated[str, Field(min_length=1, max_length=CERTIFICATION_MAX_LENGTH)]


class CertificationCreate(BaseModel):
    """A certification submitted with a product."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    standard: Standard


class CertificationRead(BaseModel):
    """A certification as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    standard: str


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

    certifications: list[CertificationCreate] = Field(
        default_factory=list, max_length=MAX_CERTIFICATIONS_PER_PRODUCT
    )

    @model_validator(mode="after")
    def check_certifications_unique(self) -> Self:
        """Each standard may appear at most once per product."""
        standards = [c.standard for c in self.certifications]
        if len(standards) != len(set(standards)):
            raise ValueError("Certifications must not contain duplicate standards.")
        return self

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
    certifications: list[CertificationRead]


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


class ProductPage(BaseModel):
    """One page of products from a keyset-paginated listing."""

    items: list[ProductRead]
    next_cursor: str | None = Field(
        description="Pass as `cursor` to fetch the next page. Null on the last page."
    )
