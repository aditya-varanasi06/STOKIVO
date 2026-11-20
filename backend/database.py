"""Small SQLite/Postgres database adapter for local and Vercel deployments."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Database:
    """Open a short-lived connection per request for serverless compatibility."""

    def __init__(self) -> None:
        self.url = os.getenv("DATABASE_URL", "").strip()
        self.is_postgres = self.url.startswith(("postgres://", "postgresql://"))
        if not self.url and os.getenv("VERCEL"):
            raise RuntimeError(
                "DATABASE_URL is required on Vercel. Add a Postgres database "
                "from the Vercel Marketplace and redeploy."
            )
        local_path = os.getenv("SQLITE_PATH", str(Path(__file__).resolve().parent.parent / "stokivo.db"))
        self.sqlite_path = local_path

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("Install psycopg[binary] to use Postgres.") from exc
            connection = psycopg.connect(self.url, row_factory=dict_row)
            try:
                with connection:
                    yield connection
            finally:
                connection.close()
            return

        connection = sqlite3.connect(self.sqlite_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, connection: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self.is_postgres:
            return connection.execute(sql.replace("?", "%s"), params)
        return connection.execute(sql, params)

    def initialize(self) -> None:
        if self.is_postgres:
            schema = (
                """CREATE TABLE IF NOT EXISTS products (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    sku TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL DEFAULT 'General',
                    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
                    cost_price NUMERIC(12, 2) NOT NULL CHECK (cost_price >= 0),
                    stock INTEGER NOT NULL CHECK (stock >= 0),
                    min_stock INTEGER NOT NULL DEFAULT 5 CHECK (min_stock >= 0),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS sales (
                    id BIGSERIAL PRIMARY KEY,
                    product_id BIGINT NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_price NUMERIC(12, 2) NOT NULL,
                    unit_cost NUMERIC(12, 2) NOT NULL,
                    total NUMERIC(12, 2) NOT NULL,
                    profit NUMERIC(12, 2) NOT NULL,
                    sold_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT sales_product_fk FOREIGN KEY (product_id)
                        REFERENCES products(id) ON DELETE RESTRICT
                )""",
                "CREATE INDEX IF NOT EXISTS sales_sold_at_idx ON sales(sold_at)",
                "CREATE INDEX IF NOT EXISTS sales_product_idx ON sales(product_id)",
            )
        else:
            schema = (
                """CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sku TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL DEFAULT 'General',
                    price REAL NOT NULL CHECK (price >= 0),
                    cost_price REAL NOT NULL CHECK (cost_price >= 0),
                    stock INTEGER NOT NULL CHECK (stock >= 0),
                    min_stock INTEGER NOT NULL DEFAULT 5 CHECK (min_stock >= 0),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_price REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    total REAL NOT NULL,
                    profit REAL NOT NULL,
                    sold_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
                )""",
                "CREATE INDEX IF NOT EXISTS sales_sold_at_idx ON sales(sold_at)",
                "CREATE INDEX IF NOT EXISTS sales_product_idx ON sales(product_id)",
            )
        with self.connect() as connection:
            for statement in schema:
                self.execute(connection, statement)


def row_dict(row: Any) -> dict[str, Any]:
    """Convert driver rows into JSON-friendly dictionaries."""
    result = dict(row)
    for key, value in result.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif value is not None and value.__class__.__name__ == "Decimal":
            result[key] = float(value)
    return result
