# Repair the tenant balance summary

Meterline stores prepaid wallet accounts in the ClickHouse table
`account_balances`. Every change to an account appends a new row with a
higher `revision`; the row with the highest `revision` is the account's
current state. The table is a `ReplacingMergeTree(revision)` ordered by
`(tenant_id, account_id)`, so superseded revisions disappear only when
background merges happen to run.

Support reports that the tenant balance summary sometimes shows more
accounts and more money than the tenant holds, and that the numbers drop
again later without any new writes. On the development database, where all
parts have been merged, it prints:

```text
$ python -m meterline.cli summary northwind
currency accounts        balance
EUR             2         532.50
GBP             1         300.00
USD             1         150.75
```

Work in `/app`. Limit production changes to `meterline/balances.py`,
specifically the `tenant_balance_summary()` function. Keep its signature and
docstring and the rest of the file unchanged, including imports; use only
names the file already imports.

`tenant_balance_summary(client, tenant_id)` must return one
`CurrencyTotal` per currency, ordered by currency code, where:

- every account of the tenant contributes only its current row, whether or
  not older revisions have been merged away yet;
- `revision` alone decides which row is current: rows can arrive out of
  revision order and `updated_at` is not a reliable ordering;
- an account is counted only when its current row is `active`, under its
  current row's currency and balance;
- `accounts` is the number of such accounts and `balance_minor` the sum of
  their current balances;
- a tenant with no active accounts returns an empty list;
- the result is the same before and after the table is merged.

Keep the work in ClickHouse: a single query through `client.query()`. Do
not aggregate or deduplicate rows in Python, do not run `OPTIMIZE`,
`SYSTEM`, DDL, or insert statements from the function, and do not change the
table definition, the other functions, the client, the CLI, tests, or project
configuration.

Run these checks before finishing:

```bash
pytest tests/test_balances.py
ruff check --no-cache meterline/balances.py
```
