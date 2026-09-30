# Prune reads for the tenant settlement report

Work in `/app`. Change only the body of `settled_total()` in `observatory/report.py`. Preserve its signature, docstring, imports and all other source bytes.

The settlement total is correct on ordinary inputs but scans almost all tenants. Preserve the exact signed sum of `amount` for the requested integer tenant, status `settled` and UTC timestamp interval `[start, end)`. Return one row `{"total": integer}`, zero if no matching rows. The MergeTree sorting key is `(tenant_id, happened, event_id)` with 1024-row granules. Make the selective report read **at least 10 times fewer rows** than the existing query on roughly one million rows across at least 100 tenants. The HTTP client exposes ClickHouse response statistics as `last_statistics`; read-row measurements exclude query caching. Use one query; do not use result caching, materialized tables, indexes, settings that change correctness, or client-side filtering. Keep all inputs parameterized.

Keep the edited function within 6,000 UTF-8 bytes and 500 Python AST nodes.

Keep query work in ClickHouse through `client.query()`. The report must not write data or change the schema. Do not add imports, cache answers, or edit the client, tests, configuration or any other file. The development database is seeded; the separate test database may be used for local investigation.

Run these checks before finishing:

```bash
pytest tests/test_report.py
ruff check --no-cache observatory/report.py
```
