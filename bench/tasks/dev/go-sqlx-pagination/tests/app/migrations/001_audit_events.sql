CREATE TABLE IF NOT EXISTS audit_events (
    id          bigserial PRIMARY KEY,
    tenant_id   text        NOT NULL,
    actor       text        NOT NULL,
    action      text        NOT NULL,
    target      text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_tenant_created_idx
    ON audit_events (tenant_id, created_at, id);
