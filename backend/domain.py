"""Store domain objects and reporting logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from backend.database import Database, row_dict


@dataclass(slots=True)
class Product:
    id: int | None
    name: str
    sku: str
    category: str
    price: float
    cost_price: float
    stock: int
    min_stock: int = 5
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> "Product":
        data = row_dict(row)
        for key in ("price", "cost_price"):
            data[key] = float(data[key])
        return cls(**{key: data.get(key) for key in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "category": self.category,
            "price": float(self.price),
            "cost_price": float(self.cost_price),
            "stock": self.stock,
            "min_stock": self.min_stock,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "low_stock": self.low_stock,
        }

    @property
    def low_stock(self) -> bool:
        return self.stock <= self.min_stock


@dataclass(slots=True)
class Sale:
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    unit_cost: float
    total: float
    profit: float
    sold_at: str

    @classmethod
    def from_row(cls, row: Any) -> "Sale":
        data = row_dict(row)
        for key in ("unit_price", "unit_cost", "total", "profit"):
            data[key] = float(data[key])
        return cls(**{key: data[key] for key in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "product_id": self.product_id,
            "product_name": self.product_name, "quantity": self.quantity,
            "unit_price": self.unit_price, "unit_cost": self.unit_cost,
            "total": self.total, "profit": self.profit, "sold_at": self.sold_at,
        }


class Inventory:
    """Product catalogue and stock management."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_products(self, search: str = "") -> list[dict[str, Any]]:
        ordering = "name" if self.database.is_postgres else "name COLLATE NOCASE"
        with self.database.connect() as connection:
            rows = self.database.execute(
                connection,
                f"""SELECT * FROM products
                   WHERE is_active = TRUE
                     AND (? = '' OR name LIKE ? OR sku LIKE ? OR category LIKE ?)
                   ORDER BY {ordering}""",
                (search, f"%{search}%", f"%{search}%", f"%{search}%"),
            ).fetchall()
        return [Product.from_row(row).to_dict() for row in rows]

    def get_product(self, product_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = self.database.execute(
                connection, "SELECT * FROM products WHERE id = ? AND is_active = TRUE", (product_id,)
            ).fetchone()
        return Product.from_row(row).to_dict() if row else None

    def add_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = self._clean_payload(payload)
        with self.database.connect() as connection:
            if self.database.is_postgres:
                row = self.database.execute(
                    connection,
                    """INSERT INTO products (name, sku, category, price, cost_price, stock, min_stock)
                       VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *""",
                    tuple(fields.values()),
                ).fetchone()
            else:
                cursor = self.database.execute(
                    connection,
                    """INSERT INTO products (name, sku, category, price, cost_price, stock, min_stock)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    tuple(fields.values()),
                )
                row = self.database.execute(
                    connection, "SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        return Product.from_row(row).to_dict()

    def update_product(self, product_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields = self._clean_payload(payload)
        with self.database.connect() as connection:
            cursor = self.database.execute(
                connection,
                """UPDATE products
                   SET name = ?, sku = ?, category = ?, price = ?, cost_price = ?,
                       stock = ?, min_stock = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND is_active = TRUE""",
                (*fields.values(), product_id),
            )
            if cursor.rowcount == 0:
                return None
            row = self.database.execute(
                connection, "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        return Product.from_row(row).to_dict()

    def delete_product(self, product_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = self.database.execute(
                connection,
                "UPDATE products SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND is_active = TRUE",
                (product_id,),
            )
        return cursor.rowcount > 0

    def low_stock(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = self.database.execute(
                connection,
                "SELECT * FROM products WHERE is_active = TRUE AND stock <= min_stock ORDER BY stock ASC, name",
            ).fetchall()
        return [Product.from_row(row).to_dict() for row in rows]

    @staticmethod
    def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": payload["name"].strip(),
            "sku": payload["sku"].strip().upper(),
            "category": payload.get("category", "").strip() or "General",
            "price": round(float(payload["price"]), 2),
            "cost_price": round(float(payload["cost_price"]), 2),
            "stock": int(payload["stock"]),
            "min_stock": int(payload.get("min_stock", 5)),
        }


class SalesAnalytics:
    """Revenue, profit, and time-bucketed sales reports."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def summary(self, start: datetime | None = None, end: datetime | None = None) -> dict[str, Any]:
        where, params = self._range_clause(start, end)
        with self.database.connect() as connection:
            row = self.database.execute(
                connection,
                f"""SELECT COALESCE(SUM(total), 0) AS revenue,
                           COALESCE(SUM(profit), 0) AS profit,
                           COALESCE(SUM(quantity), 0) AS units,
                           COUNT(*) AS orders
                    FROM sales {where}""",
                params,
            ).fetchone()
        data = row_dict(row)
        return {key: float(value) if key in ("revenue", "profit") else int(value)
                for key, value in data.items()}

    def grouped_sales(self, period: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        date_group = "DATE(sold_at)" if period == "day" else (
            "DATE_TRUNC('month', sold_at)" if self.database.is_postgres
            else "STRFTIME('%Y-%m', sold_at)"
        )
        where, params = self._range_clause(start, end)
        with self.database.connect() as connection:
            rows = self.database.execute(
                connection,
                f"""SELECT {date_group} AS label, SUM(total) AS revenue,
                           SUM(profit) AS profit, SUM(quantity) AS units, COUNT(*) AS orders
                    FROM sales {where}
                    GROUP BY label ORDER BY label""",
                params,
            ).fetchall()
        result = []
        for row in rows:
            item = row_dict(row)
            label = item["label"]
            if hasattr(label, "isoformat"):
                label = label.isoformat()
            result.append({
                "label": str(label)[:10],
                "revenue": float(item["revenue"]),
                "profit": float(item["profit"]),
                "units": int(item["units"]),
                "orders": int(item["orders"]),
            })
        return result

    def top_products(self, start: datetime, end: datetime, limit: int = 5) -> list[dict[str, Any]]:
        where, params = self._range_clause(start, end)
        with self.database.connect() as connection:
            rows = self.database.execute(
                connection,
                f"""SELECT product_name AS name, SUM(quantity) AS units,
                           SUM(total) AS revenue, SUM(profit) AS profit
                    FROM sales {where}
                    GROUP BY product_name ORDER BY revenue DESC LIMIT ?""",
                (*params, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = row_dict(row)
            result.append({
                "name": item["name"], "units": int(item["units"]),
                "revenue": float(item["revenue"]), "profit": float(item["profit"]),
            })
        return result

    def recent_sales(self, limit: int = 8) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = self.database.execute(
                connection, "SELECT * FROM sales ORDER BY sold_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Sale.from_row(row).to_dict() for row in rows]

    def _range_clause(self, start: datetime | None, end: datetime | None) -> tuple[str, tuple[Any, ...]]:
        clauses: list[str] = []
        params: list[Any] = []
        for operator, value in ((">=", start), ("<", end)):
            if value:
                clauses.append(f"sold_at {operator} ?")
                if self.database.is_postgres:
                    params.append(value)
                else:
                    normalized = value.astimezone(timezone.utc) if value.tzinfo else value
                    params.append(normalized.strftime("%Y-%m-%d %H:%M:%S"))
        return ("WHERE " + " AND ".join(clauses) if clauses else "", tuple(params))

    @staticmethod
    def parse_period(period: str) -> tuple[datetime, datetime, str]:
        today = datetime.now(timezone.utc).date()
        if period == "today":
            start_date, end_date, grouping = today, today + timedelta(days=1), "day"
        elif period == "week":
            start_date, end_date, grouping = today - timedelta(days=6), today + timedelta(days=1), "day"
        elif period == "month":
            start_date = today.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date, grouping = next_month, "day"
        elif period == "year":
            start_date, end_date, grouping = today.replace(month=1, day=1), today + timedelta(days=1), "month"
        else:
            start_date, end_date, grouping = today - timedelta(days=29), today + timedelta(days=1), "day"
        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(end_date, time.min, tzinfo=timezone.utc)
        return start, end, grouping


class Store:
    """Composition root for inventory, sales, and analytics."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.inventory = Inventory(database)
        self.analytics = SalesAnalytics(database)

    def record_sale(self, product_id: int, quantity: int) -> dict[str, Any]:
        if quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        with self.database.connect() as connection:
            if not self.database.is_postgres:
                connection.execute("BEGIN IMMEDIATE")
            lock = " FOR UPDATE" if self.database.is_postgres else ""
            row = self.database.execute(
                connection, "SELECT * FROM products WHERE id = ? AND is_active = TRUE" + lock, (product_id,)
            ).fetchone()
            if not row:
                raise LookupError("That product could not be found.")
            product = Product.from_row(row)
            if product.stock < quantity:
                raise ValueError(f"Only {product.stock} units are in stock.")
            total = round(product.price * quantity, 2)
            profit = round((product.price - product.cost_price) * quantity, 2)
            self.database.execute(
                connection,
                "UPDATE products SET stock = stock - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (quantity, product_id),
            )
            if self.database.is_postgres:
                sale_row = self.database.execute(
                    connection,
                    """INSERT INTO sales
                       (product_id, product_name, quantity, unit_price, unit_cost, total, profit)
                       VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *""",
                    (product_id, product.name, quantity, product.price, product.cost_price, total, profit),
                ).fetchone()
            else:
                cursor = self.database.execute(
                    connection,
                    """INSERT INTO sales
                       (product_id, product_name, quantity, unit_price, unit_cost, total, profit)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (product_id, product.name, quantity, product.price, product.cost_price, total, profit),
                )
                sale_row = self.database.execute(
                    connection, "SELECT * FROM sales WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        return Sale.from_row(sale_row).to_dict()
