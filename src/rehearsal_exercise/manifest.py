"""Independent intended-input fixture and comparison, without application imports."""

import hashlib
import json
from uuid import UUID


def digest(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def intended_order(number):
    quantity = number % 4 + 1
    price = 125 + number * 7
    return {
        "id": str(UUID(int=number)),
        "customer": f"SYNTH-{number % 7:02d}",
        "sku": f"ITEM-{number % 5:02d}",
        "quantity": quantity,
        "unit_price_cents": price,
        "total_cents": quantity * price,
        "placed_at": "2026-01-01T12:00:00+00:00",
    }


def manifest():
    records = [intended_order(i) for i in range(1, 101)]
    return {
        "fixture_version": 1,
        "schema_version": 1,
        "records": records,
        "record_sha256": {r["id"]: digest(r) for r in records},
        "total_cents": sum(r["total_cents"] for r in records),
    }


def compare(expected, actual):
    def same(left, right):
        return type(left) is type(right) and left == right

    expected_by_id = {r["id"]: r for r in expected}
    actual_by_id = {r["id"]: r for r in actual}
    missing = sorted(expected_by_id.keys() - actual_by_id.keys())
    extra = sorted(actual_by_id.keys() - expected_by_id.keys())
    changed = {
        key: sorted(
            field
            for field in expected_by_id[key].keys() | actual_by_id[key].keys()
            if field not in expected_by_id[key]
            or field not in actual_by_id[key]
            or not same(expected_by_id[key][field], actual_by_id[key][field])
        )
        for key in expected_by_id.keys() & actual_by_id.keys()
        if digest(expected_by_id[key]) != digest(actual_by_id[key])
    }
    duplicates = len(actual) != len(actual_by_id)
    return {
        "passed": not (missing or extra or changed or duplicates),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "duplicate_ids": duplicates,
        "expected_count": len(expected),
        "actual_count": len(actual),
    }
