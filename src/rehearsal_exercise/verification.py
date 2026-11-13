"""Independent SQL/schema assertions, run against an explicitly selected instance."""

from rehearsal_exercise.evidence import ExerciseError

RECORDS_SQL = """
SELECT coalesce(json_agg(row ORDER BY id), '[]') FROM (
  SELECT id::text, customer, sku, quantity, unit_price_cents, total_cents,
    rtrim(rtrim(to_char(placed_at AT TIME ZONE 'UTC',
      'YYYY-MM-DD"T"HH24:MI:SS.US'), '0'), '.') || '+00:00' AS placed_at
  FROM orders
) row;
"""

SCHEMA_SQL = """
SELECT json_build_object(
  'tables', (SELECT json_agg(tablename ORDER BY tablename)
    FROM pg_tables WHERE schemaname='public'),
  'version', (SELECT json_agg(version ORDER BY version) FROM schema_version),
  'columns', (SELECT json_object_agg(attname,
    json_build_array(format_type(atttypid,atttypmod),attnotnull))
    FROM pg_attribute WHERE attrelid='orders'::regclass AND attnum>0 AND NOT attisdropped),
  'constraints', (SELECT json_object_agg(conname,contype) FROM pg_constraint
    WHERE conrelid IN ('orders'::regclass,'schema_version'::regclass)),
  'indexes', (SELECT json_agg(indexname ORDER BY indexname) FROM pg_indexes
    WHERE schemaname='public'),
  'index_definitions', (SELECT json_object_agg(indexname,indexdef) FROM pg_indexes
    WHERE schemaname='public'),
  'enforcement', (SELECT json_object_agg(conname,json_build_array(convalidated,conenforced))
    FROM pg_constraint WHERE conrelid IN ('orders'::regclass,'schema_version'::regclass)),
  'definitions', (SELECT json_object_agg(conname,pg_get_constraintdef(oid)) FROM pg_constraint
    WHERE conrelid IN ('orders'::regclass,'schema_version'::regclass))
);
"""

EXPECTED_COLUMNS = {
    "id": ["uuid", True],
    "customer": ["text", True],
    "sku": ["text", True],
    "quantity": ["integer", True],
    "unit_price_cents": ["integer", True],
    "total_cents": ["integer", True],
    "placed_at": ["timestamp with time zone", True],
}

EXPECTED_DEFINITIONS = {
    "customer_format": "CHECK ((customer ~ '^[A-Z0-9-]{1,40}$'::text))",
    "sku_format": "CHECK ((sku ~ '^[A-Z0-9-]{1,40}$'::text))",
    "quantity_range": "CHECK (((quantity >= 1) AND (quantity <= 10000)))",
    "price_range": "CHECK (((unit_price_cents >= 1) AND (unit_price_cents <= 10000)))",
    "total_matches": "CHECK ((total_cents = (quantity * unit_price_cents)))",
    "orders_pkey": "PRIMARY KEY (id)",
    "schema_version_pkey": "PRIMARY KEY (version)",
    "schema_version_version_check": "CHECK ((version = 1))",
    **{f"orders_{column}_not_null": f"NOT NULL {column}" for column in EXPECTED_COLUMNS},
    "schema_version_version_not_null": "NOT NULL version",
}
EXPECTED_INDEXES = {
    "orders_customer_idx": "CREATE INDEX orders_customer_idx "
    "ON public.orders USING btree (customer)",
    "orders_pkey": "CREATE UNIQUE INDEX orders_pkey ON public.orders USING btree (id)",
    "schema_version_pkey": "CREATE UNIQUE INDEX schema_version_pkey "
    "ON public.schema_version USING btree (version)",
}
EXPECTED_CONSTRAINTS = {
    "orders_pkey": "p",
    "customer_format": "c",
    "sku_format": "c",
    "quantity_range": "c",
    "price_range": "c",
    "total_matches": "c",
    "schema_version_pkey": "p",
    "schema_version_version_check": "c",
    # PostgreSQL 18 records NOT NULL constraints explicitly in pg_constraint.
    "orders_id_not_null": "n",
    "orders_customer_not_null": "n",
    "orders_sku_not_null": "n",
    "orders_quantity_not_null": "n",
    "orders_unit_price_cents_not_null": "n",
    "orders_total_cents_not_null": "n",
    "orders_placed_at_not_null": "n",
    "schema_version_version_not_null": "n",
}


def check_schema(actual):
    valid = (
        actual.get("tables") == ["orders", "schema_version"]
        and actual.get("version") == [1]
        and actual.get("columns") == EXPECTED_COLUMNS
        and actual.get("constraints") == EXPECTED_CONSTRAINTS
        and actual.get("definitions") == EXPECTED_DEFINITIONS
        and actual.get("enforcement") == {key: [True, True] for key in EXPECTED_CONSTRAINTS}
        and actual.get("index_definitions") == EXPECTED_INDEXES
        and actual.get("indexes") == ["orders_customer_idx", "orders_pkey", "schema_version_pkey"]
    )
    if not valid:
        raise ExerciseError("schema objects or constraints differ from verifier contract")


def constraint_probes():
    """Each expected rejection executes in a rollback-only transaction on synthetic rows."""
    cases = [
        ("customer_format", "customer", "'bad customer'", "check_violation"),
        ("sku_format", "sku", "'bad sku'", "check_violation"),
        ("quantity_range", "quantity", "0", "check_violation"),
        ("quantity_range", "quantity", "10001", "check_violation"),
        ("price_range", "unit_price_cents", "0", "check_violation"),
        ("price_range", "unit_price_cents", "10001", "check_violation"),
        ("total_matches", "total_cents", "2", "check_violation"),
        ("orders_pkey", "id", "'00000000-0000-0000-0000-000000000001'", "unique_violation"),
    ]
    for constraint, field, value, condition in cases:
        values = {
            "id": "'ffffffff-ffff-4fff-8fff-ffffffffffff'",
            "customer": "'PROBE'",
            "sku": "'PROBE'",
            "quantity": "1",
            "unit_price_cents": "1",
            "total_cents": "1",
            "placed_at": "'2026-01-01T12:00:00Z'",
        }
        values[field] = value
        if field in ("quantity", "unit_price_cents"):
            values["total_cents"] = value
        yield f"""
BEGIN;
DO $$ DECLARE observed text;
BEGIN
  BEGIN
    INSERT INTO orders ({",".join(values)}) VALUES ({",".join(values.values())});
  EXCEPTION WHEN {condition} THEN
    GET STACKED DIAGNOSTICS observed = CONSTRAINT_NAME;
    IF observed = '{constraint}' THEN RETURN; END IF;
    RAISE EXCEPTION 'unexpected constraint';
  END;
  RAISE EXCEPTION 'constraint did not reject invalid synthetic order';
END $$;
ROLLBACK;
"""
