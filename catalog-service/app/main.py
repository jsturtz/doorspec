from fastapi import FastAPI

from app.routers import products

app = FastAPI()


@app.get("/")
def read_root():
    """Placeholder root route."""
    return {"Hello": "World"}


@app.get("/health/", tags=["health"])
async def read_health():
    """Report that the service is up."""
    return {"status": "healthy"}


app.include_router(products.router, prefix="/products", tags=["products"])
