# Wave 2: Python/PostgreSQL task construction

All four dev tasks are built and completed Docker validation: **66/66 checks**, with four reference solutions scoring 1, four empty patches scoring 0, nine decoys scoring 0 by their declared behavioural assertions, and twelve scope variants rejected only by conservation checks. No inference runs or held-out tasks were used. Two instruction-only size-limit clarifications made after validation change those task digests; the recorded results refer to their original validation inputs, as detailed below.

| Task | Scope | Distinguishing hidden tests | Decoys (each must pass visible checks) |
|---|---|---|---|
| `py-sqla-latest-per-customer` | Named function body | Equal timestamps choose greatest ID; IDs out of chronological order; NULL timestamps; half-open window applied before ranking; one query across 71 customer partitions; exact timestamp projection with microseconds and offset input | smallest ID on ties; ID treated as chronology; day-truncated timestamp |
| `py-psycopg-left-join-filter` | Trace endpoint through two permitted files | Empty departments; only cancelled/out-of-window bookings; equal amounts; zero amounts; tenant isolation; inclusive lower/exclusive upper boundary; one parameterized query | WHERE predicate with OR NULL; COUNT(*) counts the null-extended row |
| `py-django-not-in-null` | Named function body | NULL customer block; indefinite blocks; exact expiry boundary; inactive blocks; other-tenant blocks; duplicate blocks; one query across 501 customers | finite-expiry blocks only; cross-tenant Exists |
| `py-sqla-partial-index` | Existing migration file only | Actual Alembic upgrade/downgrade/re-upgrade; unchanged query results and ordering; original indexes/data/columns conserved; partial predicate excludes ineligible rows; natural EXPLAIN uses index and ≤80 buffers / ≥10× reduction on 100,000 rows | wrong NULL predicate; tenant-only index needs too much heap/sort work |

Each task contains an independent environment/verifier pair, PostgreSQL 16.6 service, visible seeded database, copied app trees, reference solution with exact source anchors, and two or three decoys declaring assertion test IDs. Docker builds install the Ridges baseline dependencies; the validator runs its normal runtime prerequisite probe. Named body boundaries preserve surrounding bytes, signature and docstring. Tree manifests compare paths, modes and protected file contents; scope variants must still run all behaviour tests.

Static validation: Python AST parsing, all nine decoy patches apply, app tree pairs are identical, and Ruff passes. The migration test uses buffer work rather than elapsed time and never changes planner switches.

Limitations: these are synthetic applications and do not establish competition solve rates. Dependencies from the baseline requirements are currently unpinned upstream, matching the existing task convention; exact built image identity belongs in B2 run identity. Source duplication remains explicit and must be checked when editing. The bounded constructs check is a contract guard, not an adversarial Python sandbox.

## Docker evidence

| Task | Docker validity | Evidence |
|---|---|---|
| `py-sqla-latest-per-customer` | **PASS, 18/18**, warm rerun 242.8 s; instruction clarified afterward | [Complete validator log](wave2-evidence/py-sqla-latest-per-customer.validation.log), [artifacts](wave2-evidence/py-sqla-latest-per-customer.artifacts/) |
| `py-psycopg-left-join-filter` | **PASS, 16/16**; source unchanged | [Complete validator log](wave2-evidence/py-psycopg-left-join-filter.validation.log), [artifacts](wave2-evidence/py-psycopg-left-join-filter.artifacts/) |
| `py-django-not-in-null` | **PASS, 16/16**; instruction clarified afterward | [Complete validator log](wave2-evidence/py-django-not-in-null.validation.log), [artifacts](wave2-evidence/py-django-not-in-null.artifacts/) |
| `py-sqla-partial-index` | **PASS, 16/16**; source unchanged | [Complete validator log](wave2-evidence/py-sqla-partial-index.validation.log), [artifacts](wave2-evidence/py-sqla-partial-index.artifacts/) |

The first failed latest-event attempt is preserved in [its initial log](wave2-evidence/py-sqla-latest-per-customer.initial.validation.log). Saved empty-patch and all nine decoy logs were replayed successfully with the corrected assertion/error parser. All four task digests remained unchanged during their successful full runs.

## Independent cross-review

The ClickHouse task author reviewed these four tasks. Follow-ups incorporated before Docker validation: the latest-event task now checks the returned timestamp itself (microseconds and equivalent offset timestamps) and has a third wrong-projection decoy; all existing public function signatures are checked for unnamed as well as named scope; migration plan/buffer checks run for three tenants. The reference solutions also pass an offline execution of their actual conservation, bounds and construct guards.

The editable Alembic migration implementation lives at `migrations/ready_jobs.py`; an immutable revision entrypoint under `migrations/versions/` imports it. This keeps a harmless additional Python file in the allowed file's directory from being misread as a broken Alembic revision, so the new-file scope variant can fail conservation alone while retaining valid migration behaviour.

Initial Docker validation of `py-sqla-latest-per-customer` correctly rejected a hidden-fixture setup error: psycopg interpreted literal `%` modulo operators in `exec_driver_sql` as parameter placeholders. The fixture now uses PostgreSQL `mod(x, n)`, and the same issue was corrected proactively in the partial-index seed. First-attempt evidence is retained; only a complete passing rerun admits either task.

The migration's tenant-only-index decoy reached the actual work assertion while using the named index: 1,004 shared buffer blocks versus 4,167 before migration for tenant 7. Its rejection therefore demonstrates measured work discrimination, beyond checking an index name or query output.

## Post-validation instruction clarification

The shared checker runs `assert len(after) < 15000` inside its configured named-function loop, where `after` is the **entire file returned by `Path.read_text()`**. This means fewer than 15,000 Unicode code points, including surrounding imports, docstrings and whitespace, after universal-newline normalization; it is neither a function-only limit nor a byte limit. The loop applies to `py-sqla-latest-per-customer` and `py-django-not-in-null`. The other two tasks have empty `bounded` mappings, so this limit does not apply to them.

Only those two instructions now state this existing restriction explicitly. [The clarification evidence](wave2-evidence/python-pg-instruction-clarifications.json) records every task's prior validation digest and current digest, instruction hashes, the exact unchanged regression block and its hash, and an entry-by-entry check proving all non-instruction inputs (including file modes) stayed unchanged. As an independent check, copying each current task and removing only the recorded added paragraph reproduces its full original validation digest exactly. The original validation records are preserved. No Docker rerun or inference trial was performed for this wording change; calibration outcomes are unchanged, and no agent solve results exist for these tasks yet.

| Task | Validated digest suffix | Current digest suffix |
|---|---|---|
| `py-sqla-latest-per-customer` | `29ec14de1c940927f991fd17e6fd48b1ffa535d6608d9b9e9e8dd948ebe195cf` | `bb76c3b05d29854a00efb4ec8b9b09bd7eb1dcbee9a34dfae06fe278353682dc` |
| `py-psycopg-left-join-filter` | `86116c31a4af16c6f78b893560755d8aef2a68446c36dfda013e072bb9ce0a2d` | `86116c31a4af16c6f78b893560755d8aef2a68446c36dfda013e072bb9ce0a2d` |
| `py-django-not-in-null` | `608f360ff037939a5be225a967b600bc0e2df4094c28183c871bd0477168a773` | `333a0eb20a45fb2d00ad9ea8367ea48a21fa33f8b13c22cb2b90af20243afe44` |
| `py-sqla-partial-index` | `a9aa1f67a4398181328b2e6802d06f5b7f2c9702f0801dde272674937d1c315e` | `a9aa1f67a4398181328b2e6802d06f5b7f2c9702f0801dde272674937d1c315e` |
