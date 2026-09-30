# Wave 3 construction review

Date: 2026-09-30. Construction review and task calibration only; no agent inference, tuning, baseline promotion or upload.

The seven applications use fresh domains and real database drivers/ORMs. Each has an API or service path, repositories, schema/model definitions, neighboring behavior and visible tests. They are synthetic applications, not extracted production repositories. Their relative difficulty and ability to predict competition performance remain unmeasured.

## Independence

Existing design inputs were limited to the Wave 3 plan, catalog and Wave 1/2 task folders. Agent source, prompts, packs, bundles, experiment logs and agent-run logs were not read during construction. Calibration uses only reference patches, empty patches, decoys and scope probes.

This was **not fresh-session authorship**. The coordinating thread already contained Wave 2 and experiment context. The [evidence provenance](wave3-evidence/README.md) preserves that limitation. This review is a construction self-review, not an independent author's review. Any subsequent agent tuning informed by one of these tasks requires moving that task to dev and replacing it.

## Statement-to-test matrix

All paths below are relative to `bench/tasks/heldout/<task>/tests/`. Hidden fixtures vary the data; the contracts are stated in each task's `instruction.md`.

| Task / fresh domain | Stated contract | Behavioral coverage |
|---|---|---|
| `py-sqla-distinct-on` / freight tracking | Current scan is greatest event time, then greatest ID; carrier isolation, one complete row per parcel, ascending parcel IDs | `hidden.py`: `test_backfilled_scans_do_not_replace_current_state`, `test_timestamp_ties_choose_one_complete_greatest_id_row` cover backfills, single scans, missing scans, other carriers, 48 timestamp ties and complete winning payloads |
| Same | Full precision and types, one database query returning only winners, no persistent cache | `test_large_scrambled_history_matches_domain_reference_in_one_query`: 3,000 deterministically scrambled events, Python domain oracle, cursor row count, query count, microsecond timestamps and a subsequent insert; visible checks cover empty selection and neighboring reports |
| `py-django-annotate-subquery` / clinic roster | Open future appointment count; integer zero; existing approved-minute annotation must not fan out | `hidden.py`: `test_unrelated_annotations_do_not_fan_out`, `test_empty_and_nonmatching_counts_are_integer_zero` exercise multiple sessions/appointments, rejected states, past appointments and absent children |
| Same | Lazy queryset; clinic isolation, name/ID order, inclusive aware boundary, freshness and one query independent of roster size | `test_boundary_clinic_isolation_ties_and_fresh_state`, `test_query_count_is_constant_at_one_and_fifty_doctors`; query capture starts before queryset construction and covers evaluation |
| `ch-py-argmax-state` / utility meters | Latest event by `(observed_at, version)` before online/region filtering; utility isolation, full payload and ascending IDs | `hidden.py`: `test_current_state_precedes_online_and_region_filters`, `test_version_ties_choose_the_complete_latest_payload` cover disconnection, relocation, single events and 40 ties |
| Same | Time outranks version, microseconds, quoted parameters, fresh state, one query returning current rows only | `test_event_time_over_version_precision_parameter_binding_and_freshness`, `test_single_query_returns_only_current_rows_and_stable_order`; 100 meters with historical events and measured returned-row count |
| `go-sqlc-interval` / payroll | Use supplied instants as inclusive start/exclusive end; preserve organization, ordering, fields and 64-bit signed amounts | `hidden_test.go`: `TestHiddenFractionalEndAndExclusiveMidnight` checks the final fractional second, next midnight, other organizations, zero/negative/large amounts and tied timestamps |
| Same | Calendar boundaries and IANA zones, not UTC rounding or fixed 24-hour days; query source and generated output synchronized | `TestHiddenDSTUsesSuppliedInstants`, `TestHiddenYearChangeFractionalZoneAndTies` cover 23/25-hour days, year change and fractional offsets; checker runs actual pinned sqlc regeneration and compares generated files |
| `ts-typeorm-fanout` / ticketing | Parent-based pages and total, published tenant events, zero-child parents, full child collections | `hidden.test.ts`: `hidden: totals count matching parents and pages contain complete events` checks sizes 1/2/5, multiple pages, eight children on one event, empty collections and other tenants/drafts |
| Same | Enabled-child eligibility must not trim children; quoted values and complete fields | `hidden: ticket eligibility retains all child types` checks disabled-only disqualification, mixed kinds, disabled children, zero capacity and quoted filter values |
| Same | Timestamp/ID order, empty/out-of-range pages, fresh data and at most three queries | `hidden: stable ties, empty pages, fresh data and bounded work` instruments the real query runner and repeats tied-page reads; visible checks preserve the editor selector |
| `pg-expr-index-lower` / library membership | Only named expression index via model state and AddIndex; natural plan, at most 64 buffers and 10× improvement at 100,000 rows | `hidden.py`: `test_real_lookup_index_work_and_reversible_state` runs the immutable lookup and EXPLAIN on three present addresses and one missing address across five branches; checks named-index use and both work bounds |
| Same | Clean migration state, unchanged results/data/schema/old indexes, no-op reapply, reverse and restore | Same lifecycle test fingerprints all rows/columns/constraints, compares existing index definitions and lookup results, checks migration state and reverses/reapplies; visible checks cover mixed-case lookup and branch/active semantics |
| `ch-go-skip-index` / CI build history | Only named job-ID index; materialize old parts; native query reads at most 32,768 of 1,048,576 rows | `hidden_test.go`: `TestHiddenExistingPartsReadRowsBoundAndLifecycle` measures actual progress for three present IDs and one absent ID, with one thread and query cache disabled; confirms the pre-index scan is at least 90% |
| Same | Unchanged results/layout/data; ledger-backed no-op repeat, down/reapply, correct future parts and bound job IDs | Same lifecycle test checks row/layout fingerprints, index count, ledger count, down/reapply benefit and duplicate job IDs in newly inserted parts; `TestHiddenQuotedJobAndCompleteFields` checks quoted IDs, timestamps, project IDs, outcome and chronological/ID order |

