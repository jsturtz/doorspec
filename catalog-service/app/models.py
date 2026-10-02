from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain import (
    CERTIFICATION_MAX_LENGTH,
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
CERTIFICATION_UNIQUE = "uq_certifications_product_id"


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

    # Lazy by default: reading product.certifications on a loaded product issues its own SELECT.
    # List endpoints must eager-load with selectinload() or they become N+1 queries.
    certifications: Mapped[list[Certification]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,  # let ON DELETE CASCADE remove rows instead of loading them first
        order_by="Certification.id",
    )


class Certification(Base):
    """A standard or listing a product is certified to, e.g. "UL 10C"."""

    __tablename__ = "certifications"
    __table_args__ = (UniqueConstraint("product_id", "standard", name=CERTIFICATION_UNIQUE),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # No separate index: the unique (product_id, standard) index already serves product_id lookups.
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    standard: Mapped[str] = mapped_column(String(CERTIFICATION_MAX_LENGTH))

    product: Mapped[Product] = relationship(back_populates="certifications")
