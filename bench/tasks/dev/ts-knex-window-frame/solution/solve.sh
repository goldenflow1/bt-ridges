#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('src/reports.ts')
old="import knex from 'knex';\n\nexport const db = knex({ client: 'pg', connection: process.env.AUDITFEED_TEST_DATABASE_URL ?? 'postgres://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_test?sslmode=disable' });\nexport interface LedgerRow { id: number; account: string; amount: string; total: string }\n\n/** Return lifetime running balances for visible movements, in chronological ID order. */\nexport async function runningBalances(tenant: string, start: number, end: number): Promise<LedgerRow[]> {\n  const result = await db.raw(`SELECT id, account, amount::text, SUM(amount) OVER (PARTITION BY account ORDER BY occurred_at)::text AS total FROM movements WHERE tenant = ? AND occurred_at >= ? AND occurred_at < ? ORDER BY occurred_at, id`, [tenant, start, end]);\n  return result.rows;\n}\n"
assert p.read_text()==old, 'source anchor changed'
p.write_text("import knex from 'knex';\n\nexport const db = knex({ client: 'pg', connection: process.env.AUDITFEED_TEST_DATABASE_URL ?? 'postgres://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_test?sslmode=disable' });\nexport interface LedgerRow { id: number; account: string; amount: string; total: string }\n\n/** Return lifetime running balances for visible movements, in chronological ID order. */\nexport async function runningBalances(tenant: string, start: number, end: number): Promise<LedgerRow[]> {\n  const result = await db.raw(`SELECT id, account, amount::text, total::text FROM (SELECT id, account, amount, occurred_at, SUM(amount) OVER (PARTITION BY account ORDER BY occurred_at, id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS total FROM movements WHERE tenant = ? AND occurred_at < ?) ledger WHERE occurred_at >= ? ORDER BY occurred_at, id`, [tenant, end, start]);\n  return result.rows;\n}\n")
PYFIX
