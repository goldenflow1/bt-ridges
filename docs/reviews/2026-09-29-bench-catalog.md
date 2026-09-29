# Independent review of the five practice tasks

All five full Docker validations passed: **47/47 gate checks**, comprising 37 patch evaluations plus the five baseline regression checks and five offline checks. The reported scoring results are reproducible. Two additional probes found gaps in the TypeScript checker and the validator's decoy classification; neither changes the observed results for the supplied patches.

This was a review, not an implementation change. Task sources, reference solutions, checkers, and validator code were not edited. Additional patches and test code ran only in disposable containers. Evidence is saved in `docs/reviews/bench-catalog-evidence-2026-09-29/`.

## Findings

### BC1 — P2: TypeScript accepts ordering by the unrounded rate

Location: `bench/tasks/dev/ts-prisma-groupby/tests/completion_rate_hidden.test.ts:48` and `:79`.

The statement requires ordering by the **rounded** rate, then course ID. The existing ordering test has distinct rounded rates; the small-fractions test converts results to a map and does not assert their order. The visible equal-rate test uses rates that are equal before rounding too.

I submitted a plausible wrong patch that fixes the displayed percentage with `ROUND(..., 1)` but changes the SQL ordering to the unrounded expression:

```sql
ORDER BY COALESCE(COUNT(e.completed_at) * 100.0 / NULLIF(COUNT(e.id), 0), 0) DESC, c.id
```

The actual verifier returned **reward 1**, with no failed checks. A subsequent independent test against that patched app created these courses in order:

| Course ID | Completed / enrolled | Exact percentage | Rounded percentage |
|---|---|---|---|
| 1 | 1 / 1500 | 0.0666… | 0.1 |
| 2 | 1 / 1000 | 0.1 | 0.1 |

Expected IDs: `[1, 2]`. Actual rows: `[[2, 0.1], [1, 0.1]]`. The assertion failed.

Add a hidden test where distinct exact rates round to the same displayed rate, with the lower exact rate assigned the lower ID. Store this patch as another decoy. Renaming “ordering uses the precise rate” to refer explicitly to the rounded rate would also align the test with the statement.

Evidence: `unrounded-order-decoy.patch`, `unrounded-order-junit.xml`, `rounding-tie-probe.ts`, and `unrounded-order-result.json` in the evidence directory. The independent test was added only after the original verifier had produced reward 1.

### BC2 — P2: a collection error counts as a semantic decoy failure

Location: `bench/validate_task.py:309–322`, especially the classification at line 317.

The validator infers a behavioural failure from the outer JUnit check name. Those checks also wrap compiler, import, collection, and setup failures. Consequently, a failure named `hidden_revenue_fanout_worlds` does not establish that a behavioural assertion ran.

Reproduction: introduce invalid Python syntax inside the allowed SQLAlchemy function. Run the real task verifier, then apply the validator's unchanged decoy acceptance condition to its returned reward and failed-check names.

```text
reward = 0
failed checks = bounded_customer_revenue_function,
                python_compilation, ruff_lint,
                regression_report_tests, hidden_revenue_fanout_worlds
pytest = collected 0 items / 1 error; SyntaxError
accepted_by_current_decoy_condition = true
```

Thus the new condition rejects scope-only failures, but it does not yet guarantee failure for the intended behavioural reason. The supplied 12 decoys did fail actual behavioural checks in this run; this finding concerns the gate's guarantee for future decoys.

Require successful applicability, structural checks, and compilation, and consume structured inner test results that distinguish executed assertion failures from collection/setup errors. Record an expected failing test or failure category for each decoy. If a decoy is advertised as passing visible tests, enforce that separately; retain the documented Go exception rather than silently classifying it as sample-passing.

Evidence: `syntax-error-decoy.patch` and `syntax-error-result.json`. Full probe log: `/tmp/validate-py-sqla-orders-fanout-rczo25r7/syntax-error-decoy.verifier.log`.

### BC3 — P3: the generated new-file variant does not isolate scope rejection

