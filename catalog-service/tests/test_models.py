"""Checks that the ORM model and the API schemas stay in sync. No database involved."""

from app.domain import CategoryEnum, MaterialEnum
from app.models import Product
from app.schemas import ProductBase, ProductRead


def test_read_schema_validates_from_model_instance():
    """Fails if a model column is renamed or retyped without updating the schema."""
    product = Product(
        id=1,
        sku="LCK-100",
        category=CategoryEnum.LOCK,
        manufacturer="Corbin Russwin",
        fire_rating_minutes=90,
        material=MaterialEnum.HOLLOW_METAL,
        electrified=True,
        voltage=24,
        finish="626",
    )
    read = ProductRead.model_validate(product)
    assert read.model_dump() == {
        "id": 1,
        "sku": "LCK-100",
        "category": "lock",
        "manufacturer": "Corbin Russwin",
        "fire_rating_minutes": 90,
        "material": "hollow_metal",
        "electrified": True,
        "voltage": 24,
        "finish": "626",
    }


def test_every_schema_field_is_a_model_column():
    columns = set(Product.__table__.columns.keys())
    assert set(ProductBase.model_fields) <= columns


def test_string_enum_columns_store_values_not_member_names():
    allowed = Product.__table__.c.category.type.enums
    assert allowed == [member.value for member in CategoryEnum]
