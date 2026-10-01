# SPEC — Quarry Harness (M0 + deterministic parts of M1/M2)

Status: accepted · 2026-09-29 (rev 2: review 2026-09-29 findings R1–R8 + extras) · Design source: `architecture.md` (v3)

Each requirement has a stable ID and a verification method:
`unit` (tests/unit), `scenario` (tests/scenario), `e2e` (tests/e2e, offline bundle through a fake proxy), `bench` (live tasks), `manual`.
Gate G5 fails if an ID with `unit|scenario|e2e` has no test whose name contains the ID (dashes → underscores).

---

## 1. Control shell (`quarry.shell`, `quarry.clock`)
| ID | Requirement | Verify |
|---|---|---|
| H-SHELL-01 | `agent_main(input)` reads `input["problem_statement"]`, uses `os.getcwd()` as the repo root, and returns a `str`. | e2e |
| H-SHELL-02 | Deadline = start + `AGENT_TIMEOUT` − reserve, reserve = max(60 s, 5 %). Missing/invalid `AGENT_TIMEOUT` → 1500 s. | unit |
| H-SHELL-03 | Any exception inside the workflow is caught. The shell returns the best stored candidate; else the current guarded diff if non-empty; only if neither exists does it raise. | unit, e2e |
| H-SHELL-04 | Every child process started by tools runs in its own process group and is killed before `agent_main` returns. | unit |
| H-SHELL-05 | The candidate store keeps candidates with their evidence score; `best()` returns the highest score, ties broken by the smaller diff. | unit |
| H-SHELL-06 | Phase time slices: a phase gets `min(its share × total, remaining − reserve)`; a phase past its slice is stopped by the loop, not by the model. | unit |
| H-SHELL-07 | Hand-off: after choosing the patch, the agent restores the working tree, index and HEAD to the start state on every return path, then returns the first patch (chosen, then other candidates by rank) that passes a plain `git apply --check` on that tree; if none applies it returns nothing. If cleanup raises, it is retried once; if it still fails, a patch is returned only if it applies to the tree as it actually is. | scenario, e2e |
| H-SHELL-08 | Evidence identity: the state a check ran on is the diff plus every untracked file except disposable artifacts (caches, logs, coverage/test reports). If the checks change it (edit source or create a helper), the guard and checks run again on the new state; the stored candidate is the validated state, or the checks count as failed. | scenario |
| H-SHELL-09 | No checks is not check evidence (`None`, not `True`). | scenario |
| H-SHELL-10 | A candidate is eligible only if the guard passes and no required check failed. Eligible beats ineligible; an ineligible patch is returned only as a last resort, logged with its failure reasons, and only if it applies (H-SHELL-07). | scenario |
| H-SHELL-11 | Baseline checks share one phase budget (default 35% of the run, preferred minimum 60 s), capped by time remaining minus 60 s for editing. The minimum never overrides the deadline; checks that cannot start within the phase are skipped and reported. Duration, exit status and timeout are recorded on the unmodified tree. | scenario |
| H-SHELL-12 | Check timeouts come from the baseline: about 3× its duration (at least 120 s, never past the deadline). If the baseline timed out, later runs are skipped as `unknown` rather than failed; if the baseline itself failed, a later failure is `unknown` ("fails before any change too"), not evidence against the patch. | scenario |
| H-SHELL-13 | Check observations are logged, not only shown to the model: per run of each check its round, command, exit code, seconds, timeout flag and a short output tail go to the run log and the telemetry record, along with per-round loop outcome, guard eligibility and the final candidate's status. | scenario, e2e |

## 2. Wallet (`quarry.wallet`)
| ID | Requirement | Verify |
|---|---|---|
| H-WALLET-01 | Cap = `RIDGES_MAX_COST_USD` (default 0.29, invalid → 0.29). Spendable = cap × 0.9. | unit |
| H-WALLET-02 | `can_afford(estimate)` is false when estimate > remaining spendable; the LLM client refuses such calls without sending them. | unit |
| H-WALLET-03 | Actual cost is charged from `usage.cost` when the response provides it, else from the model price table and token counts; unknown models use a conservative default price. | unit |
| H-WALLET-04 | A budget refusal (HTTP 402, or an error body mentioning budget/cost cap) sets `spent = True`; later calls fail fast with `BudgetExhausted`. | unit |
| H-WALLET-05 | Per-phase caps: `wallet.phase(name, cap)` limits spending inside that phase to `cap`. | unit |
| H-WALLET-06 | Cost provenance: every attempt is recorded as `provider` (reported cost), `estimate` (usage-based, labelled), `unknown` (no usable report, including malformed successful HTTP responses; its reservation stays consumed) or `none` (evidence of no charge). Summaries separate subtotals and state accounting completeness. Bench key-usage deltas remain separate from attributable trial cost; reconciliation requires complete provider telemetry and agreement within max($0.0001, 5%). Discrepancies or missing evidence block cost-based approval, while the spending ledger still counts usage. | unit, scenario, e2e |

