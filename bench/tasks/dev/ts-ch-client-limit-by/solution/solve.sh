#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('src/reports.ts')
old="import { createClient } from '@clickhouse/client';\n\nexport const db = createClient({ url: 'http://clickhouse:8123', username: 'meterline', password: 'meterline-app-4e2a9c17', database: 'meterline_test' });\nexport interface RankedItem { category: string; id: number; score: number }\n\n/** Return up to n eligible items per category, with deterministic ties. */\nexport async function topItems(tenant: string, n: number): Promise<RankedItem[]> {\n  const result = await db.query({ query: `SELECT category, id, score FROM items WHERE tenant = {tenant:String} AND active = 1 ORDER BY category, score DESC, id ASC LIMIT 1`, query_params: { tenant, n }, format: 'JSONEachRow' });\n  return result.json<RankedItem>();\n}\n"
assert p.read_text()==old, 'source anchor changed'
p.write_text("import { createClient } from '@clickhouse/client';\n\nexport const db = createClient({ url: 'http://clickhouse:8123', username: 'meterline', password: 'meterline-app-4e2a9c17', database: 'meterline_test' });\nexport interface RankedItem { category: string; id: number; score: number }\n\n/** Return up to n eligible items per category, with deterministic ties. */\nexport async function topItems(tenant: string, n: number): Promise<RankedItem[]> {\n  const result = await db.query({ query: `SELECT category, id, score FROM items WHERE tenant = {tenant:String} AND active = 1 ORDER BY category, score DESC, id ASC LIMIT {n:UInt32} BY category`, query_params: { tenant, n }, format: 'JSONEachRow' });\n  return result.json<RankedItem>();\n}\n")
PYFIX
