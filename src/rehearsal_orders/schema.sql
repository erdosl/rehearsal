-- Explicit v1 initialization, run once on a fresh SOURCE only. Restore uses the dump.
BEGIN;
CREATE TABLE schema_version (version integer PRIMARY KEY CHECK (version = 1));
INSERT INTO schema_version VALUES (1);
CREATE TABLE orders (
    id uuid PRIMARY KEY,
    customer text NOT NULL CONSTRAINT customer_format CHECK (customer ~ '^[A-Z0-9-]{1,40}$'),
    sku text NOT NULL CONSTRAINT sku_format CHECK (sku ~ '^[A-Z0-9-]{1,40}$'),
    quantity integer NOT NULL CONSTRAINT quantity_range CHECK (quantity BETWEEN 1 AND 10000),
    unit_price_cents integer NOT NULL
        CONSTRAINT price_range CHECK (unit_price_cents BETWEEN 1 AND 10000),
    total_cents integer NOT NULL
        CONSTRAINT total_matches CHECK (total_cents = quantity * unit_price_cents),
    placed_at timestamp with time zone NOT NULL
);
CREATE INDEX orders_customer_idx ON orders (customer);
COMMIT;
