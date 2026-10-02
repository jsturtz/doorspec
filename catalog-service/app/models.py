from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain import (
    FINISH_MAX_LENGTH,
    MANUFACTURER_MAX_LENGTH,
    SKU_MAX_LENGTH,
    VOLTAGE_MAX,
    VOLTAGE_MIN_EXCLUSIVE,
    CategoryEnum,
    FireRatingMinutesEnum,
    MaterialEnum,
)

SKU_UNIQUE_INDEX = "ix_products_sku"


def _string_enum(enum_cls: type[PyEnum], name: str) -> Enum:
    """A VARCHAR column restricted to the enum's values by a CHECK constraint.

    native_enum=False avoids a Postgres ENUM type (awkward to change, and Alembic leaves it behind
    on downgrade). values_callable stores "exit_device", not the member name "EXIT_DEVICE".
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )


_FIRE_RATINGS = ", ".join(str(rating.value) for rating in FireRatingMinutesEnum)


class Product(Base):
    """Represents a product in the catalog."""

    __tablename__ = "products"
    __table_args__ = (
        Index(SKU_UNIQUE_INDEX, "sku", unique=True),
        CheckConstraint(f"fire_rating_minutes IN ({_FIRE_RATINGS})", name="fire_rating_minutes"),
        CheckConstraint(
            f"voltage > {VOLTAGE_MIN_EXCLUSIVE} AND voltage <= {VOLTAGE_MAX}", name="voltage_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(SKU_MAX_LENGTH))
    category: Mapped[CategoryEnum] = mapped_column(_string_enum(CategoryEnum, "category"))
    manufacturer: Mapped[str] = mapped_column(String(MANUFACTURER_MAX_LENGTH))
    fire_rating_minutes: Mapped[int]
    material: Mapped[MaterialEnum] = mapped_column(_string_enum(MaterialEnum, "material"))
    electrified: Mapped[bool]
    voltage: Mapped[int | None]
    finish: Mapped[str] = mapped_column(String(FINISH_MAX_LENGTH))
