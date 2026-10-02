"""Shared fixtures: a real Postgres test database, built by Alembic, rolled back after every test.

The test database is `<dev database>_test` on the same server (override with TEST_DATABASE_URL).
DATABASE_URL is pointed at it *before* any app module is imported, so nothing in the test run can
reach the development database, including Alembic's env.py, which reads the URL from settings.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, make_url, text

from app.config import Settings, get_settings

_dev_url = make_url(Settings().database_url)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _dev_url.set(
    database=f"{_dev_url.database}_test"
).render_as_string(hide_password=False)
assert make_url(TEST_DATABASE_URL).database.endswith("_test"), "refusing to test a non-test DB"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
get_settings.cache_clear()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal, get_db  # noqa: E402
from app.main import app  # noqa: E402

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _create_test_database() -> None:
    """Create the test database if it doesn't exist (connects to the dev database to do so)."""
    test_db = make_url(TEST_DATABASE_URL).database
    admin = create_engine(_dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_db})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Test database with a fresh schema from the real migrations (base, then head)."""
    _create_test_database()
    alembic_cfg = Config(str(ALEMBIC_INI))
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    test_engine = create_engine(TEST_DATABASE_URL)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose commits are savepoints in an outer transaction rolled back after the test.

    Route code calls commit() as usual; nothing persists past the test.
    """
    with engine.connect() as connection:
        outer = connection.begin()
        session = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient whose routes all use the per-test session."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()
