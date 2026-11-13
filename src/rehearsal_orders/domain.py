"""Order validation and integer-money calculation; no database or Docker dependency."""

import re
from datetime import UTC, datetime
from uuid import UUID


def order_input(value):
    fields = {"id", "customer", "sku", "quantity", "unit_price_cents", "placed_at"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("exact order fields required")
    if not isinstance(value["id"], str) or not isinstance(value["placed_at"], str):
        raise ValueError("ID and placed_at must be strings")
    result = dict(value)
    result["id"] = str(UUID(value["id"]))
    for key in ("customer", "sku"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[A-Z0-9-]{1,40}", value[key]):
            raise ValueError("invalid synthetic customer or sku")
    for key in ("quantity", "unit_price_cents"):
        if type(value[key]) is not int or not 1 <= value[key] <= 10000:
            raise ValueError("quantity and unit price must be integers in 1..10000")
    placed = datetime.fromisoformat(value["placed_at"])
    if placed.tzinfo is None:
        raise ValueError("placed_at requires a timezone")
    result["placed_at"] = placed.astimezone(UTC).isoformat()
    result["total_cents"] = value["quantity"] * value["unit_price_cents"]
    return result
