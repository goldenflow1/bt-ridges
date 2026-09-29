TypeScript data-access notes:
- Prisma: include/select for relations, groupBy/_count for aggregates; $queryRaw uses tagged templates (parameters are bound, not interpolated) and returns bigint for COUNT in PostgreSQL. Avoid schema changes unless required; the client may not regenerate offline.
- TypeORM: leftJoinAndSelect multiplies rows; getCount/getManyAndCount on joined queries can count joined rows; getRawMany returns raw column aliases.
- Knex/Kysely/Drizzle: build window functions and subqueries with raw fragments carefully; keep parameters bound.
- @clickhouse/client: query({ query, format: 'JSONEachRow', query_params }) with {name:Type} placeholders.
- Verify with `npx tsc --noEmit -p .` (using the local node_modules; do not download packages) and the project's test script.
