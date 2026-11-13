"""Explicit SQL interface, configured by PG* environment and a credential reference."""

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

FIELDS = "id, customer, sku, quantity, unit_price_cents, total_cents, placed_at"


def connect():
    # Read the referenced secret only at connection time. Never expose a DSN in errors.
    return psycopg.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "order_app"),
        dbname=os.environ.get("PGDATABASE", "orders"),
        password=Path(os.environ["ORDER_PASSWORD_FILE"]).read_text().strip(),
        connect_timeout=3,
        options="-c statement_timeout=5000 -c timezone=UTC",
        row_factory=dict_row,
    )


def canonical(row):
    return {
        **row,
        "id": str(row["id"]),
        "placed_at": row["placed_at"].isoformat(),
    }


def ready():
    with connect() as conn:
        return conn.execute("SELECT version FROM schema_version").fetchall() == [{"version": 1}]


def get_order(order_id):
    with connect() as conn:
        row = conn.execute(f"SELECT {FIELDS} FROM orders WHERE id = %s", (order_id,)).fetchone()
        return canonical(row) if row else None


def create_order(order):
    with connect() as conn:
        row = conn.execute(
            f"INSERT INTO orders ({FIELDS}) VALUES (%s,%s,%s,%s,%s,%s,%s) "
            f"ON CONFLICT (id) DO NOTHING RETURNING {FIELDS}",
            tuple(order[key.strip()] for key in FIELDS.split(",")),
        ).fetchone()
        if row:
            return canonical(row), True
        existing = conn.execute(
            f"SELECT {FIELDS} FROM orders WHERE id = %s", (order["id"],)
        ).fetchone()
        if canonical(existing) != order:
            raise ValueError("stable order ID conflicts with different fields")
        return canonical(existing), False
