# Implement running balances

`runningBalances()` in `src/ledger/balances.ts` is a stub that returns an empty
array. Implement it with Knex against PostgreSQL.

- each row carries the running balance up to and including itself;
- rows with the same `booked_at` are ordered by `id`;
- accounts are independent.

Change only `src/ledger/balances.ts`. Run `npm test -- ledger` before finishing.
