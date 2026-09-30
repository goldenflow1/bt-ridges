# Implement per-category top items

Work in `/app`. Complete only the body of `topItems` in `src/reports.ts`; keep its signature, documentation, imports and every other file unchanged.

For the specified tenant select only active items, then return up to `n` items from each category. Rank within each category by score descending and ID ascending; ties at the cutoff never increase the quota. Return rows globally in category ascending, score descending, ID ascending order. Categories with no active items produce no rows. `n` is an integer from 0 through 100; zero returns no rows. Negative and zero scores are valid. The same input must yield the same selected rows and order across repeated calls.

Use one parameterized query through `@clickhouse/client`, with selection and ordering in ClickHouse SQL. Do not add JavaScript row transforms, change schemas/dependencies/tests, cache answers, or add filesystem/process/network side effects.

Run these checks before finishing:
```bash
node --import tsx --test --test-reporter=tap test/reports.test.ts
npx --offline tsc --noEmit
```
