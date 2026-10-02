"""Unit tests for the product API contract."""

import pytest
from pydantic import ValidationError
from pytest_check import check

from app.schemas import ProductCreate, ProductRead, ProductUpdate

VALID = {
    "sku": "LCK-100",
    "category": "lock",
    "manufacturer": "Corbin Russwin",
    "fire_rating_minutes": 90,
    "material": "hollow_metal",
    "electrified": True,
    "voltage": 24,
    "finish": "626",
}

NOT_ELECTRIFIED = {**VALID, "electrified": False, "voltage": None}


def test_create_accepts_valid_product():
    product = ProductCreate(**VALID)
    with check:
        assert product.sku == "LCK-100"
    with check:
        assert product.voltage == 24


def test_create_accepts_non_electrified_product_without_voltage():
    assert ProductCreate(**NOT_ELECTRIFIED).voltage is None


def test_create_strips_whitespace():
    product = ProductCreate(**{**VALID, "sku": "  LCK-100 ", "manufacturer": " Corbin Russwin "})
    with check:
        assert product.sku == "LCK-100"
    with check:
        assert product.manufacturer == "Corbin Russwin"


@pytest.mark.parametrize(
    "field, value",
    [
        ("sku", "A" * 64),
        ("voltage", 1),
        ("voltage", 48),
        ("fire_rating_minutes", 0),
        ("fire_rating_minutes", 180),
        ("manufacturer", "M" * 100),
        ("finish", "F" * 32),
    ],
)
def test_create_accepts_boundary_values(field, value):
    ProductCreate(**{**VALID, field: value})


@pytest.mark.parametrize(
    "field, value",
    [
        ("sku", ""),
        ("sku", "   "),  # empty after stripping
        ("sku", "lck-100"),
        ("sku", "-LCK"),
        ("sku", "LCK 100"),
        ("sku", "A" * 65),
        ("category", "doorknob"),
        ("material", "steel"),
        ("fire_rating_minutes", 30),
        ("manufacturer", ""),
        ("manufacturer", "M" * 101),
        ("finish", ""),
        ("finish", "F" * 33),
        ("voltage", 0),
        ("voltage", -5),
        ("voltage", 49),
    ],
)
def test_create_rejects_invalid_field(field, value):
    with pytest.raises(ValidationError) as exc:
        ProductCreate(**{**VALID, field: value})
    assert exc.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "field",
    ["sku", "category", "manufacturer", "fire_rating_minutes", "material", "electrified", "finish"],
)
def test_create_requires_field(field):
    data = {k: v for k, v in VALID.items() if k != field}
    with pytest.raises(ValidationError):
        ProductCreate(**data)


def test_create_rejects_electrified_without_voltage():
    with pytest.raises(ValidationError, match="Voltage is required"):
        ProductCreate(**{**VALID, "voltage": None})


def test_create_rejects_voltage_on_non_electrified_product():
    with pytest.raises(ValidationError, match="Voltage must be omitted"):
        ProductCreate(**{**NOT_ELECTRIFIED, "voltage": 24})


def test_create_rejects_unknown_field():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProductCreate(**VALID, fire_raiting=60)  # pyright: ignore[reportCallIssue]


def test_read_does_not_enforce_input_rules():
    """A stored row that breaks a Create rule must still be readable, not a 500."""
    product = ProductRead(id=1, **{**VALID, "voltage": None})
    with check:
        assert product.electrified is True
    with check:
        assert product.voltage is None


def test_read_builds_from_object_attributes():
    class FakeRow:
        id = 7
        sku = "LCK-100"
        category = "lock"
        manufacturer = "Corbin Russwin"
        fire_rating_minutes = 90
        material = "hollow_metal"
        electrified = True
        voltage = 24
        finish = "626"

    product = ProductRead.model_validate(FakeRow())
    with check:
        assert product.id == 7
    with check:
        assert product.sku == "LCK-100"


def test_update_accepts_empty_body():
    assert ProductUpdate().model_dump(exclude_unset=True) == {}


def test_update_exclude_unset_returns_only_sent_fields():
    assert ProductUpdate(finish="626").model_dump(exclude_unset=True) == {"finish": "626"}


def test_update_allows_electrified_without_voltage():
    """The stored product may already have a voltage; the check runs after merging."""
    assert ProductUpdate(electrified=True).electrified is True


def test_update_allows_clearing_voltage_with_null():
    assert ProductUpdate(voltage=None).model_dump(exclude_unset=True) == {"voltage": None}


@pytest.mark.parametrize(
    "field",
    ["sku", "category", "manufacturer", "fire_rating_minutes", "material", "electrified", "finish"],
)
def test_update_rejects_null_for_non_nullable_field(field):
    with pytest.raises(ValidationError, match=f"{field} cannot be null"):
        ProductUpdate(**{field: None})


@pytest.mark.parametrize(
    "field, value",
    [
        ("sku", "lck-100"),
        ("sku", "A" * 65),
        ("voltage", 49),
        ("fire_rating_minutes", 30),
        ("manufacturer", ""),
    ],
)
def test_update_applies_same_field_constraints_as_create(field, value):
    with pytest.raises(ValidationError):
        ProductUpdate(**{field: value})


def test_update_rejects_unknown_field():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProductUpdate(finsh="626")


def test_update_strips_whitespace():
    assert ProductUpdate(sku=" LCK-100 ").sku == "LCK-100"
