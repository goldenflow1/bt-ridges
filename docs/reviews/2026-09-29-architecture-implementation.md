**Quarry architecture and implementation review — 2026-09-29**

**Verdict: sound direction, incomplete M0, not ready to upload.** The most urgent problem is the final patch handoff: a correct edit can fail before task verification because the agent leaves the edited working tree behind. The existing offline integration test conceals this by stashing changes itself. Fix mechanical correctness before investing in additional model phases or cost optimization.

This review covers `architecture.md`, all runtime modules and prompt/knowledge packs, the build and test tooling, harness specifications, milestone plan, benchmark runner, and practice-task validation design. It compares these with the current Ridges documentation and source, including the local upstream checkout at `d74410d8`. Practice-task Docker environments and paid inference runs were not executed. Reference solutions were not used to design agent fixes. Production source was not changed.

**Challenge fit**

The task is to modify the application's actual data-access path across PostgreSQL and ClickHouse, including ORM code, query builders and migrations. Result semantics, edge cases and scope matter; named regression checks alone do not establish correctness or improved performance. The six public tasks demonstrate a format, not the full distribution. Quarry's focus on production paths, schema discovery, reproducible scenarios and work measurement matches this challenge. [Official niche requirements](https://docs.ridges.ai/competitions/database-query-engineering).

The single-file bundle, `agent_main(input) -> str`, current working directory, proxy endpoint, budget variable and timeout variable align with the interface. The final return lifecycle does not yet align with the runner. [Agent contract](https://docs.ridges.ai/guides/agent-contract).

**Confirmed implementation findings, in priority order**

**R1 — P0: restore the repository before returning the selected patch.**

Locations: `src/quarry/shell.py:181`, `src/quarry/shell.py:206`, `src/quarry/git.py:114`, `tests/e2e/test_bundle_offline.py:155`.

`Workflow.result()` returns the diff while the working tree still contains its changes. `run_agent()` only kills subprocesses and logs telemetry in `finally`. The local apply check uses a temporary index populated from HEAD, so it succeeds despite the dirty working tree. Ridges subsequently runs ordinary `git apply --check` in that same working directory; the runtime does not restore it first. This is present both in the pinned checkout and current upstream. [Ridges runner](https://github.com/ridgesai/ridges/blob/main/ridges_harbor/agents.py), [runtime](https://github.com/ridgesai/ridges/blob/main/ridges_harbor/ridges_miner_runtime.py).

Reproduction through `run_agent()` with a scripted edit and finish:

```text
patch_nonempty=true
pristine_index_check=true
runtime_worktree_check=false
worktree_dirty=true
```

An ordinary replacement fails with `patch does not apply`. New-file patches similarly encounter an existing file. The integration test's `git stash -u` performs cleanup that the deployed agent never performs.

Correction: capture an immutable baseline; select and preserve the patch; restore run-owned changes on every exit path; perform the actual working-tree apply check; return the saved patch. Preserve any pre-existing state if running outside the platform. Test the real handoff without test-side cleanup, including an earlier candidate selected after a later failed attempt.

**R2 — P1: retry attempts share no absolute deadline.**

Locations: `src/quarry/llm.py:130`, `src/quarry/loop.py:47`, `src/quarry/clock.py:57`.

`complete(timeout=...)` grants the same timeout to each of four attempts and adds backoff. It never recomputes remaining phase time. A simulated 20-second allowance produced four 20-second attempts and about 97 seconds elapsed including backoff. This was virtual time, not a real network benchmark. With 180-second attempts, one call can consume roughly twelve minutes plus backoff.

The driver also dispatches every tool in a reply without checking its phase timer between calls. Shell timeout calculation uses the overall clock rather than the phase deadline, and Git operations have independent fixed timeouts. The existence of `Clock` therefore does not guarantee timely return.

Correction: pass an absolute monotonic deadline through inference, retries, tools and finalization. Recompute remaining time before every attempt, sleep and tool. Keep a separately bounded cleanup reserve. Fault-test slow providers and batches of long-running tools.

**R3 — P1: explicit method scope is not consistently enforced.**

Locations: `src/quarry/spec.py:210`, `src/quarry/guard.py:176`, `src/quarry/guard.py:275`.

Reproduction: `Change only f() in m.py` correctly extracts the file and function but leaves `rest_frozen=False`. Editing both `f()` and its neighbour passes every guard check. The guard requires an additional phrase such as “rest of the file unchanged” before enforcing symbol boundaries, although “only f()” already specifies them.

A second reproduction deletes the entire named file under an explicit method-only, frozen-signature, frozen-imports contract. The guard still reports eligible: bounded-symbol, signature and syntax checks iterate modified files and miss deletion.

Correction: represent file and symbol permissions directly, infer exclusion from explicit “only” wording, and reject removal or unresolved replacement of a required symbol/file. Required checks must not report success when they inspected no relevant code.

**R4 — P1: file-level construct restrictions can silently pass without inspection.**

Location: `src/quarry/guard.py:311`.

Reproduction: `Only edit m.py. Do not use loops.` compiles to `forbidden=['no_loops']`. Adding a loop passes the guard because `_SymbolPairCheck.pairs()` yields nothing when no symbol was named. Added files are also omitted from this iterator. Go and TypeScript do not receive comparable structural checking.

Correction: check the appropriate changed module or changed definitions for file/open scope, and include allowed new files. Record unsupported language checks as unavailable rather than PASS. Use statement-derived restrictions, not restrictions inferred from public checker internals.

**R5 — P1: validation results can refer to different code from the returned candidate.**

Location: `src/quarry/shell.py:129`.

`gate()` captures `report.diff` before running named commands. A formatter, generator, migration helper or test that modifies source can change the tree afterward. The stored candidate still uses the earlier diff.

Reproduction: capture a function returning `2`; run a command that updates it to `3` and successfully asserts the result is `3`. The gate reports eligible and checks passed, while the returned candidate still returns `2`.

Correction: associate evidence with a patch/tree hash. Detect command-induced changes, rerun hygiene checks and invalidate affected evidence. Store a candidate only once the validated tree is stable. Guard repair must also invalidate prior semantic evidence when it changes code.

**R6 — P1: the guard deletes some explicitly requested production files.**

Locations: `src/quarry/spec.py:240`, `src/quarry/guard.py:143`, `src/quarry/tools.py:220`.

Reproduction: `Create a new file service.py to implement the production query.` sets `allow_new_files=True`; `CreateTool` creates it successfully; `DropUntracked` then removes it. Retention requires an existing scope directory or a hard-coded migration/database directory name, and this statement supplies neither.

Correction: compile explicit new paths and permitted directories into the scope policy and share that policy between creation and cleanup. Do not privilege database-themed directory names over a production module the task explicitly requests.

**R7 — P2: unresolved configuration can become the default database target.**

Locations: `src/quarry/profile.py:160`, `src/quarry/profile.py:226`, `src/quarry/tools.py:278`.

Static parsing changes dynamic config expressions into `None`, then substitutes connection defaults. A normal Django config using `os.environ[...]` produced database target 0 with host `localhost`, empty name and empty user, followed by target 1 containing the correct `PG*` environment values. The SQL tool defaults to target 0. It has no tool to register a subsequently discovered connection.

Correction: distinguish unresolved values from intentional defaults, resolve supported environment expressions, prioritize complete connections, and probe connectivity. Permit runtime discovery through the application's own configuration mechanism without letting discovery mutate the application.

**R8 — P2: extracted shell checks do not preserve shell semantics.**

Locations: `src/quarry/spec.py:144`, `src/quarry/shell.py:138`.

Every eligible fenced block becomes separate command lines, regardless of whether it describes an example, setup or verification. Each command starts a new shell in the repository root. Consequently `cd backend` followed by `pytest` does not run pytest in backend; an `export` does not carry forward. Whitespace normalization also changes spaces inside quoted strings. Untyped SQL blocks can be mistaken for shell checks. This is established by the extraction and execution code, not a live task failure.

Correction: preserve explicit command blocks as scripts, retain quoting and working-directory context, and distinguish examples from required checks. Store source text and provenance for compiled requirements so normalization can be audited.

**Additional implementation concerns**

- `GitRepo` records `self.head` but later compares against symbolic `HEAD`. An incidental commit made through `shell` can move the baseline and erase the intended diff. Use the captured commit consistently.
- The PostgreSQL tool's “always rolled back” description is stronger than the code: arbitrary submitted SQL can include `COMMIT` before the appended rollback. Sequence operations also survive transaction rollback. This is a static finding; no database writes were executed during review. Prefer controlled application transactions, read-only exploration by default, and disposable fixtures for writes. [PostgreSQL COMMIT](https://www.postgresql.org/docs/current/sql-commit.html), [sequence behavior](https://www.postgresql.org/docs/current/functions-sequence.html).
- `ProcessRunner.communicate()` buffers all output before truncation. Prompt output is capped, process memory is not. Large logs or query output can exhaust memory; stream into a bounded buffer or file.
- `checks_ok` starts true even if no checks exist; calling `finish` adds evidence points without proving semantics. `Candidate.eligible` excludes neither regression failures nor missing semantic proof. This is M0 bookkeeping, not an evidence ledger.
- `fallback_diff()` can return an applyable patch that failed hard guard checks. The specification explicitly allows last-resort candidates, but the architecture must not simultaneously promise that every returned patch is in scope and valid. Mechanical validity and confidence in the fix need distinct states.

**Architecture-to-implementation assessment, step by step**

| Step | Current implementation | Assessment / next requirement |
|---|---|---|
| Packaging and entry point | Readable single-file bundler, embedded assets, stdlib runtime, Python 3.9 import check | Keep. Add runtime-handoff integration coverage. |
| Control shell | Clock, wallet, driver loop, repair rounds, candidate store | Useful foundation; deadline propagation and final cleanup remain incomplete. |
| P1 specification | Regex/Markdown extraction, weighted kind classification, numbered bullets | Partial M1. No LLM normalization, structured edge-case table or source-backed confidence. Prose requirements outside bullets remain only in the full prompt. |
| P2 profiling | Manifest detection, literal Django config and DSNs, binaries, writable paths, pack selection | Useful. No live connection validation, privileges probe, general runtime config resolution or import-based layer discovery. |
| P3 locating | Generic read/search/list tools in one driver conversation | No dedicated locator, symbol outline, findings card, phase boundary or compact handoff. |
| P4 lab/build | Exact-match edit/create, scratch, shell and SQL tools; reproduction instructions in prompts | Tools exist. No enforced baseline, reproduction artifact or application-context runner. |
| P5 proof | Python compile, guard, named checks | T3 semantic proof and T4 work proof are absent. No requirement-to-evidence ledger or evidence invalidation. |
| P6 critic | No critic phase | Explicit future work. Add only after reliable execution and measurable failure data. |
| P7 guard | File cleanup, Python AST rules, symbol splice, mode and index apply checks | Valuable but incomplete; R1–R6 invalidate broad guarantees. Go/TS method scopes are not protected equivalently. |
| P8 selection/retry | Store candidates; up to three repair rounds on the same route and transcript | No independent second strategy. Model fallback responds to provider failure, not semantic weakness. |
| Measurement | Offline tests, free gates, sequential live runner, practice-task validator | No live agent baseline in the experiment log. Held-out submission readiness is unestablished. |

The implementation is a tool-using driver with deterministic safeguards. The proposed staged, evidence-based system is still a roadmap. That is acceptable for M0, but M0's own live exit criterion has not been met.

**Design decisions to retain and adjust**

Retain the separation between runtime code, reusable database knowledge and development benchmarks. Keep exact-match edits, scripts outside the target repository, non-empty patch checks, process-group cleanup and injectable collaborators. The strongest planned improvement is proof through the actual production function/query, because an isolated SQL experiment can be correct while the application still runs a different query.

Implement the next proof phase narrowly: record the target function, schema and caller; reproduce one requirement-derived failure; run the production path before and after; record an assertion and patch hash. Add additional cases for duplicate grain, NULLs, empty groups, ties and ordering as appropriate. For optimization, compare equivalent results and capture actual query count/plans/work at representative volumes.

Do not require database work to be independent of N for every optimization. An aggregate over all input rows can legitimately be O(N); N+1 query count, rows examined, buffers and elapsed time are different quantities. Prove the task's specific performance requirement. For ordered results, comparison must retain ordering and duplicate multiplicity; a set comparison or indiscriminate sort can conceal the defect.

The planned rule forbidding all new string literals also found in tests/scenario data is too broad: legitimate field names and business statuses can appear in both. Judge whether values come from the task contract and application domain; do not treat string overlap as a correctness oracle.

**Cost and competitive strategy**

The runtime driver budget is `0.29 × 0.9 × 0.85 = $0.22185`, with up to 45 turns per repair round. There is no $0.025/$0.03 soft spending policy. This does not prove high average cost, but it means the target is currently an aspiration. The default model's listed prices match the table; actual proxy behavior, caching, reasoning-token use and cost are still unmeasured. [OpenRouter model listing](https://openrouter.ai/openai/gpt-5.6-luna).

The worked reward examples are approximately consistent with the upstream formula, but Appendix C differs near thresholds: upstream sums positive improvements after determining qualification, whereas the appendix independently discards each subthreshold contribution. With the document's hypothetical leader at 0.38 / $0.0437, a candidate at 0.40 / $0.043 produces about 1.996 units upstream versus 1.735 in the appendix. [Upstream incentive implementation](https://github.com/ridgesai/ridges/blob/main/utils/incentives.py).

The statement that every extra cent costs more than another solved task gains is conditional. It fails when an additional solved task crosses the qualification threshold, and depends on the leader and cost-unit cap. Establish sufficient score and repeatability first, then optimize the score/cost tradeoff. Competition policy can override the general thresholds. Current leaderboard and competition-state endpoints could not be read through the browsing tool, so the document's leader snapshot and closing-window assumptions were not independently confirmed. [Official incentive policy](https://docs.ridges.ai/incentive-mechanism).

**Benchmark and test quality**

At final inventory, there were six public task definitions and three development definitions: SQLAlchemy, ClickHouse/Python and Go/sqlx. The Go definition appeared while this review was underway. There were no held-out task definitions. The 24-row catalog is a plan, not a completed benchmark suite. Runtime validity of those containers was not assessed here.

`tools/run_bench.py` collects results, but returns success after a completed run regardless of solve rate or mechanical failures. It neither enforces G6/G7 thresholds nor compares a saved baseline. It does not save raw CLI output or a manifest containing the agent hash, task versions and effective model route, limiting reproducibility.

`bench/validate_task.py` implements B-VALID-01 through B-VALID-05, not B-VALID-06. Running successfully on a public Docker network is not evidence of offline operation. Its requirement that the solution touch exactly one file also prevents it from validating legitimate multi-file tasks such as SQL source plus generated code. Its decoy success condition checks for a parseable JUnit result, which alone does not prove failure occurred for the intended semantic reason.

Report both average per-run solve rate and tasks solved in all three repeats. Ridges uses all-validator agreement, so an intermittently successful local task is less useful than its mean suggests. Local repeats remain only a diagnostic, not a production score estimate. Preserve the held-out split; repeated tuning against it eventually makes it another development set. [Scoring policy](https://docs.ridges.ai/scoring), [local-testing limitations](https://docs.ridges.ai/guides/local-testing).

Pre-screen lint is a useful hygiene check, not a guarantee of platform acceptance or originality. A pass on one previously accepted agent cannot establish that the regex rules match the platform review. I found no stored answer dispatch in the runtime reviewed, but did not perform a provenance comparison against other agents. [Pre-screening policy](https://docs.ridges.ai/guides/pre-screening).

**Validation performed**

| Check | Result |
|---|---|
| Ruff on source, tools and tests | Passed |
| Existing unit and scenario tests | 87 passed |
| Bundle generation | Passed |
| Actual Python 3.9 bundle import | Passed after permitting access to uv's otherwise read-only cache |
| Existing offline integration tests | 4 passed after allowing the fake server to bind localhost |
| Pre-screen lint | 0 failures, 1 warning for the ClickHouse HTTP URL |
| Requirement-ID traceability | 60/60; checks naming coverage, not behavioral completeness |
| Additional targeted probes | Confirmed R1–R7, including two distinct scope failures; R2 used simulated time |
| Live models / Docker task verification / paid uploads | Not run |

The original gate invocation stopped at an environment permission error. Its remaining checks were then completed individually; source was not changed to make them pass. The existing tests all pass while the independent probes expose the failures above. This is evidence of missing test cases and an incorrect test contract, not evidence that the whole test suite is ineffective.

**Recommended execution order**

1. Fix R1 and replace the test-side stash with a real runner-contract test. Cover normal finish, model failure, budget exhaustion and selection of an earlier candidate.
2. Fix deadline propagation, scope/deletion handling, construct coverage, new-file retention and candidate/evidence identity. Add the corresponding small regression cases.
3. Run the existing public tasks through the pinned Ridges runner and record applyability, scope, solve outcome, cost, caching and elapsed time. M0 completes only after that live handoff is demonstrated.
4. Add production-path semantic proof, then optimization work proof. Keep this smaller than the full planned phase framework until it improves measured failures.
5. Complete representative Go/TS/ClickHouse and migration tasks, plus an untouched held-out set. Add mechanical and baseline-comparison failures to the benchmark command's exit behavior.
6. Compare model/critic strategies and introduce a measured soft cost policy. Upload only after a reproducible candidate passes the runtime, task and benchmark gates.

The next useful milestone is a verified end-to-end M0 baseline. Additional orchestration complexity should follow observed semantic failures from that baseline.
