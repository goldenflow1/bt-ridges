# PLAN — Wave 2 development tasks

Status: in progress · 2026-09-30

Build the remaining twelve development tasks in [the catalog](../specs/bench-catalog.md). The seven held-out tasks remain Wave 3, with separate authorship where possible. No agent inference or submission is part of this work.

## Scope and ownership

| Batch | Tasks |
|---|---|
| Python/PostgreSQL | `py-sqla-latest-per-customer`, `py-psycopg-left-join-filter`, `py-django-not-in-null`, `py-sqla-partial-index` |
| Python/ClickHouse | `ch-py-uniq-exact`, `ch-py-join-defaults`, `ch-py-tz-buckets`, `ch-py-prewhere-orderkey` |
| Go/TypeScript | `go-dbsql-null-scan`, `go-gorm-preload`, `ts-knex-window-frame`, `ts-ch-client-limit-by` |

Task construction can proceed in parallel. Docker validation is serialized on this host, with no live inference running alongside it. Existing reconnaissance records and source changes are preserved.

## Acceptance

Each task must satisfy B-VALID-01 through B-VALID-06, B-VALID-08/09 and B-VALID-11. Include a clear statement, working application and visible regression checks, a reference solution, at least two plausible decoys with declared assertion evidence, and scope isolation probes. Application copies must match. Install runtime dependencies at image build time; checks must run on the validator's internal network.

Hidden cases must distinguish the stated semantics across multiple sizes and edge cases, rather than merely reproduce a sample. Optimization tasks measure query count, execution plans, or rows read on declared data volumes. Record limits and blind spots without claiming that more tasks guarantee competition difficulty.

## Execution

1. Build and statically inspect the twelve tasks against their catalog rows.
2. Run `bench/validate_task.py` for each task; retain full logs, fix failures, and rerun changed tasks.
3. Review reference/decoy independence, statement-to-test coverage, application-copy identity, and cleanup.
4. Update the catalog and link validation evidence. Run applicable repository gates.

## Results

Pending. Built tasks are not considered validated until their complete validity run passes. No baseline or solve-rate claim follows from task construction.
