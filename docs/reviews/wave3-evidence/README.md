# Wave 3 construction evidence

Status: all seven task calibrations passed on 2026-09-30. G0–G5 passed. G7 agent evaluation has not been run.

## Independence and provenance

The author has read only the Wave 3 plan, the catalog and Wave 1/2 task files as existing design inputs during this construction phase. The referenced plan was fetched from `origin/master` because it was absent from the initial checkout. Agent source, prompts, packs, bundles, experiment logs and agent-run logs are excluded from construction reads. Task-calibration logs produced here contain only empty, reference, decoy and scope-probe executions.

This is **not fresh-session authorship**: the coordinating conversation already contained Wave 2 and experiment context before construction began. A fresh-agent preference was requested; absent a reply, construction continued in this thread under the read restrictions. This limitation must remain visible when assessing held-out independence; it is not claimed to be a blind external benchmark.

No agent is run on these tasks during construction or validation. Any later use of a task to tune the agent requires moving it to dev and replacing it. The maintainer's predeclared G7 target in the plan is unchanged.

## Acceptance evidence

Each numbered attempt retains its full validator output, verifier artifacts and before/after task-source identity. Failed attempts are preserved. Completion also requires a statement-to-test matrix, byte-and-mode-identical app copies, cold named-check timing well under 120 seconds, scope-only rejection of conservation probes, and cleanup of all task resources.

Only the plan, task fixtures and task-validity evidence are being changed. No inference, tuning or upload is part of this work.

## Accepted results

**112/112 validation checks passed.** All seven empty patches score 0 and all seven references score 1. All 14 decoys pass visible checks and fail their declared behavioral assertions. All 21 scope probes apply and are rejected only by scope/conservation checks. Every task passed B-VALID-11 and ran named checks/grading on an internal Docker network without internet egress.

| Task | Accepted log | Checks | Cold environment phase (upper bound for named checks) |
|---|---|---|---|
| `py-sqla-distinct-on` | [Attempt 1](py-sqla-distinct-on.attempt1.validation.log) | 16/16 | 42 s |
| `py-django-annotate-subquery` | [Attempt 1](py-django-annotate-subquery.attempt1.validation.log) | 16/16 | 39 s |
| `ch-py-argmax-state` | [Attempt 1](ch-py-argmax-state.attempt1.validation.log) | 16/16 | 39 s |
| `go-sqlc-interval` | [Attempt 3](go-sqlc-interval.attempt3.validation.log) | 16/16 | 33 s |
| `ts-typeorm-fanout` | [Attempt 1](ts-typeorm-fanout.attempt1.validation.log) | 16/16 | 51 s |
| `pg-expr-index-lower` | [Attempt 3](pg-expr-index-lower.attempt3.validation.log) | 16/16 | 45 s |
| `ch-go-skip-index` | [Attempt 1](ch-go-skip-index.attempt1.validation.log) | 16/16 | 46 s |

The complete environment phase includes startup/runtime prerequisites and cleanup. Image build time is separate. `verifier runs` in each validator log is the total across all candidate patches, not the duration of one checker invocation.

- [Final results](final-results.json): accepted attempts, counts, source-manifest hashes and app-copy identity.
- Numbered attempt JSON files: complete source manifests at validation time. The final audit requires the current task tree to match its accepted manifest exactly.
- [Statement-to-test review](../wave3-heldout.md): domain contracts, hidden assertions, decoy rationale, repairs and provenance limits.
- [Repository gates](gates.log): G0–G5, including offline end-to-end checks, prescreen lint and originality checks, all passed. No held-out inference was performed by these gates.
- [Local image identities](image-identities.json): image content IDs retained for the calibrated environment/checker builds; a future rebuild may resolve different shared baseline packages.
- [Cleanup](cleanup.json): no containers, networks or volumes remain for any recorded Wave 3 validation project. Cached images remain; unrelated resources were left untouched.

Failed attempts are retained: library attempt 1 (migration-discovery interaction with the extra-file scope probe); payroll attempt 1 (`python` unavailable in the Go image) and attempt 2 (Go JSON output not recognized as per-test behavioral evidence). Library attempt 2 already passed; attempt 3 recalibrates its relaxed expression guard. Payroll attempt 3 also checks the less restrictive query-header/comment handling.

The tasks are ready for the separately authorized G7 run on the bench host, subject to the provenance limitation above. The predeclared target remains 11/21 valid trials solved, zero agent mechanical failures, mean reconciled cost at most $0.03, and green upload gates. Construction does not establish an agent solve rate or competition readiness.
