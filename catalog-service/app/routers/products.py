from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import DbSession, is_unique_violation
from app.domain import CategoryEnum
from app.models import SKU_UNIQUE_INDEX, Product
from app.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.schemas import ProductCreate, ProductPage, ProductRead, ProductUpdate

router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100  # caps the work one request can ask the database to do


def get_product_or_404(db: Session, product_id: int) -> Product:
    """Load a product by ID, or raise 404."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found.")
    return product


def commit_or_409(db: Session, sku: str) -> None:
    """Commit, turning a duplicate-SKU violation into 409. Other integrity errors are bugs."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if is_unique_violation(exc, SKU_UNIQUE_INDEX):
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"A product with SKU {sku!r} already exists."
            ) from exc
        raise


@router.get("", response_model=ProductPage)
def list_products(
    db: DbSession,
    category: CategoryEnum | None = None,
    fire_rated: Annotated[
        bool | None, Query(description="true: rated products only; false: unrated only")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: Annotated[
        str | None, Query(description="`next_cursor` from the previous page; omit for the first")
    ] = None,
) -> ProductPage:
    """List products, optionally filtered, in pages ordered by id (keyset pagination)."""
    stmt = select(Product).order_by(Product.id).limit(limit + 1)  # one extra row: is there more?
    if cursor is not None:
        try:
            after_id = decode_cursor(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid cursor.") from exc
        stmt = stmt.where(Product.id > after_id)
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if fire_rated is True:
        stmt = stmt.where(Product.fire_rating_minutes > 0)
    elif fire_rated is False:
        stmt = stmt.where(Product.fire_rating_minutes == 0)

    rows = list(db.scalars(stmt))
    page, has_more = rows[:limit], len(rows) > limit
    return ProductPage(
        items=[ProductRead.model_validate(product) for product in page],
        next_cursor=encode_cursor(page[-1].id) if has_more else None,
    )


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(body: ProductCreate, db: DbSession) -> Product:
    """Create a product. Returns 409 if the SKU already exists."""
    product = Product(**body.model_dump())
    db.add(product)
    commit_or_409(db, body.sku)
    return product


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: DbSession) -> Product:
    """Get a product by ID. Returns 404 if the product does not exist."""
    return get_product_or_404(db, product_id)


@router.put("/{product_id}", response_model=ProductRead)
def replace_product(product_id: int, body: ProductCreate, db: DbSession) -> Product:
    """Replace every field of a product. Returns 404 if missing, 409 if the SKU is taken."""
    product = get_product_or_404(db, product_id)
    for field, value in body.model_dump().items():
        setattr(product, field, value)
    commit_or_409(db, body.sku)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, body: ProductUpdate, db: DbSession) -> Product:
    """Update only the fields sent. Returns 404 if missing, 409 if the SKU is taken.

    Cross-field rules (electrified products need a voltage, others can't have one) are checked
    on the stored product with the changes merged in, since the body alone is incomplete.
    """
    product = get_product_or_404(db, product_id)
    changes = body.model_dump(exclude_unset=True)

    stored = ProductRead.model_validate(product).model_dump(exclude={"id"})
    try:
        ProductCreate.model_validate({**stored, **changes})
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.errors(include_url=False, include_context=False, include_input=False),
        ) from exc

    for field, value in changes.items():
        setattr(product, field, value)
    commit_or_409(db, changes.get("sku", product.sku))
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DbSession) -> None:
    """Delete a product. Returns 404 if the product does not exist."""
    db.delete(get_product_or_404(db, product_id))
    db.commit()
