# Stage Pass

Box-office staff browse published events and every ticket type available on each event. A ticket-kind search changes which events qualify, not which ticket types are displayed. Pagination and totals should count events.

`src/api/catalog.ts` delegates to a catalog service and event repository. Entity mappings and connection configuration are separate modules. An adjacent repository function supports the editor's enabled-kind selector. PostgreSQL schema is provisioned by the database image; TypeORM synchronization is disabled.