## 3. LLM client (`quarry.llm`)
| ID | Requirement | Verify |
|---|---|---|
| H-LLM-01 | Endpoint: `SANDBOX_PROXY_URL` → `{url}/api/v1/chat/completions`; else `RIDGES_INFERENCE_BASE_URL` → `{url}/chat/completions`. Bearer key from `OPENROUTER_API_KEY` or `RIDGES_INFERENCE_API_KEY` when present. No other hosts. | unit |
| H-LLM-02 | Retries 429, 5xx, timeouts and connection errors with jittered backoff (max 4 attempts); after 2 consecutive failures on a model, switches to its fallback model. | unit |
| H-LLM-03 | Never retries a budget refusal (H-WALLET-04). | unit |
| H-LLM-04 | Requests use `temperature: 0` and an explicit `max_tokens`. | unit |
| H-LLM-05 | Tool-call parsing is defensive: missing ids get generated ids; invalid JSON arguments become an error message returned to the model, not an exception. | unit |
| H-LLM-06 | Every call records role, model, prompt/cached/completion tokens, cost and latency in a telemetry list. | unit |
| H-LLM-07 | Every call takes an absolute deadline; no attempt, backoff or fallback passes it (per-attempt timeout = min(timeout, time left)). | scenario |
| H-LLM-08 | Cache telemetry: `cached_tokens` and `cache_write_tokens` are recorded independently as missing (`None`), zero or positive; summaries report read and write coverage with denominators, compute the read share only over calls that report it, and never infer savings from share alone. Telemetry is emitted as a versioned JSON record (`[quarry-telemetry] {...}`) that the bench runner parses into CSV. (M0.5A) | unit, scenario, e2e |

## 4. Git (`quarry.git`)
| ID | Requirement | Verify |
|---|---|---|
| H-GIT-01 | Records `HEAD` at start; `diff()` returns `git diff --binary HEAD` including new files registered with intent-to-add. | unit |
| H-GIT-02 | `apply_check(patch)` verifies a patch applies to a pristine copy of `HEAD` (via a temporary worktree or index), without touching the working tree. | unit |
| H-GIT-03 | `changed_files()` reports modified, added, deleted, untracked and mode-changed paths separately. | unit |
| H-GIT-05 | Undo touches only paths the run changed: content and staging of paths that were already dirty at start are preserved (the platform starts clean; this is a safety property for local use, not a general start-state guarantee). | scenario |
| H-GIT-04 | All comparisons use the baseline commit captured at start, not the symbolic `HEAD` (a commit made during the run cannot erase the diff). | scenario |

## 5. Spec compiler (`quarry.spec`) — deterministic pass
| ID | Requirement | Verify |
|---|---|---|
| H-SPEC-01 | Fenced `bash`/`sh`/`console`/untyped code blocks become `checks` (one command per logical line, `\` continuations joined). | scenario |
| H-SPEC-02 | Inline backtick commands in sentences starting with *run / execute / check with* become `checks` when they start with a known runner (python, pytest, ruff, go, npm, npx, pnpm, yarn, node, make, cargo, bundle, mvn, gradle, psql, clickhouse-client). "run `ruff …` on the file you changed" is kept as a check template bound to the changed file. | scenario |
| H-SPEC-03 | Scope files: backticked paths after *limit/restrict production changes to*, *you may edit only*, *only edit*, *change only*; plus any backticked path that exists in the repo when the statement bounds changes. | scenario |
| H-SPEC-04 | Scope symbols: backticked `Name.method()` / `Name.method` / `function()` near *specifically*, *only that method*, *change only*. | scenario |
| H-SPEC-05 | Freeze flags: *keep its signature* → `freeze_signature`; *rest of the file unchanged* / *everything else … stays* → `rest_frozen`; *including imports* / *use only names the file already imports* → `freeze_imports`. | scenario |
| H-SPEC-06 | Unnamed but bounded scope (*find the … method … change only that method*) → `scope.mode = "discover-one-symbol"`. | scenario |
| H-SPEC-07 | Forbidden rules derived from wording: `no_loops`, `no_comprehensions`, `no_lambdas`, `no_exception_handling`, `no_context_managers`, `no_db_writes`, `no_raw_sql`, `no_dynamic_code`, `no_python_materialization`. Only rules the statement states are emitted. | scenario |
| H-SPEC-08 | Kind: `optimization` / `repair` / `authoring` by weighted keywords; ties → `repair`. | scenario |
| H-SPEC-09 | Engine hint: `postgresql`, `clickhouse`, or `unknown` from statement keywords. | scenario |
| H-SPEC-10 | `allow_new_files`: true only if the statement asks for a new migration/file; otherwise the guard deletes new files. | scenario |
| H-SPEC-11 | The TaskSpec renders to a compact numbered checklist (≤ 2.5k chars) used verbatim as a stable prompt block. | unit |
| H-SPEC-12 | New files the statement names (`Create a new file \`x.py\``) are recorded and kept; a requested migration without a name may be created only in a migrations-style directory. | scenario |
| H-SPEC-13 | A fenced shell block is one check script (working directory, exports and quoting preserved) run with `set -e`. | scenario |
| H-SPEC-14 | An untyped fenced block is a check only if it starts like a shell command (SQL or output samples are not). | scenario |

