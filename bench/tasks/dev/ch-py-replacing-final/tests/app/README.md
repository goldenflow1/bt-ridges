# meterline

Prepaid usage wallets. Every change to a wallet account (top-up, usage
charge, freeze, close) appends a new *revision* of the account row to the
`account_balances` table in ClickHouse; the row with the highest `revision`
is the account's current state. The table is a `ReplacingMergeTree(revision)`,
so older revisions are eventually dropped by background merges.

- `meterline/chclient.py` — minimal HTTP client for ClickHouse (stdlib only).
- `meterline/schema.py` — table DDL.
- `meterline/balances.py` — ledger writes and tenant reports.
- `meterline/cli.py` — `python -m meterline.cli summary <tenant>`.

Environment:

- `METERLINE_CLICKHOUSE_URL`, `METERLINE_CLICKHOUSE_USER`, `METERLINE_CLICKHOUSE_PASSWORD`
- `METERLINE_DATABASE` (development data) and `METERLINE_TEST_DATABASE` (test scratch database)

Run the tests with `pytest tests/test_balances.py`.
