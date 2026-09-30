# PLAN — Wave 3 held-out tasks

Status: ready to build · 2026-09-29

Build the seven **held-out** tasks in [the catalog](../specs/bench-catalog.md) §3 under `bench/tasks/heldout/<id>/`. They exist for one purpose: gate G7 (`docs/process/engineering-loop.md`), the 3-trial held-out run that decides whether an agent build may be uploaded. No agent inference and no submission is part of this work.

## 1. Independence rules (why these tasks are different)

Held-out tasks measure whether the agent *generalises*. They are only worth that if they were not shaped by the agent.

- **Do not read** `src/`, `src/quarry/prompts/`, `src/quarry/packs/`, `dist/`, `docs/experiments/`, `bench/runs/` or any agent run log while building. The specs you need are this plan, the catalog (§1, §3, §8) and the Wave 1–2 task directories as format examples.
- **Never run the agent on these tasks** (no `ridges miner run-local`, no `run_bench --set heldout`) while building or validating. The only agent runs on them are the G7 runs on the bench host.
- **Never tune against them.** A held-out task that is looked at to fix the agent becomes a dev task (engineering-loop §5a) and must be replaced.
- **Application domains:** do not use `orders`/`customers` (the agent's prompt examples use them) and do not reuse a Wave 1–2 application (tidewater, the telemetry store, etc.). Pick fresh domains: e.g. library loans, clinic appointments, freight shipments, energy meters, ticketing, payroll, a CI build farm.
- Build in a **fresh session/author** from Wave 1–2 where possible (catalog §4.3).

## 2. Constraints every task must meet

**Format** — identical to the samples and Waves 1–2 (catalog §1):
```
bench/tasks/heldout/<id>/
  task.toml                 schema 1.3; [agent] timeout_sec 1800; [verifier] timeout_sec 900, environment_mode "separate"
  instruction.md            samples' style: goal, exact scope, bullets of required semantics, forbidden changes,
                            then "Run these checks before finishing:" + a ```bash block (validate_task.py parses it)
  environment/              Dockerfile (app at /app, .git removed, uid 1000 `agent` user, only the allowed file(s)
                            writable), docker-compose.yaml (DB service with healthcheck), DB init + seed,
                            baseline-requirements.txt (copy from any Wave 2 task)
  solution/solve.sh         reference fix, anchor-checked (fails loudly if the anchor text is missing)
  tests/                    Dockerfile + docker-compose.yaml + app copy (byte-identical to environment/app),
                            test.sh, verify.py, hidden tests, create_source_manifest.py,
                            decoys/<name>.patch + decoys/<name>.json {"expect_failing": [...], "passes_visible": true}
```

**Validity** — `python3 bench/validate_task.py bench/tasks/heldout/<id>` must end `RESULT: PASS`, covering B-VALID-01…06, 08, 09 and 11 (catalog §8):
- unmodified repo → 0; `solve.sh` → 1; named checks pass on the unmodified repo;
- **≥ 2 plausible decoys**, each passing the visible checks and scoring 0 through the behavioural assertion it declares (not a collection/compile error);
- scope variants (extra file, other file, mode change) rejected only by scope/conservation checks;
- no network egress after the build; the task image starts the miner runtime (`python3` + baseline packages, as uid 1000).

**Checker (`verify.py`)** — binary reward; tree conservation over every path + mode; byte-exact bounds outside the allowed symbol when the statement names one (Go: `funcspan`, TS: `tsspan.cjs`, Python: AST span — reuse the Wave 1–2 helpers); the statement's named checks; hidden tests on **data the statement does not show** (other sizes, ties, NULLs, empty groups, boundaries, time zones).

**Statement discipline** — every rule a hidden test enforces must be stated or unambiguously implied by `instruction.md`. A hidden test may use unseen *data*, never an unstated *rule*. Run the statement-to-test matrix (Wave 2 reviews are the template) before calling a task done.

**Timing** — named checks well under 120 s cold on the bench host; checker total well under the 900 s limit; images build offline-reproducibly (pin versions, install everything at build time).

**Difficulty** — the Wave 1–2 dev set proved easier than the competition (5/5 at reconnaissance). Aim closer to the public samples:
- a realistic repository: several packages/modules, unrelated code paths near the defect, real tests the statement names, not a 1-file toy;
- the symptom stated in domain terms (what a user sees), with the exact scope still unambiguous;
- the obvious one-line fix should be one of the decoys where the trap allows it.

## 3. The seven tasks

Kinds: **R** repair · **A** authoring · **O** optimization. Scope: **N** named file + symbol · **U** unnamed (trace from symptom) · **M** migration-only. Suggested domains are only suggestions.

### 3.1 `py-sqla-distinct-on` — Python · SQLAlchemy 2.x · PG · R · N
*Suggested domain: freight shipments, "latest tracking scan per parcel".*
- **Defect:** a repository method returns one row per key with `DISTINCT ON (key)`, but its `ORDER BY` picks the wrong row: e.g. `ORDER BY key, id DESC` where ids are not chronological (backfilled scans), or the secondary order omits the tie-breaker.
- **Statement must say:** "latest" = greatest event timestamp; ties broken by the greatest id; keys with a single row included; returned fields and ordering of the result list.
- **Hidden tests:** backfilled rows (id order ≠ time order), exact timestamp ties, single-row keys, empty table, a large random set compared with a reference computed in Python.
- **Decoys:** order by timestamp without the tie-breaker (fails ties); `GROUP BY key` + `max(ts)` join-back (duplicates on ties); keep `id DESC` only (fails backfill).

### 3.2 `py-django-annotate-subquery` — Python · Django ORM · PG · A · N
*Suggested domain: clinic appointments, "doctors with their open-appointment count".*
- **Task:** implement a queryset/manager method that annotates each parent with the count of related rows matching a filter, via a correlated `Subquery` wrapped in `Coalesce(..., 0)` with an integer output field, alongside an existing second annotation.
- **Statement must say:** zero (not `None`) when nothing matches; value is an `int`; a bounded, N-independent number of queries; no raw SQL; result ordering; the existing annotation must keep its values.
- **Hidden tests:** parents with no children, children that fail the filter only, combined with the other annotation (a JOIN-based `Count` fans out and inflates it), query count constant for 1 vs 50 parents, type is `int`.
- **Decoys:** `Count("children", filter=Q(...))` combined with the existing join annotation (fan-out); `Subquery` without `Coalesce` (`None`); Python-side counting (query count grows).

### 3.3 `ch-py-argmax-state` — Python · ClickHouse SQL · CH · R · U
*Suggested domain: energy meters, "current connection state per meter".*
- **Defect (unnamed scope — the statement gives the symptom, not the file):** a report shows meters as online after they went offline. The query filters (`WHERE state = 'online'`) or groups (`GROUP BY meter_id, region`) *before* taking `argMax`, so it returns the last matching state instead of the current one.
- **Statement must say:** current state = state of the latest event per meter; ties on the event time broken by a `version` column; meters that moved region report their current region; which file(s) may change (state the *allowed area*, e.g. "the reporting package", precisely enough for the scope checker).
- **Hidden tests:** a meter whose latest event is filtered, same-timestamp events with different versions, a meter that changed region, a meter with one event, duplicate rows from an unmerged `ReplacingMergeTree` if used.
- **Decoys:** keep the `WHERE` before aggregation; `argMax(state, event_time)` without the version tie-breaker; `max(state)`.

### 3.4 `go-sqlc-interval` — Go · sqlc · PG · R · N
*Suggested domain: payroll, "entries for a pay period".*
- **Defect:** the query uses `BETWEEN $start AND $end` where `$end` is a date's `23:59:59`, losing rows with fractional seconds and mishandling time zones. Fix: half-open `>= start AND < next day`.
- **Scope:** `query.sql` **and** the generated `*.sql.go` must stay in sync (the checker compares the SQL constant in the generated file with `query.sql`, or regenerates with a pinned `sqlc` in the image), plus the caller that computes the bound if the statement allows it. State this explicitly.
- **Hidden tests:** a row at `23:59:59.5`, a row at next-midnight exactly (excluded), month and year ends, a non-UTC period time zone if the statement defines one.
- **Decoys:** `BETWEEN start AND next_midnight` (includes the next day's midnight row); edit only the generated Go (fails the sync check); `<= 23:59:59` left in place with `date_trunc` on the column (correct results but defeats the index if the statement requires index use — only if stated).

### 3.5 `ts-typeorm-fanout` — TypeScript · TypeORM QueryBuilder · PG · R · N
*Suggested domain: ticketing, "paginated events with their ticket types".*
- **Defect:** a paginated list uses `leftJoinAndSelect` with `.limit()/.offset()` (limits joined rows, not entities) and/or a total computed over joined rows, so pages are short and totals inflated.
- **Statement must say:** page size counts parent entities; total = number of parents matching the filter; children fully loaded; deterministic order with a unique tie-breaker.
- **Hidden tests:** parents with many children across a page boundary, parents with zero children, filter that matches through a child, total on several page sizes, stable order on ties.
- **Decoys:** `.limit()` → `.take()` but no unique order (unstable pages on ties); count via `getRawMany().length` / joined rows; `DISTINCT` on the joined select (drops children).

### 3.6 `pg-expr-index-lower` — Python · Django migration · PG · O · M
*Suggested domain: library members, "sign-in lookup by e-mail".*
- **Task (migration-only):** the lookup code (unchangeable) filters on `Lower("email")`; add a migration + model `Meta.indexes` entry for an expression index on `Lower("email")` so the lookup uses it at the declared data volume.
- **Statement must say:** only a new migration file and the model's `Meta.indexes` may change; `makemigrations --check` must be clean; the migration must be reversible; the data volume at which the plan is judged.
- **Hidden tests:** `EXPLAIN` of the real lookup on a seeded large table shows an index scan on the new index; results identical; migrate → reverse → migrate works; `makemigrations --check` clean.
- **Decoys:** a plain index on `email` (not used); `RunSQL` creating the index without model state (`makemigrations --check` fails — only if the statement names that check, otherwise it is a scope decoy); an index on `Upper("email")`.

### 3.7 `ch-go-skip-index` — Go · clickhouse-go · CH · O · M
*Suggested domain: CI build farm, "look up a build by its job id".*
- **Task (migration-only):** a table ordered by `(project_id, started_at)` is queried by a high-cardinality `job_id`, scanning everything. Add a migration with a data-skipping index (e.g. `bloom_filter`) on `job_id` **and** materialise it for existing parts.
- **Statement must say:** only a new migration file may change; results unchanged; `read_rows` for the lookup must fall below a stated bound at the declared volume; migrations are idempotent (`IF NOT EXISTS`) and have a down step, if that is the repo's convention.
- **Hidden tests:** `read_rows` (from `system.query_log` or the query's progress) under the bound for several ids including a missing one; identical results; migration re-run is a no-op.
- **Decoys:** `ADD INDEX` without `MATERIALIZE INDEX` (existing parts unindexed, `read_rows` unchanged); `minmax` index type on random ids; changing the sort key (not allowed by scope).

## 4. Execution (on the building device)

1. Build each task and statically inspect it against its §3 row and §2 constraints.
2. Validate serially: `python3 bench/validate_task.py bench/tasks/heldout/<id>`; keep full logs; fix and re-run changed tasks. No live inference on that host while validating.
3. Cross-review: statement-to-test matrix, reference/decoy independence, app-copy identity (`diff -r environment/app tests/app`), cleanup (no leftover containers/volumes).
4. Record evidence under `docs/reviews/wave3-evidence/` (same shape as Wave 2), update the catalog status line and §6, run `uv run python tools/gate.py`, push.

## 5. Acceptance

All seven tasks `RESULT: PASS`; every decoy scores 0 via its declared assertion; every scope variant is rejected only by scope/conservation checks; G0–G5 green. Only then does the bench host run G7 (`run_bench --set heldout --repeats 3 --purpose evaluation`) against the target declared in §6 **before** that run.

## 6. G7 target (declare before the first held-out run)

Pending — to be fixed by the maintainer before any held-out result exists. Proposed for the first (calibration) upload: 0 agent mechanical failures; mean $/task ≤ $0.03; `prescreen_lint` and originality clean; held-out solve rate ≥ 50% of 7 × 3 trials.

## 7. Results

Pending.
