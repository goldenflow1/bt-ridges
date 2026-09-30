CREATE TABLE pay_entries (id bigint PRIMARY KEY, organization_id bigint NOT NULL, posted_at timestamptz NOT NULL, gross_cents bigint NOT NULL, memo text NOT NULL);
CREATE INDEX pay_entries_period ON pay_entries(organization_id,posted_at,id);
