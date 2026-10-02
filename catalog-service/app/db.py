from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config

settings = config.get_settings()

# Create the engine responsible for managing the connection pool and database connections.
# The echo flag enables SQL logging for debugging.
engine = create_engine(settings.database_url, echo=True, future=True)

# Do we want expire_on_commit=False?
# So this is a factory that returns sessions
SessionLocal = sessionmaker(autoflush=False, bind=engine)


# Define a base class for declarative models. All ORM models will inherit from this base.
class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


def get_db() -> Iterator[Session]:
    """Provide a database session to the caller, ensuring it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
