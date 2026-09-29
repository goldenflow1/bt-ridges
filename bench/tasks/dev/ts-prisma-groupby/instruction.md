# Repair course completion rates

The courseboard admin dashboard ranks courses by completion rate using
`courseCompletionRates()`. Course owners report that rates are wrong for
most cohorts: a course where two of three learners finished shows `66.0`
instead of `66.7`, and courses with almost identical rates are sometimes
ranked in the wrong order.

On the seeded development database the report looks correct:

```text
$ npm run -s report
code     title                        enrolled  done   rate
ART200   Colour Theory                       5     5  100.0
GEO101   Physical Geography                  4     3   75.0
MAT210   Linear Algebra                     10     7   70.0
BIO110   Cell Biology                        2     1   50.0
CHE150   Organic Chemistry I                 4     1   25.0
PHY100   Mechanics                           0     0    0.0
```

Work in `/app`. Limit production changes to `src/reports.ts`, specifically
the `courseCompletionRates()` function. Keep its signature and doc comment
and the rest of the file unchanged, including imports and the row interfaces.

`courseCompletionRates()` must return one row per non-archived course where:

- `enrolled` and `completed` count the course's non-withdrawn enrollments;
- `completionRate` is `completed * 100 / enrolled` computed exactly and
  rounded to one decimal place, with halves rounded away from zero;
- a course without enrollments has `completionRate` `0`;
- `completionRate` is a JavaScript `number`;
- rows are ordered by the rounded rate, highest first, then by course id.

Keep the arithmetic, rounding, and ordering in PostgreSQL within the single
existing `$queryRaw` query. Do not compute, round, sort, or filter rates in
TypeScript, and do not use `$queryRawUnsafe`. Do not change the Prisma
schema, the SQL schema, seed data, other functions, the CLI, tests, or
package files. Do not add database writes, process, filesystem, or network
side effects.

Run these checks before finishing:

```bash
npm test
npx tsc --noEmit
```
