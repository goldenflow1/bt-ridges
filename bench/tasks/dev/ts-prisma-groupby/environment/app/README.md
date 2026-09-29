# courseboard

Course catalogue and learner-progress reporting (TypeScript, Prisma, PostgreSQL).

- `prisma/schema.prisma` — data model; `migrations/001_init.sql` — schema DDL.
- `src/reports.ts` — reporting queries (`$queryRaw`) used by the admin dashboard.
- `npm run report` — prints the course completion report.

Environment: `COURSEBOARD_DATABASE_URL` (development data) and
`COURSEBOARD_TEST_DATABASE_URL` (scratch database used by `npm test`).