## 6. Environment profiler (`quarry.profile`)
| ID | Requirement | Verify |
|---|---|---|
| H-PROF-01 | Detects languages and query layers from marker files and manifests (Python/Django/SQLAlchemy, Go/sqlx/sqlc/GORM/pgx/clickhouse-go, TS/Prisma/TypeORM/Knex/Drizzle/Kysely, …). | scenario |
| H-PROF-02 | Discovers DB connections: Django `DATABASES` (incl. `TEST.NAME`) by AST literal parsing of settings/configuration files; `DATABASE_URL`/`PG*`/`CLICKHOUSE_*` env vars; DSN strings in config files. Never imports app code for this. | scenario |
| H-PROF-03 | Lists available binaries (`psql`, `clickhouse-client`, `go`, `node`, `tsc`, `ruff`, `pytest`) and whether scope files are writable. | unit |
| H-PROF-04 | Selects knowledge packs from the profile; unknown stack → core pack only. | unit |
| H-PROF-05 | Config values from `os.environ[...]`/`os.getenv(...)` are resolved against the environment; unresolved values are never replaced by defaults, the same connection found twice is merged (known values replace unknown ones), and complete connections are listed first. | scenario |

## 7. Guard (`quarry.guard`) — deterministic repairs and checks
Repairs run first, then checks. A check failure makes the candidate ineligible (except as last resort).
| ID | Requirement | Verify |
|---|---|---|
| H-GUARD-01 | Tracked changes to files outside `scope.files` are reverted (when scope files are known). In `discover-one-symbol` mode, at most one production file may change. | scenario |
| H-GUARD-02 | Untracked files are deleted unless `allow_new_files` and the file lies in an allowed directory (e.g. a migrations dir next to the scope). | scenario |
| H-GUARD-03 | File mode changes are restored to `HEAD`'s mode. | scenario |
| H-GUARD-04 | Method-bounded Python files: bytes before and after the target symbol are spliced back from `HEAD`, so only the symbol's span differs. If the symbol can't be found in the candidate, the check fails. | scenario |
| H-GUARD-05 | Signature check: name, arguments, decorators and return annotation are AST-identical to `HEAD`. | scenario |
| H-GUARD-06 | Import check: module-level imports identical to `HEAD`; every free name used in the symbol is bound at module level, a builtin, or local. | scenario |
| H-GUARD-07 | AST rules from `spec.forbidden` are enforced on the candidate symbol body. | scenario |
| H-GUARD-08 | The diff is non-empty and not whitespace-only. | scenario |
| H-GUARD-09 | The final patch passes `apply_check` (H-GIT-02). | scenario |
| H-GUARD-10 | Test files (paths with `test`/`tests`/`spec` segments or `_test.go`, `.test.ts`, `.spec.ts`) are reverted unless the statement allows test changes. | scenario |
| H-GUARD-11 | The guard reports every repair it made and every check result as structured `CheckResult(name, ok, detail)`. | unit |
| H-GUARD-12 | Named symbols are exclusive: naming `f()` as the thing to change freezes the rest of its file (text outside it is spliced back). | scenario |
| H-GUARD-13 | Deleting a file is refused unless the statement asks for it; deleting a scoped file under a symbol contract fails. | scenario |
| H-GUARD-15 | "Change only that method" (method not named) also freezes the rest of the file: exactly one method may change, or, with a located target, text outside it is spliced back. | scenario |
| H-GUARD-14 | Statement construct rules apply even without named symbols (to what the patch adds per file); files in languages without a parser are reported as not inspected, never as PASS. | scenario |

