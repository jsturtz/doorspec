import logging
import tomllib
from pathlib import Path

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import DbSession
from app.routers import products

logger = logging.getLogger(__name__)

# pyproject.toml is the single source of truth for the version; CHANGELOG.md records what changed.
_PROJECT = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())

app = FastAPI(
    title="DoorSpec catalog-service",
    version=_PROJECT["project"]["version"],
    description=_PROJECT["project"]["description"],
)


@app.get("/")
def read_root():
    """Placeholder root route."""
    return {"Hello": "World"}


@app.get("/health/", tags=["health"])
async def read_health():
    """Report that the service is up."""
    return {"status": "healthy"}


@app.get("/health/ready", tags=["health"])
def read_ready(db: DbSession):
    """Report whether the service can reach its database."""
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        logger.exception("Readiness check failed: database unreachable")
        raise HTTPException(status_code=503, detail="Service is not ready") from exc
    return {"status": "ready"}


app.include_router(products.router, prefix="/products", tags=["products"])
