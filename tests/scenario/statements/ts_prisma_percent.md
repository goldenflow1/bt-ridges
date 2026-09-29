# Repair campaign conversion rate

The dashboard shows conversion rates computed in PostgreSQL through Prisma's
`$queryRaw`. Every non-whole percentage is truncated.

Restrict changes to `src/stats/conversion.ts`, specifically
`conversionByCampaign()`.

- `rate` is `conversions * 100 / visits` rounded to two decimals;
- campaigns with zero visits report `0`, not NULL.

Run `npx vitest run src/stats` and `npx tsc --noEmit -p .` before finishing.
