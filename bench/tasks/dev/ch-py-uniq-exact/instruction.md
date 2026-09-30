# Return exact unique visitor counts

Work in `/app`. Change only the body of `visitor_count()` in `observatory/report.py`. Preserve its signature, docstring, imports and all other source bytes.

The distinct visitor count drifts for larger tenants. Return one row `{"visitors": integer}` with the **exact** count of different non-NULL visitor IDs for the requested tenant and UTC interval `[start, end)`. Visitor zero is valid; repeated visits count once. Missing tenants, empty intervals and only NULL visitors produce zero. Identifiers and timestamps are user inputs: retain bound parameters. The table is `visits(tenant, visitor Nullable(UInt64), happened)`; volume can exceed hundreds of thousands of unique IDs.

Keep the edited function within 6,000 UTF-8 bytes and 500 Python AST nodes.

Keep query work in ClickHouse through `client.query()`. The report must not write data or change the schema. Do not add imports, cache answers, or edit the client, tests, configuration or any other file. The development database is seeded; the separate test database may be used for local investigation.

Run these checks before finishing:

```bash
pytest tests/test_report.py
ruff check --no-cache observatory/report.py
```
