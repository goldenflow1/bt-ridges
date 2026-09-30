# Wave 2 ClickHouse practice tasks

Status: all four tasks Docker-validated, 66/66 validity checks passed.
No inference runs.

Static validation: Python and TOML parsing, `ruff check --no-cache`, identical
application copies, exact reference-source anchors, reference Python syntax,
all nine decoy patches applying cleanly, and all declared failing test IDs present.
Source/reference scope guards were also exercised offline; a public-signature
mutation is rejected in all four tasks. These checks do not establish behavioral
correctness; Docker evidence is required.

All four tasks use real ClickHouse 24.8 over the HTTP API, two isolated databases,
separate environment/checker images, the existing source-conservation and patch
transport checks, and the full miner baseline package list during image build.
App copies are byte-identical. Reference scripts check the complete source anchor.
Every decoy declares an expected executed behavioural assertion in its JSON sidecar.

| Task | Contract coverage / distinguishing tests | Wrong variants |
|---|---|---|
| `ch-py-uniq-exact` | `test_large_exact_cardinality`: 180,013 and 310,019 permuted IDs; `test_null_is_not_a_visitor`: NULLs and duplicates; `test_zero_duplicates_tenants_and_half_open_bounds`: valid zero, duplicate visits, tenant isolation and both interval endpoints; `test_all_null_and_quoted_tenant`: zero result and bound input | `uniqCombined64` remains approximate; NULL-to-zero sentinel invents a visitor |
| `ch-py-join-defaults` | `test_missing_and_valid_zero_identifier`: genuine absence vs valid zero; `test_empty_label_is_registered`: valid blank label; `test_disabled_cross_tenant_order_and_empty_code`: enabled state, tenant isolation, order and valid blank device code; `test_repeated_events_and_quoted_tenant`: preserve every event and parameterization | zero ID means absent; blank label means absent |
| `ch-py-tz-buckets` | `test_empty_days_are_materialized`: gaps and order; `test_spring_forward_local_days_and_half_open`: 23-hour day with millisecond endpoints; `test_fall_back_day_includes_last_hour`: 25-hour day and both instances of repeated hour; `test_fractional_offset_tenant_and_leap_day`: Kathmandu, leap day and tenant isolation; `test_no_events_and_reverse_range`: absent tenant, empty and reversed intervals | UTC grouping; fixed 86,400-second days; inner join drops empty days |
| `ch-py-prewhere-orderkey` | `test_filter_status_range_and_tenant`: status, signed amounts, tenant and half-open bounds; `test_primary_key_read_rows_drop_tenfold`: 1,048,576 rows over 128 tenants, three distinct targets, exact answer vs the original query and >=10x fewer rows; `test_same_tenant_narrow_window`: timestamp bound within a tenant | PREWHERE still hashes the key; key pruning silently drops status predicate |

The optimization test reads `statistics.rows_read` from the exact HTTP query
response, so it needs neither global query-log permissions nor asynchronous log
flushes. Baseline and candidate use one thread with the query cache disabled. A protected
query wrapper snapshots statistics immediately for each actual call and requires
exactly one call; a later dummy query or mutation of `last_statistics` cannot hide
work. Timezone checks also require one query for counting and day generation.
A workload-size assertion ensures the original query really scanned the large
fixture. The measurement is work-based, not a noisy wall-clock threshold.

Limitations: these are small synthetic applications, with declared schema and
bounded edit scope; they cannot substitute for public or competition tasks.
The timezone visible tests deliberately cover only pre-existing unrelated/empty
behaviour because that task asks to author a missing report. The missing-device
task names the permitted file but leaves the faulty function to be traced. The
ClickHouse major/minor tag and pip baseline dependencies follow the existing
catalog conventions and are not digest/version locked; full runtime identity
remains a separate B2 concern.

Independent cross-review: Python/PostgreSQL task author reviewed these tasks;
public-signature/construct enforcement for unnamed scope and per-call statistics
snapshots were added following that review. Docker results follow below.

First real uniq validation caught an extra visible failure in the approximate
decoy: `uniqCombined64` on nullable data returned NULL for an empty input. The
decoy now normalizes that to zero, retaining the measured approximation error
(180,194 instead of 180,013). Reference and test expectations are unchanged; a
complete rerun subsequently passed 16/16. Named function size limits inherited by the checker
are now explicitly disclosed in the three applicable task instructions.

## Docker results (serial runs, 2026-09-30)

- `ch-py-join-defaults`: **PASS 16/16**, reference reward 1, empty reward 0,
  both sample-passing decoys rejected by declared assertions, and all three
  scope variants rejected by conservation checks alone. [Full validation log](wave2-evidence/ch-py-join-defaults.validation.log).
- `ch-py-uniq-exact`: **PASS 16/16** on the complete rerun after the
  approximate-decoy repair. Both decoys pass visible checks and fail their
  declared assertions; all three scope probes reject only conservation
  violations. The initial 15/16 attempt remains archived.
  [Full rerun log](wave2-evidence/ch-py-uniq-exact.retry1.validation.log).
- `ch-py-tz-buckets`: **PASS 18/18**, including all three sample-passing
  decoys via the declared assertions and scope-only rejections. [Full validation log](wave2-evidence/ch-py-tz-buckets.validation.log).
- `ch-py-prewhere-orderkey`: **PASS 16/16**. The reference preserves semantics
  and meets the >=10x read-row reduction on all three tested tenants. Both decoys
  pass visible tests and fail their declared assertions; scope probes reject only
  conservation violations. [Full validation log](wave2-evidence/ch-py-prewhere-orderkey.validation.log).
