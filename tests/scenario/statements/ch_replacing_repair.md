# Repair current balances

The balances endpoint reads account balances from ClickHouse. Rows are stored in a
`ReplacingMergeTree` keyed by account and versioned by `updated_at`. Until parts
merge, the endpoint double counts accounts that were updated recently.

Work in `/app`. Limit production changes to `app/reports/balances.py`,
specifically `current_balances()`. Keep its signature and the rest of the file
unchanged, including imports.

- every account appears once with its latest balance;
- ties on `updated_at` resolve to the highest `version`;
- deleted accounts (`is_deleted = 1`) are excluded.

Do not change table definitions, migrations, or tests.

```bash
pytest tests/test_balances.py -q
```