Location: `bench/validate_task.py:253–255` and `:325–330`.

The generator writes `// helper` regardless of language. For Go, the resulting `extra_helper.go` has no package declaration. Its verifier run failed tree conservation, but also `go_vet`, visible tests, and hidden tests with `expected 'package', found 'EOF'`. For Django, the extra `.py` file also failed Ruff because `// helper` is invalid Python.

The claimed zero scores are correct, and the logs explicitly show functioning conservation checks. However, B-VALID-05's reward-only acceptance would still pass if conservation regressed while these syntax failures remained. Generate a valid harmless file for each language, require the scope/conservation failure, and require the solution's behavioural checks to remain passing. The other-file and mode variants passed this stronger observational check in the current run.

## Full validation results

| Task | Gate checks | Empty | Reference | Supplied decoys | Scope variants | Elapsed |
|---|---:|---:|---:|---:|---:|---:|
| py-sqla-orders-fanout | 9/9 | 0 | 1 | 2/2 scored 0 | 3/3 scored 0 | 450.7 s |
| ch-py-replacing-final | 10/10 | 0 | 1 | 3/3 scored 0 | 3/3 scored 0 | 509.2 s |
| go-sqlx-pagination | 9/9 | 0 | 1 | 2/2 scored 0 | 3/3 scored 0 | 304.4 s |
| ts-prisma-groupby | 9/9 | 0 | 1 | 2/2 scored 0 | 3/3 scored 0 | 439.4 s |
| py-django-n-plus-one | 10/10 | 0 | 1 | 3/3 scored 0 | 3/3 scored 0 | 480.8 s |

Every baseline visible-check run exited zero and left a clean Git tree. Every empty patch failed its hidden behavioural group. All supplied decoys failed hidden behavioural groups; only Go's `split-predicate` additionally failed visible tests, matching the documented caveat. No supplied decoy relied solely on a scope or build failure.

The Django reference patch changed both `recipes/serializers.py` and `recipes/views.py`; transport and grading preserved both changes. This directly exercises multi-file solution support.

The validator generates `internal: true` on the default network. All five task Compose files use that default network and do not define a public alternative or host networking. Live Docker inspection also confirmed `Internal=true` on sampled SQLAlchemy, ClickHouse, and TypeScript verifier networks. Successful reference and regression runs therefore support B-VALID-06 for runtime after image construction; image builds themselves can use the network.

## Integrity, cleanup, and documentation

- All five `environment/app` and `tests/app` trees matched by path, content, and mode before execution, including Go's vendored source.
- `ruff check bench/validate_task.py` passed.
- Before/after Docker snapshots are identical for containers, networks, and volumes. No validation resources remained; the pre-existing unrelated container/network/volume were preserved. Images were retained by the validator's default behavior.
- Two full task validations ran concurrently. The focused probes started after Go and TypeScript finished, alongside the remaining Django run. The durations above are observations for this machine, not performance guarantees.
- The current Quarry guard does report Go/TypeScript symbol bounds as uninspected, while the task checkers use language parsers. The documented M4 limitation is accurate.
- Small catalog correction: the ClickHouse task uses a custom standard-library HTTP client (`meterline/chclient.py`), not `clickhouse-connect` as the coverage matrix says. The validator description in section 2 also still says B-VALID-01..05 although it now runs 06.
- Source duplication remains a maintenance risk. Making the existing content/mode comparison an automatic validation prerequisite would prevent accidental divergence.

Full run logs remain at:

```text
/tmp/validate-py-sqla-orders-fanout-gbdyxxym
/tmp/validate-ch-py-replacing-final-6a_9z975
/tmp/validate-go-sqlx-pagination-9kzgtkat
/tmp/validate-ts-prisma-groupby-4flehtzh
/tmp/validate-py-django-n-plus-one-m2fb_myw
```

This verifies the catalog's current calibration cases. It does not measure Quarry's live solve rate or cost; no model calls or competition submission were made.
