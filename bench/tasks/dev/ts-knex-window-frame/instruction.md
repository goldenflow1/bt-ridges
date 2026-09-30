# Implement chronological running balances

Work in `/app`. Complete `runningBalances` in `src/reports.ts`, changing only its body. Preserve imports, signature, documentation and all other files.

For the requested tenant return movements in `[start,end)`, globally ordered by `(occurred_at,id)` ascending. For each row, `total` is the lifetime sum for its account through that exact row, including movements before `start`. Equal timestamps must advance the balance one row at a time in ID order; other accounts and tenants must not contribute. IDs are unique but need not follow timestamp order. Preserve exact signed integer values, including integers beyond JavaScript's safe number range, as decimal strings. Empty intervals return no rows.

Use one parameterized PostgreSQL query through Knex. Window calculation, filtering and ordering belong in SQL; no JavaScript row transformations, schema changes, caches, filesystem/network/process side effects or dependency changes.

Run these checks before finishing:
```bash
node --import tsx --test --test-reporter=tap test/reports.test.ts
npx --offline tsc --noEmit
```