Scope checks are additional to these behavioral tests. Source manifests include paths, bytes and modes. Named-function tasks preserve surrounding bytes and signatures; payroll preserves all generated content outside its SQL literal. The meter task preserves public interfaces in its allowed reporting package. Migration tasks permit only their stated additions/model value. The TypeScript checker uses the TypeScript parser, rather than treating incidental identifier names as forbidden operations.

## Decoy design

Each decoy declares a specific failing behavioral test in its adjacent JSON file. All decoys must pass visible checks; a syntax, collection, compilation or scope failure does not establish task validity.

| Task | Two plausible wrong fixes | Why the hidden assertion distinguishes them |
|---|---|---|
| Freight | Timestamp ordering without ID; max-time join-back | Timestamp ties select the wrong payload or duplicate a parcel |
| Clinic | Joined filtered count; subquery without zero fallback | Independent session totals inflate, or an empty count is NULL |
| Meters | Filter before selecting current; omit version from argMax | Disconnected/moved meters reappear, or equal-time payload is stale |
| Payroll | Include next midnight; round supplied instants to UTC dates | Boundary row leaks in, or local-day entries disappear/appear around DST |
| Ticketing | Change only limit/offset to take/skip; filter the loaded child join | Total still counts joined rows, or qualifying parents lose valid child rows |
| Library | Plain-email index; Upper-email index | Correct results and clean migration state remain, but the real lower-expression lookup cannot use the named index |
| CI builds | Add index without materialization; minmax on pseudorandom IDs | Existing parts still exceed the declared read-work bound |

Reference patches and decoys were compiled/typechecked where appropriate and exercised against real PostgreSQL/ClickHouse instances. Application code was not changed to accommodate an agent response. Both app copies must remain byte-and-mode identical, and reference scripts check original source anchors before editing.

## Calibration repairs and limitations

Numbered evidence retains failed attempts. Library attempt 1 exposed a scope probe accidentally entering Django's migration-discovery package; the application now uses `schema_migrations`, so the extra-file probe is an ordinary unrelated Python file. Payroll attempt 1 exposed a `python`/`python3` mismatch in the Go image. Attempt 2 exposed Go JSON test output not being recognized by the validator: the checker now retains raw JSON and emits its standard Go output records in the command log. Both Go tasks use that reporting format.

Static review also removed an overly narrow migration-expression call whitelist and a blanket TypeScript identifier blacklist, and made the payroll query header/comment checks accept ordinary formatting. Changed checkers receive full recalibration. These are task validity repairs, not agent tuning.

Named-check timing is reported conservatively as the complete cold environment phase, including startup/runtime checks and cleanup. It is an upper bound for the named checks together, not a claim that image builds fit that duration. Application dependencies are pinned or vendored; shared baseline-runtime requirements and apt installation follow the Wave 2 format and are not a complete immutable build lock. Thus grading is offline, but a future rebuild is not guaranteed bit-identical from task files alone. Grading runs on an internal Docker network without internet access. Cached images are retained, while validation containers, networks and volumes must be removed.

Final accepted attempts, source identities, timing, gate results and cleanup are indexed in [Wave 3 evidence](wave3-evidence/README.md). The seven-task G7 target remains unchanged and unmeasured until the bench host's authorized gate run.
