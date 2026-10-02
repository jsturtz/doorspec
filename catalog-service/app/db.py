from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from psycopg.errors import UniqueViolation
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config

settings = config.get_settings()

# Create the engine responsible for managing the connection pool and database connections.
# The echo flag enables SQL logging for debugging.
engine = create_engine(settings.database_url, echo=True)

# Session factory. expire_on_commit=False keeps attribute values after commit, so a route can
# return the object it just saved without an extra SELECT to reload it.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Define a base class for declarative models. All ORM models will inherit from this base.
class Base(DeclarativeBase):
    """Base class for all ORM models."""

    # Deterministic constraint names, so Alembic migrations can refer to them later.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def get_db() -> Iterator[Session]:
    """Provide a database session to the caller, ensuring it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Annotated type for dependency injection in FastAPI routes.
DbSession = Annotated[Session, Depends(get_db)]


# utility functions
def is_unique_violation(exc: IntegrityError, constraint_name: str) -> bool:
    """True if exc is a Postgres unique violation on the named constraint or index."""
    return (
        isinstance(exc.orig, UniqueViolation) and exc.orig.diag.constraint_name == constraint_name
    )
