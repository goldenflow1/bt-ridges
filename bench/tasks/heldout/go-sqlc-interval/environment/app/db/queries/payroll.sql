-- name: ListPayEntries :many
SELECT id, organization_id, posted_at, gross_cents, memo
FROM pay_entries
WHERE organization_id = sqlc.arg(organization_id)::bigint
  AND posted_at BETWEEN sqlc.arg(period_start)::timestamptz AND sqlc.arg(period_end)::timestamptz - INTERVAL '1 second'
ORDER BY posted_at, id;
