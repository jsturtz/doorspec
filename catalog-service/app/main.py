import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_db
from app.routers import products

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
def read_root():
    """Placeholder root route."""
    return {"Hello": "World"}


@app.get("/health/", tags=["health"])
async def read_health():
    """Report that the service is up."""
    return {"status": "healthy"}


@app.get("/health/ready", tags=["health"])
def read_ready(db: Annotated[Session, Depends(get_db)]):
    """Report whether the service can reach its database."""
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        logger.exception("Readiness check failed: database unreachable")
        raise HTTPException(status_code=503, detail="Service is not ready") from exc
    return {"status": "ready"}


app.include_router(products.router, prefix="/products", tags=["products"])