## 8. Tools (`quarry.tools`)
| ID | Requirement | Verify |
|---|---|---|
| H-TOOL-01 | Tools are classes registered in a `ToolRegistry`; the registry produces the OpenAI tool schema list and dispatches by name. Unknown tool → error text, not exception. | unit |
| H-TOOL-02 | `read(path, start, end)`: max 400 lines, line-numbered, paths confined to the repo. | unit |
| H-TOOL-03 | `search(pattern, glob)`: count + first 50 hits `path:line: text`, excluding `.git`, `node_modules`, venvs, build dirs. | unit |
| H-TOOL-04 | `edit(path, old, new)`: exact single match; zero or multiple matches return an error with the closest lines; out-of-scope paths are refused with the reason. | unit |
| H-TOOL-05 | `shell(cmd, timeout)`: runs in the repo with a timeout, own process group, output capped to head + tail + error lines. | unit |
| H-TOOL-06 | `scratch(name, content)` writes only under the scratch dir outside the repo and returns the absolute path. | unit |
| H-TOOL-07 | `sql(query, target)`: PostgreSQL through `psql` inside `BEGIN … ROLLBACK` with `statement_timeout`; ClickHouse through its HTTP interface with `readonly=1` unless the query only touches temporary/inline data. Output capped. | unit |
| H-TOOL-08 | `finish(summary)` ends the loop; the shell then runs checks and the guard (the model cannot skip them). | unit |
| H-TOOL-09 | The SQL tool refuses transaction-control statements and psql meta-commands, found by a lexer that understands comments (incl. nested), quoted strings, quoted identifiers and dollar quoting. | scenario |
| H-TOOL-10 | Process output is buffered with a bounded head + tail; memory does not grow with output size. Internal git reads are exact. | scenario |

## 9. Driver loop (`quarry.loop`)
| ID | Requirement | Verify |
|---|---|---|
| H-LOOP-01 | Stops on `finish`, `BudgetExhausted`, phase deadline, or max turns. | unit |
| H-LOOP-02 | Executes all tool calls of one reply in order and returns every result with its call id. | unit |
| H-LOOP-03 | When the transcript exceeds a token budget, old tool results are replaced by one-line summaries; the system prompt and the spec block are never compacted. | unit |
| H-LOOP-04 | Three consecutive empty replies → the loop ends with reason `stalled`. | unit |
| H-LOOP-05 | Tool calls in one reply stop at the phase deadline; skipped calls still get an answer. | scenario |

## 10. Build and lint (`tools/build.py`, `tools/prescreen_lint.py`)
| ID | Requirement | Verify |
|---|---|---|
| H-BUILD-01 | `dist/agent.py` is one file, stdlib-only imports, exports `agent_main`, compiles on Python 3.9 grammar (`ast.parse(feature_version=(3, 9))`). | unit |
| H-BUILD-02 | The build fails on duplicate top-level names across modules, on import cycles, and on intra-package imports other than top-level `from quarry.<module> import …` (single-line or parenthesised). | unit |
| H-BUILD-03 | Knowledge packs and prompts (`src/quarry/packs/*.md`, `src/quarry/prompts/*.md`) are embedded as string constants. | unit |
| H-LINT-01 | `prescreen_lint` fails on grading vocabulary, evaluation-environment words, sample task/repo names, long encoded blobs and decode calls; warns on hard-coded URLs, dynamic execution and scoring words. | unit |
| H-LINT-02 | Originality (upload gate): `tools/originality_check.py` compares the bundle with every public agent in `references/` by distinctive-line overlap and 12-token shingle containment; identical files or ≥ 30% on either measure fail, ≥ 15% warns, and no references means "not run", never a pass. | unit |
| H-LINT-03 | The bundle contains no SQL function-call text that the upload API's web firewall rejects (`COALESCE(…)`, `CAST(…)` with arguments): `prescreen_lint` fails on it. Found 2026-09-30: the first upload of v001 got HTTP 403 from Cloudflare; three pack lines were the trigger. | unit |

## 11. Out of scope for M0 (tracked, not yet specified in detail)
Lab phase (baseline, repro, work proof), evidence ledger T3/T4, critic, second attempt, Go/TS symbol splice (tree-sitter), ClickHouse lab helpers. See `docs/plans/`.
