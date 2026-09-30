# PLAN — Wave 2 development tasks

Status: complete · 2026-09-30

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

Construction, cross-review and serial Docker calibration are complete: **12/12 tasks, 196/196 validity checks, 26 behavioral decoys and 36 scope variants passed**. Every reference scores 1; every empty patch and decoy scores 0. Every decoy passes its visible checks and fails a declared behavioral assertion. All scope probes preserve passing reference behavior and fail only scope/conservation checks. No baseline or solve-rate claim follows from task construction.

The [final audit](../reviews/wave2-evidence/final-results.json) selects the accepted run for each task, replays all empty/decoy assertion logs, checks matching application copies, and records current and validated source digests. Two Python instructions have separately documented wording-only clarifications of existing size limits. The [cleanup audit](../reviews/wave2-evidence/cleanup.json) found no containers, networks or volumes left by any recorded Wave 2 validation project. The development set now contains 17 tasks; seven held-out tasks remain Wave 3. No miner inference calls were made.

The first PostgreSQL run exposed a fixture bug: psycopg interpreted literal `%` operators in `exec_driver_sql` as placeholders. The fixtures now use PostgreSQL `mod()`, and the original failed run is retained. That run also exposed a B-VALID-08 parser bug: an assertion mentioned in a sibling test's summary could hide a runtime error. The parser now bounds traceback sections and checks the terminal exception; two regression tests cover summary contamination and exception messages/chaining.

Calibration also caught two invalid ClickHouse decoys: the approximate-count variant returned NULL on an empty input, and the TypeScript global-limit variant accidentally damaged `ORDER BY`. Both were repaired without weakening their tests. Unused TypeScript template settings and checker constants were removed; affected tasks passed complete reruns. Failed attempts remain available in the [evidence index](../reviews/wave2-evidence/README.md).

[G0–G5 pass after the parser fix](../reviews/wave2-evidence/automatic-gates-final.txt). Per-task records retain source digests, full reference/decoy/scope logs, and initial failed attempts. See the three batch reviews linked from the catalog for statement-to-test coverage and limitations.
