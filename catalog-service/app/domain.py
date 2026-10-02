"""Domain vocabulary shared by the ORM models and the API schemas.

Pure Python only: this module must not import SQLAlchemy or Pydantic, so that
models.py and schemas.py can both depend on it without depending on each other.
"""

from enum import IntEnum, StrEnum


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


SKU_MAX_LENGTH = 64
SKU_PATTERN = r"^[A-Z0-9][A-Z0-9-]*$"
MANUFACTURER_MAX_LENGTH = 100
FINISH_MAX_LENGTH = 32

# Door hardware is almost always 12 or 24 VDC; 48 leaves headroom without accepting nonsense.
VOLTAGE_MIN_EXCLUSIVE = 0
VOLTAGE_MAX = 48

# Listings and standards a product is certified to, e.g. "UL 10C" or "ANSI/BHMA A156.13 Grade 1".
CERTIFICATION_MAX_LENGTH = 64
MAX_CERTIFICATIONS_PER_PRODUCT = 20
