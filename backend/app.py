"""FastAPI application object."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.database import Database
from backend.domain import SalesAnalytics, Store

app = FastAPI(title="Stokivo", description="Inventory and sales management API", version="1.0.0")

database = Database()
store = Store(database)


@app.on_event("startup")
def prepare_database() -> None:
    database.initialize()


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sku: str = Field(min_length=1, max_length=48)
    category: str = Field(default="General", max_length=80)
    price: float = Field(ge=0, le=99999999)
    cost_price: float = Field(ge=0, le=99999999)
    stock: int = Field(ge=0, le=10000000)
    min_stock: int = Field(default=5, ge=0, le=10000000)


class SaleInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000000)


def translate_database_error(error: Exception) -> HTTPException:
    message = str(error)
    if "unique" in message.lower() or "duplicate" in message.lower():
        return HTTPException(status_code=409, detail="That SKU is already in use.")
    if "foreign key" in message.lower() or "sales_product_fk" in message:
        return HTTPException(status_code=409, detail="Products with sales records cannot be removed.")
    return HTTPException(status_code=400, detail="The database could not save this change.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "postgres" if database.is_postgres else "sqlite"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    week_start, _, _ = SalesAnalytics.parse_period("week")
    products = store.inventory.list_products()
    return {
        "today": store.analytics.summary(today, today + timedelta(days=1)),
        "month": store.analytics.summary(month, now + timedelta(seconds=1)),
        "all_time": store.analytics.summary(),
        "week_series": store.analytics.grouped_sales("day", week_start, now + timedelta(days=1)),
        "low_stock": store.inventory.low_stock(),
        "recent_sales": store.analytics.recent_sales(7),
        "product_count": len(products),
        "units_in_stock": sum(product["stock"] for product in products),
    }


@app.get("/api/products")
def list_products(search: str = Query(default="", max_length=100)) -> list[dict]:
    return store.inventory.list_products(search.strip())


@app.post("/api/products", status_code=201)
def add_product(payload: ProductInput) -> dict:
    try:
        return store.inventory.add_product(payload.model_dump())
    except Exception as error:
        raise translate_database_error(error) from error


@app.put("/api/products/{product_id}")
def update_product(product_id: int, payload: ProductInput) -> dict:
    try:
        product = store.inventory.update_product(product_id, payload.model_dump())
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        return product
    except HTTPException:
        raise
    except Exception as error:
        raise translate_database_error(error) from error


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int) -> dict[str, bool]:
    try:
        deleted = store.inventory.delete_product(product_id)
    except Exception as error:
        raise translate_database_error(error) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found.")
    return {"deleted": True}


@app.post("/api/sales", status_code=201)
def record_sale(payload: SaleInput) -> dict:
    try:
        return store.record_sale(payload.product_id, payload.quantity)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise translate_database_error(error) from error


@app.get("/api/sales")
def list_sales(limit: int = Query(default=50, ge=1, le=250)) -> list[dict]:
    return store.analytics.recent_sales(limit)


@app.get("/api/reports")
def sales_report(period: str = Query(default="month", pattern="^(today|week|month|year)$")) -> dict:
    start, end, grouping = SalesAnalytics.parse_period(period)
    return {
        "period": period,
        "summary": store.analytics.summary(start, end),
        "series": store.analytics.grouped_sales(grouping, start, end),
        "top_products": store.analytics.top_products(start, end),
    }


# Keep this mount last so API routes take precedence. Vercel promotes public
# assets to its CDN; the mount also makes the frontend available under uvicorn.
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "public", html=True),
    name="frontend",
)
