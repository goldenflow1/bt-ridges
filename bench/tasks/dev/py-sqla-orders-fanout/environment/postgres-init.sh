#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE tidewater LOGIN PASSWORD 'tidewater-app-5c1e93d7'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template0 FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL

createdb --username "$POSTGRES_USER" --owner tidewater tidewater_dev
createdb --username "$POSTGRES_USER" --owner tidewater tidewater_test

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
REVOKE ALL ON DATABASE tidewater_dev FROM PUBLIC;
REVOKE ALL ON DATABASE tidewater_test FROM PUBLIC;
GRANT CONNECT ON DATABASE tidewater_dev TO tidewater;
GRANT CONNECT ON DATABASE tidewater_test TO tidewater;
SQL

psql --username "$POSTGRES_USER" --dbname tidewater_dev --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE tidewater;

CREATE TABLE customers (
  id serial PRIMARY KEY,
  name varchar(120) NOT NULL,
  email varchar(254) NOT NULL UNIQUE,
  region varchar(16) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_customers_region ON customers (region);

CREATE TABLE orders (
  id serial PRIMARY KEY,
  customer_id integer NOT NULL REFERENCES customers (id),
  status varchar(16) NOT NULL,
  placed_at timestamptz NOT NULL,
  CONSTRAINT orders_status_check CHECK (status IN ('placed', 'paid', 'cancelled'))
);
CREATE INDEX ix_orders_customer_id ON orders (customer_id);
CREATE INDEX ix_orders_placed_at ON orders (placed_at);

CREATE TABLE order_items (
  id serial PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders (id),
  sku varchar(32) NOT NULL,
  quantity integer NOT NULL,
  unit_price_cents integer NOT NULL,
  CONSTRAINT order_items_quantity_check CHECK (quantity > 0),
  CONSTRAINT order_items_price_check CHECK (unit_price_cents >= 0)
);
CREATE INDEX ix_order_items_order_id ON order_items (order_id);

CREATE TABLE shipments (
  id serial PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders (id),
  carrier varchar(32) NOT NULL,
  tracking_code varchar(64) NOT NULL UNIQUE,
  shipped_at timestamptz NOT NULL
);
CREATE INDEX ix_shipments_order_id ON shipments (order_id);

INSERT INTO customers (id, name, email, region, created_at) VALUES
  (1, 'Ana Duarte',    'ana.duarte@example.test',    'north', '2025-11-02 09:14+00'),
  (2, 'Ben Okafor',    'ben.okafor@example.test',    'south', '2025-11-19 17:40+00'),
  (3, 'Cleo Marsh',    'cleo.marsh@example.test',    'north', '2026-01-07 08:03+00'),
  (4, 'Dev Patel',     'dev.patel@example.test',     'west',  '2026-01-22 12:31+00'),
  (5, 'Eli Brandt',    'eli.brandt@example.test',    'south', '2026-02-11 19:55+00'),
  (6, 'Fay Lund',      'fay.lund@example.test',      'west',  '2026-02-28 07:12+00');
SELECT setval('customers_id_seq', 6);

INSERT INTO orders (id, customer_id, status, placed_at) VALUES
  (101, 1, 'paid',      '2026-03-02 10:12+00'),
  (102, 1, 'paid',      '2026-03-09 16:45+00'),
  (103, 2, 'paid',      '2026-03-03 11:20+00'),
  (104, 2, 'cancelled', '2026-03-04 08:05+00'),
  (105, 4, 'paid',      '2026-03-05 13:30+00'),
  (106, 5, 'paid',      '2026-03-06 09:00+00'),
  (107, 5, 'placed',    '2026-03-12 21:18+00'),
  (108, 6, 'paid',      '2026-03-08 15:02+00');
SELECT setval('orders_id_seq', 108);

INSERT INTO order_items (order_id, sku, quantity, unit_price_cents) VALUES
  (101, 'TENT-2P',   1, 24900),
  (101, 'STAKE-8',   2,  1250),
  (102, 'LAMP-HD',   1,  3999),
  (103, 'PACK-40L',  1, 13900),
  (103, 'RAIN-CVR',  1,  2400),
  (104, 'PACK-60L',  1, 17900),
  (105, 'MUG-TI',    3,  2450),
  (105, 'STOVE-M',   1,  8900),
  (106, 'SOCK-W',    4,  1800),
  (107, 'MAP-NW',    1,  1500),
  (108, 'BAG-DOWN',  1, 32900),
  (108, 'PAD-FOAM',  1,  4500);

INSERT INTO shipments (order_id, carrier, tracking_code, shipped_at) VALUES
  (101, 'harbourpost', 'HP00001001', '2026-03-03 08:00+00'),
  (102, 'harbourpost', 'HP00001002', '2026-03-10 08:00+00'),
  (103, 'ridgeline',   'RL00004410', '2026-03-04 12:15+00'),
  (105, 'harbourpost', 'HP00001007', '2026-03-06 08:00+00'),
  (106, 'ridgeline',   'RL00004452', '2026-03-07 10:40+00'),
  (108, 'harbourpost', 'HP00001013', '2026-03-09 08:00+00');
SQL

touch "$PGDATA/TASK_READY"
