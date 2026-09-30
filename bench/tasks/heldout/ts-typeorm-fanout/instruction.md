# Box-office event pages are short and totals are inflated

Box-office staff browse published events with their ticket types. Events with many ticket types cause short pages and inflated totals; a ticket-kind search can also hide ticket types that should still be displayed. Repair the repository query in `/app`.

Change only the body of `listEvents` in `src/repositories/events.ts`. Preserve its JSDoc, signature, imports, neighboring functions, public types and every other file. Use the existing TypeORM repository/QueryBuilder APIs and bound parameters. Do not change schemas, data, tests, dependencies, configuration, connection settings or loggers; do not create query runners directly or add file/process/network/dynamic-code side effects or persistent caches.

Required semantics:
- Include only published events belonging to the requested tenant. With no kind filter, include events with zero ticket types.
- With a kind filter, an event qualifies when at least one of its ticket types has that exact kind and is enabled. Qualification must not trim the loaded collection: return every ticket type of each selected event, including other kinds and disabled types.
- `offset` counts events skipped and `limit` counts events returned, never joined rows. Inputs are valid nonnegative offsets and limits from 1 through 100. Return all qualifying events up to that page size.
- `total` is the number of qualifying events before pagination, independent of page size or offset. An out-of-range page has an empty item list while retaining the total; an empty selection has total zero.
- Sort events by `startsAt` ascending, then unique event ID ascending, including exact millisecond timestamp ties. No particular ticket-type ordering is required, but child IDs and all their fields must be complete and unchanged.
- Preserve event fields and their TypeScript types, including `Date` timestamps, and ticket-type kind/capacity/enabled values. Zero capacity is valid. Quoted kind strings must remain bound values.
- A page including its total and children uses at most three read-only queries regardless of child counts or page size. The next call reflects new data without persistent caching. Keep the editor's enabled-kind selector unchanged.

Run these checks before finishing:

```bash
npm test
npm run typecheck
```
