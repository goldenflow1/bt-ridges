# Quarry — System Design for a Ridges DB Query Engineering Agent

| | |
|---|---|
| **Competition** | Ridges (Bittensor SN62) · Set 28 · *Database Query Engineering* |
| **Deliverable** | One file, `agent.py`, exporting `agent_main(input) -> str` |
| **Doc status** | Draft v3.1 · 2026-09-29 (v3: check against docs, `ridges@d74410d`, sample `verify.py`; v3.1: review `docs/reviews/2026-09-29-architecture-implementation.md`, see §22) |
| **Codename** | Quarry (placeholder) |

---

## 0. TL;DR

The leading agents solve **18–19 of 50** tasks (0.36–0.38) and spend **$0.04–0.09** per task. The most common code family, Enigma and its forks (ranks 15–20), is stuck at **0.32**: five miners changed its settings and none of them improved the score.

Quarry's thesis:

1. **Correct and repeatable first, then cheap.** Matching the leader's score at a much lower cost can earn **~3.7× more** reward than beating the score at a higher cost (12.6 vs 3.4 units, §2), but only a qualifying agent earns anything, and near the bar one more solved task is worth more than any cost saving. Order: reliable mechanics → measured solve rate → cost policy. Target: **≥ 0.40**, then **≤ $0.03 per task** as a measured objective.
2. **Specification first, evidence-gated.** Compile the problem statement into a numbered spec. The agent may not finish until every requirement has evidence behind it: from the live database, from tests, or from a static check.
3. **Use the live database as a lab.** Reproduce the bug on crafted data *before* fixing it. Prove the fix on the same data *after*. For optimization tasks, show identical results with less database work.
4. **Deterministic guard rails in code, judgment in the LLM.** Scope, timeouts, budget, patch validity and the final revert are plain Python, never LLM decisions.
5. **Treat every stack equally.** Build explicit Go, TypeScript and Python packs, plus a ClickHouse pack. The Enigma family is Django-shaped, which is likely where its 68% failure rate lives.
6. **Separate the core from the niche.** The competition may end soon (§14). The harness core is niche-agnostic, and the DB knowledge is a swappable "niche pack".

---

## 1. Requirements

### 1.1 Functional
| ID | Requirement |
|---|---|
| F1 | Accept `{"problem_statement": str}` and return a **non-empty unified git diff** that applies with `git apply` at the repo root. |
| F2 | Solve three task kinds: **authoring** (write a data path), **repair** (fix wrong data), **optimization** (same results, less database work). |
| F3 | Work on real apps in **Python, Go, TypeScript and more**, on **PostgreSQL and ClickHouse**, through an ORM, a query builder, embedded SQL or migrations. |
| F4 | Respect task-stated scope exactly: allowed files and methods, frozen imports, forbidden constructs. |
| F5 | Locate the target code even when the statement doesn't name it. |

### 1.2 Non-functional
| ID | Requirement | Target |
|---|---|---|
| N1 | Validator score (50 tasks, 3-validator consensus) | **≥ 0.40** (stretch 0.44) |
| N2 | Average inference cost per task | **≤ $0.03** (hard cap $0.29) |
| N3 | Wall time per task | p50 ≤ 9 min, p99 < `AGENT_TIMEOUT` − 60 s |
| N4 | Zero "mechanical" losses | 0% empty, unappliable, out-of-scope or timed-out patches |
| N5 | Pre-screening | Pass the first time. No banned vocabulary, no task knowledge, readable code. |
| N6 | Determinism | Temperature 0, stable prompts. The proxy may also set seeds. |

### 1.3 Hard constraints (verified from docs and source)
| Constraint | Source / evidence |
|---|---|
| Entry point: `agent_main({"problem_statement": text})`. The return value must be a non-empty `str`. | `ridges_harbor/ridges_miner_runtime.py` |
| The agent runs with **cwd = task workdir** (`/app` in all samples; the docs say `/repo`). Always use `os.getcwd()`. | `ridges_harbor/agents.py`, sample `task.toml` |
| The workdir is a git repo with a clean HEAD (Ridges runs `git init` + a baseline commit if needed). | `_ensure_git_baseline` |
| The patch is `git apply --check`-ed in the agent's container, then **applied in a separate, pristine verifier container**. Anything not in the diff (including live-database changes) is lost. | `agents.py`, `task.toml: environment_mode="separate"` |
| All LLM calls go through `SANDBOX_PROXY_URL` → `/api/v1/chat/completions` and `/api/v1/embeddings`. There is no other network access. | Agent Contract doc |
| `RIDGES_MAX_COST_USD` = 0.29 hard cap per task. `AGENT_TIMEOUT` = wall seconds (samples: 1800). | Agent Contract doc |
| Standard library plus `miners/baseline-requirements.txt` only (`openai`, `httpx`, `requests`, `pydantic`, `sqlparse`, `tree-sitter`, `tree-sitter-language-pack`, `numpy`, `pandas`, …). | Repo |
| OpenRouter account: logging **off**; **zero-data-retention** models only. | Mining intro doc |
| Pipeline: Screener 1 (20 tasks) → Screener 2 (20) → 3 validators × 50. Per-task credit only if **all 3** pass it. | Scoring doc |
| One upload per hotkey per competition per 12 h. ~$5 burned per upload, plus $10–20 of inference. | Mining intro doc |
| **Banned in prompts and code:** mentioning scoring, hidden tests, the verifier, the sandbox or the evaluation; task, repo or file fingerprints; stored answers; obfuscation. | Pre-screening doc |
| **Per-task result is binary.** `reward.txt` is 1 only if *every* check passes (patch applies, scope, compile, lint, named tests, hidden tests, tree conservation). | sample `tests/verify.py` (`Report.write`) |
| **Whole-tree conservation.** The checker records every path under `/app` (kind, **permission mode**, sha256) except the allowed file(s). Any added, removed, changed or re-moded file fails the task. | sample `verify.py` `source_identity()`, `create_source_manifest.py` |
| **Method-bounded tasks are checked byte-exactly.** Lines before and after the target method must be identical to the original; the method header (name, args, decorators) must be AST-identical. | sample `verify.py` `bounded_method()` |
| **Method body limits (samples):** ≤ 5000 bytes, ≤ 320 AST nodes; banned constructs and names that mirror the statement's wording ("no loops, comprehensions, lambdas, exception handling, context managers", "no database writes", "no raw SQL", "no dynamic code"); no test-data string literals. | sample `verify.py` `bounded_method()` |
| **A timeout publishes nothing.** If the runtime is cancelled, no patch is written; there is no partial rescue. | `agents.py` `run()` |
| **DB access is an ordinary role.** Samples: role `solver` (no superuser, no createdb/createrole), owner of `<app>_dev` and `<app>_test`. Credentials live in the **app's config** (e.g. Django `DATABASES`), not in env vars. | sample `postgres-init.sh`, `configuration.py` |
| **Image permissions:** `/app` is root-owned and read-only except the allowed file (owned by uid 1000 `agent`). The sample `task.toml` runs the agent as root, so this is not guaranteed to stop stray writes. Treat `EACCES` as a scope signal, never work around it. | sample `environment/Dockerfile`, `task.toml` |
| Git baseline excludes `__pycache__/` and `*.pyc`. Untracked files are not in `git diff` unless added, but **tracked** files touched by tools (formatters, test runs) are. | `_ensure_git_baseline` |

### 1.4 Known unknowns
- The exact production `AGENT_TIMEOUT`. Design against the environment variable, never a constant.
- Whether the proxy passes prompt-caching discounts through. Measure it (§9.3).
- The language and engine mix of the hidden set. Assume at least 30–40% non-Python and 20–30% ClickHouse until the data says otherwise.
- Which tools exist in task images (`psql`, `clickhouse-client`, `go`, `node`, `tsc`). Probe at runtime, and always have a fallback. (Samples ship `psql`, `ruff`, `git`, `jq`, `redis-cli`.)
- Whether production runs the agent as root (samples: `user = "root"`) or as `agent` (uid 1000). Design for both.
- Whether the sample checker's limits (5000 bytes / 320 nodes, banned-name lists) are the same on the hidden set. Assume *similar*, but derive every constraint from the **statement text**, never from these lists (§13).

---

## 2. Winning Condition (reward math that drives every design choice)

From the incentive mechanism (per competition):

- Qualify if **score ≥ leader × 1.03**, or if **score ≥ leader and cost ≤ leader × 0.94**.
- Performance units: `ln(1+Δperf)/ln(1.03)`. Cost units: `ln(1−Δcost)/ln(0.94)`, capped at ~16.7. The two add together.
- Multiplied by `1 + sqrt(hours_leader_unbeaten / 6)`, then decays with a 14-day half-life.

Worked scenarios (leader data as of 2026-09-29):

| Scenario | vs "hope" (0.38 @ $0.0437, under review) | vs "thrush" (0.36 @ $0.0914, approved) |
|---|---|---|
| 0.38 @ $0.020 | cost 12.6 → **12.6 units** | perf 1.8 + cost 16.7 (cap) → **18.5** |
| 0.40 @ $0.025 | perf 1.7 + cost 9.0 → **10.8** | perf 3.6 + cost 16.7 → **20.2** |
| 0.40 @ $0.030 | perf 1.7 + cost 6.1 → **7.8** | — |
| 0.42 @ $0.050 | perf 3.4 + cost 0* → **3.4** | — |

\*This assumes a more expensive agent earns no cost credit.

**Design consequence (conditional):** once an agent qualifies with margin, extra cents cost reward quickly because cost units compound. But the trade is not universal: when one more solved task crosses the qualification threshold (score ≥ leader, or ≥ 1.03 × leader), that task outweighs the cost difference. Quarry aims for **~$0.025 average** as a measured objective, introduced as a soft spending policy only after the live baseline (the runtime currently allows up to ~$0.22 per task for the driver).

---

## 3. Competitive Landscape (what we learned)

| Observation | Implication for Quarry |
|---|---|
| The top three score 0.36–0.38 and run 600–970 s. Their code is hidden. | The bar is low in absolute terms: 64% of tasks fail even for the leaders. |
| The Enigma family (ranks 15–20; 96% shared code across 4 forks) is flat at 0.32 regardless of settings. | Tuning settings is a dead end. Structural changes are needed. |
| Enigma's strengths: a rollback-wrapped `sql` tool, a mature retry/timeout harness, a good generic DB playbook, and **$0.020** per task. | Re-implement these ideas independently. Copying is banned and earns nothing. |
| Enigma's gaps: one cheap model for everything; a second attempt only when the first returns *nothing*; code-run checks and scope put-back **off** by default; Django-centric (0 Go-ORM mentions, no `.ts` syntax check). | These are exactly Quarry's investment areas. |
| Validator score distribution for set 28: most agents land between 0.2 and 0.34. | One task = 0.02. Any local improvement must be **≥ 2–3 tasks** to be real signal. |

---

## 4. Design Principles

1. **The diff is the only output.** Anything not in the diff doesn't exist. Schema changes ship as migrations.
2. **Specification before code.** No edits until the spec is compiled and the target is located.
3. **Evidence before submit.** Each requirement ends in PASS, FAIL or an explicit UNVERIFIABLE with a reason.
4. **Code enforces, the LLM proposes.** Scope, budget, clock, patch hygiene and fallbacks are deterministic.
5. **Cheap by default, strong on demand.** A cheap model for the bulk; a strong model for one or two critical calls.
6. **Stack-neutral core, stack packs on detection.** Inject only the language/ORM/engine knowledge that applies.
7. **Never lose a task mechanically.** Always keep a "best-known-good" candidate and a fallback return path.
8. **Write it like a real engineering tool.** It must make sense on your own repo. That's also the pre-screening rule.

---

## 5. High-Level Architecture

```
                         problem_statement
                                │
┌───────────────────────────────▼──────────────────────────────────────────┐
│ CONTROL SHELL  (deterministic)                                           │
│  Clock · Wallet · Phase scheduler · Candidate store · Crash-safe return  │
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                  │
│  │ P1 SPEC      │──►│ P2 PROFILE   │──►│ P3 LOCATE    │                  │
│  │ compiler     │   │ env/stack/DB │   │ symptom→code │                  │
│  │ (regex+LLM)  │   │ (determ.)    │   │ (LLM+tools)  │                  │
│  └──────────────┘   └──────────────┘   └──────┬───────┘                  │
│         TaskSpec        EnvProfile            │ FindingsCard             │
│                                               ▼                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                  │
│  │ P6 CRITIC    │◄──│ P5 PROVE     │◄──│ P4 LAB+BUILD │                  │
│  │ strong model │   │ evidence     │   │ baseline,    │                  │
│  │ 1 call       │   │ ledger       │   │ repro, edit  │                  │
│  └──────┬───────┘   └──────┬───────┘   └──────────────┘                  │
│         │  concrete issue  │ FAIL → back to P4 (bounded)                 │
│         └────────┬─────────┘                                             │
│                  ▼                                                       │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐    │
│  │ P7 GUARD (deterministic)     │───►│ P8 SELECT & RETURN           │    │
│  │ scope revert · junk strip ·  │    │ best candidate by evidence   │    │
│  │ contract check · apply-check │    │ score → git diff string      │    │
│  └──────────────────────────────┘    └──────────────────────────────┘    │
│                                                                          │
│  Knowledge packs (injected): core playbook · PG · CH · Python · Go · TS  │
└──────────────────────────────────────────────────────────────────────────┘
          │ all LLM traffic
          ▼
   SANDBOX_PROXY_URL ──► OpenRouter ──► routed models (§8)
```

**Data flow (artifacts passed between phases):**

`TaskSpec` → `EnvProfile` → `FindingsCard` → `Baseline` → `Candidate(diff, ledger)` → `CriticReport` → `FinalDiff`

Each artifact is a small JSON-able object. Phases talk through artifacts, **not** through one ever-growing transcript. This is the main cost lever (§9).

---

## 6. Component Deep Dive

### 6.1 Control Shell
- **Clock:** `deadline = start + AGENT_TIMEOUT − reserve`, where `reserve = max(60 s, 5%)`. Each phase gets a *soft* and a *hard* slice (§10). At the hard slice, the phase is cut and the shell moves on.
- **Wallet:** before every call, estimate the maximum cost (prompt tokens × input price + `max_tokens` × output price) and refuse calls that could breach the phase's cap. After each call, add the actual `usage` cost. A 402 or budget error from the proxy is treated as `Spent`: stop exploring immediately and go to Guard.
- **Candidate store:** after every *verified* state change, snapshot `git diff` together with its evidence ledger. The best candidate is always ready to return.
- **Crash safety:** `agent_main` is wrapped in `try/finally`. On any exception, return the best candidate. If there is none, return the current tree's diff when it's non-empty and passes the guard. Raise only if truly nothing exists.
- **Git hygiene:** record `HEAD` at start. Use `git stash`/`git checkout` to switch candidates. Never commit. Never touch `.git` config beyond what's needed.

### 6.2 P1 — Spec Compiler (the SDD layer)
Two passes, merged:

1. **Deterministic extraction** (regex + markdown parse):
   - fenced code blocks → `checks[]` (the commands to run);
   - phrases like "Limit/Restrict changes to…", "Keep signature…", "including imports", "use only names the file already imports" → `scope`;
   - bullet lists → candidate `requirements[]`;
   - "Do not …" sentences → `forbidden[]`;
   - engine keywords → `engine_hint`.
2. **One cheap LLM call** (structured JSON output) normalizes it into a `TaskSpec` and classifies `kind`. It also produces an **edge-case table** derived *only* from the statement.

```jsonc
// TaskSpec (abridged)
{
  "kind": "repair | authoring | optimization",
  "goal": "one sentence",
  "scope": {"files": ["netbox/tenancy/models/contacts.py"],
            "symbols": ["ContactGroupManager.annotate_contacts"],
            "freeze_signature": true, "freeze_imports": true, "rest_of_file_frozen": true},
  "requirements": [
    {"id": "R1", "text": "count distinct contacts at any depth", "verify": "sql-scenario"},
    {"id": "R2", "text": "empty groups return integer 0",        "verify": "sql-scenario"},
    {"id": "R3", "text": "one query for any number of groups",   "verify": "query-count"}
  ],
  "forbidden": ["python loops in method", "materialize rows", "change migrations"],
  "checks": ["python netbox/manage.py test tenancy.tests... --keepdb --noinput",
             "ruff check --no-cache netbox/tenancy/models/contacts.py"],
  "edge_cases": ["duplicate membership across levels", "separate trees", "empty group",
                 "filtered/sliced/values querysets"],
  "engine_hint": "postgresql"
}
```

The spec is **pinned at the top of every later prompt** as a checklist. That keeps the prompt prefix stable, which helps caching, and anchors the model.

### 6.3 P2 — Environment Profiler (deterministic, ~0 LLM cost)
| Probe | Method |
|---|---|
| Languages | Marker files: `pyproject.toml`/`setup.py`/`manage.py`, `go.mod`, `package.json`/`tsconfig.json`, `Gemfile`, `mix.exs`, `pom.xml`… |
| ORM / query layer | Dependency manifests plus import grep. Python: Django, SQLAlchemy, Peewee, psycopg/asyncpg, clickhouse-connect/driver. Go: database/sql, sqlx, sqlc (`sqlc.yaml`), GORM, pgx, bun, ent, clickhouse-go. TS: Prisma (`schema.prisma`), TypeORM, Knex, Drizzle, Sequelize, Kysely, MikroORM, @clickhouse/client. |
| Build / type check | Python: `python -m py_compile` + `ruff` if present. Go: `go build ./...` and `go vet` on the touched package. TS: `node_modules/.bin/tsc --noEmit -p .` (never `npx` downloads). |
| Test runner | pytest / `manage.py test` / `go test ./pkg/...` / jest, vitest or mocha (from `package.json` scripts). |
| Database | **App config first** (Django `DATABASES` incl. `TEST.NAME`, SQLAlchemy URLs, `config/*.yml`, `.env` files, Go/TS config), then env vars (`DATABASE_URL`, `PG*`, `CLICKHOUSE_*`), then compose files. Samples keep credentials only in the app config. Probe with `psql`/`clickhouse-client`. If those are missing, fall back to the app's own driver (Python `psycopg`, `clickhouse-connect`, Go/TS one-off scripts) or ClickHouse's HTTP port 8123 via `urllib`. Record the role's privileges (`rolsuper`, extensions present); expect a **non-superuser** role. |
| Writable paths | `os.access(path, W_OK)` on the scope files and their dirs. Read-only everywhere else is a strong scope hint. |
| Tools present | `shutil.which` for psql, clickhouse-client, go, node, tsc, ruff, pytest. |

Output: an `EnvProfile`. That profile selects which **knowledge packs** get injected (§7.3).

### 6.4 P3 — Locator
Goal: a **FindingsCard** (≤ 4k chars) listing the target file(s) and symbol(s), the caller chain, the related model/schema, relevant snippets, and the tables involved.

- **Deterministic pre-ranking:** grep the spec's identifiers (symbols, tables, columns, endpoint paths, error strings). Rank files by hit density and proximity to the DB layer.
- **tree-sitter outline** (allowed package) for Python, Go and TS: function/class spans without reading whole files.
- **LLM loop:** cheap model, ≤ 8 turns, parallel tool calls. It must end with `set_findings(...)`.
- When the spec names the file and symbol, skip most of P3. Just read the symbol, its callers and its model.
- The exploration transcript is **discarded** after P3. Only the FindingsCard continues.

### 6.5 P4 — Lab & Build
**Lab (before editing):**
1. **Schema read:** columns, types, nullability, indexes, constraints for the involved tables. ClickHouse: engine, ORDER BY, partitioning, skip indexes.
2. **Baseline capture** by task kind:
   - *optimization*: the result fingerprint of the target path (row count + stable hash) + **query count** + `EXPLAIN (ANALYZE, BUFFERS)` for PG, or `system.query_log` read_rows/read_bytes for CH;
   - *repair*: **reproduce the bug.** Craft scenario rows in a rolled-back transaction (PG) or inline `values()` / temporary tables (CH), and show the wrong output;
   - *authoring*: build scenario rows covering the spec's edge cases, and write down the expected output **derived from the spec**, before writing code.
3. **Realistic volume for work measurement.** On small tables PostgreSQL picks a sequential scan whatever the indexes, and query-count growth is invisible with 2 rows. For optimization tasks, seed **thousands** of rows shaped like the statement describes (e.g. "many rows share one key"), run `ANALYZE` on the touched tables, then measure — all inside one rolled-back transaction. Prove the **task's stated** performance requirement: a bounded query count (N+1 → constant), fewer buffers/rows read, or index use for a stated predicate. Aggregates over all rows are legitimately O(N); query count, rows examined, buffers and time are different quantities. Where the statement says work must not grow with the selection size, measure at two sizes (N and 4N). Result comparison keeps order and multiplicity when the output is ordered.
4. **Query-count harness per stack** (driver-level; the DB role is not a superuser, so `SET log_statement` is refused and `pg_stat_statements` is usually absent):
   - Django: `connection.execute_wrapper(...)` or `CaptureQueriesContext`;
   - SQLAlchemy: an `after_cursor_execute` event;
   - PG generic: `pg_stat_statements` only if the probe found it;
   - CH: `system.query_log` (filtered by a per-run `log_comment` or query id);
   - Go/TS: a driver-level wrapper in a scratch script.
5. **Plan evidence:** Django `queryset.explain(format="json", analyze=True, buffers=True)` or raw `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. Record the chosen index name and total shared buffers. `EXPLAIN ANALYZE` **executes** the statement (including DELETE/UPDATE), so it always runs inside a rolled-back transaction.
6. **Where lab code runs:** every scratch script lives in `/tmp/quarry/` and loads the app from there (`sys.path` + `DJANGO_SETTINGS_MODULE` + `django.setup()`, or the stack's equivalent), using the **test database** named in the app config. The agent never writes a scratch test module into the repo: one stray file anywhere under the workdir fails the task (§1.3).

**Build:**
- Driver loop (cheap model) with **exact-match edit** (`old` must match exactly once; on failure, return the nearest lines). Parallel read calls are allowed.
- **Scope-aware edit tool:** an edit outside `scope.files`/`scope.symbols` is **refused at the tool level**, with the reason given. The model isn't trusted to comply on its own.
- Scratch scripts are written **outside the repo** (`/tmp/quarry/…`) so they can never leak into the diff.

### 6.6 P5 — Prove (Evidence Ledger)
Tiered and cheapest first. Each tier writes ledger rows `{req_id, status, evidence}`.

| Tier | Check | Cost |
|---|---|---|
| T0 | Syntax / build / type check for touched files (per stack) | seconds, $0 |
| T1 | **Every command in `spec.checks`**, run by code after the *last* edit, with exit codes recorded. These are regression checks that **already pass before any change**, so T1 is a gate (must not break), not proof of the fix. | seconds–minutes, $0 |
| T2 | Contract guard (see below) | $0 |
| T3 | **Differential data proof:** repair = old wrong / new right on the repro scenario; authoring = output matches the spec-derived expectation on edge rows; optimization = result fingerprint identical to baseline | $0 LLM + DB time |
| T4 | Work proof (optimization): the statement's own performance requirement (query count bound, index use, buffers/read_rows), measured at realistic volume | $0 |

**T2 contract guard, in detail** (all deterministic):
1. **Tree conservation:** `git status --porcelain` shows only the allowed file(s); no mode changes (`git diff --summary` has no `mode change`); no new files unless the statement allows them (e.g. a new migration).
2. **Method boundary:** when bounded to one symbol, the file text before and after the symbol span is **byte-identical** to `HEAD`, and the header (name, arguments, decorators, return annotation) is AST-identical.
3. **Imports:** the import block is unchanged, and every free name used in the method is already bound in the module (module globals + builtins + method locals).
4. **Statement-derived AST rules:** the spec compiler maps the statement's own wording to AST checks, for example: "no Python loops / comprehensions / lambdas" → `For`/`While`/`*Comp`/`GeneratorExp`/`Lambda`; "no exception handling / context managers" → `Try`/`Raise`/`With`; "no database writes" → no `.save/.update/.delete/.create/.bulk_create` calls; "no raw SQL" → no `.raw/.execute/.cursor`/`RawSQL` *added* by the patch; "no dynamic code" → no `eval/exec/compile/getattr/setattr/__import__`, no dunder names. Rules come from the statement text only (§13).
5. **Size sanity:** the edited method stays small (warn above ~4 KB or ~300 AST nodes); prefer the smallest correct expression.

A FAIL returns the **specific failing evidence** to the driver. That's bounded to N repair rounds (default 3) and to the phase budget.

**The submit gate** (enforced in code): T0–T2 must pass. Every requirement is either PASS, or UNVERIFIABLE with a stated reason. Otherwise the candidate is stored with a lower evidence score, and the shell decides whether to retry (§6.8).

### 6.7 P6 — Critic (the one strong-model call)
- Input: TaskSpec + FindingsCard + final diff + ledger. **No transcript.** Roughly 6–12k tokens.
- Output (JSON): `verdict ∈ {accept, fix}`, plus up to 3 **concrete** issues, each tied to a requirement ID and a code line.
- Only a concrete issue triggers **one** repair round (cheap driver + the critic's note), followed by a re-prove.
- Skipped when the ledger is all-PASS on T1+T3 *and* the task is "easy" (single symbol, repair kind, small diff). Target: the critic runs on ~50–60% of tasks.

### 6.8 P7/P8 — Guard, Selection, Second Attempt
**Guard (always runs, deterministic):**
1. Revert out-of-scope files (`git checkout -- <path>`). For method-bounded tasks, **splice back** the original bytes outside the symbol span.
2. Restore original file modes (`git diff --summary` must show no `mode change`) and line endings.
3. Delete untracked junk and scratch files, caches, `.orig`/`.rej`, logs, even though untracked files are not in the diff: they can break later checks in this container. Remove test-file changes unless the spec allows them.
4. `git add -N` **only** for new files the statement allows (e.g. a migration), then `git diff --binary`.
5. `git apply --check` against a clean copy (`git stash` → apply → restore).
6. Non-empty. Reject diffs that only touch whitespace.

**Evidence score** for picking between candidates. T1 and T2 are **gates** (a candidate failing either is not eligible unless nothing else exists); the ranking comes from the proofs that distinguish a fix from no change:
`score = 4·[T3 pass] + 2·[T4 pass, optimization only] + 1·[critic accept] − 1·(#UNVERIFIABLE requirements)`

**Second attempt policy** (the key difference from Enigma). Run it when **any** of these is true, *and* the budget has ≥ $0.06 and ≥ 35% of the clock left:
- no valid candidate;
- a T1 or T3 failure remains after the repair rounds;
- the critic still says `fix` after its repair round.

The second attempt uses a **different strategy**: the strong model as driver, *or* an alternative approach the critic suggested. It starts from the same TaskSpec/FindingsCard, so P1–P3 aren't paid for twice. Return the highest evidence score, breaking ties toward the smaller diff.

---

## 7. Prompt Engineering

### 7.1 Prompt stack (order is fixed, for cache friendliness)
```
[system]  Core role + workflow + tool rules            (static, ~1.2k tok)
[system]  Core DB playbook                             (static, ~1.0k tok)
[system]  Packs selected by EnvProfile                 (semi-static, ≤1.5k tok)
[user]    TaskSpec checklist + FindingsCard            (per task, stable within task)
[...]     Rolling transcript (append-only, compacted)
```

### 7.2 Style rules
- Frame the task as real engineering: *"The change must be correct for every state of the data the requirement describes, not only the rows present now."*
- **Never** use the words or ideas: hidden tests, grader, verifier, score, benchmark, evaluation, sandbox, harness, "you are being tested". Enforce this with a **pre-screen lint** in the build (§12).
- No repository, task or file names from the samples. No NetBox/MPTT specifics. Examples are **synthetic** (`orders`/`customers`).
- Language- and engine-specific guidance is added **after detection**, never hard-assumed.

### 7.3 Knowledge packs (generic niche expertise, which is allowed and rewarded)
**Core (all tasks):** join fan-out changing grain (aggregate at the native grain first, or use EXISTS); `COUNT(col)` vs `COUNT(*)`; `COUNT DISTINCT` across levels; LEFT JOIN + WHERE silently becoming an inner join; `NOT IN` with NULLs; empty groups → `COALESCE(...,0)`; ties → a total order with a unique tie-breaker; "latest per group" (window/`DISTINCT ON`/`LATERAL`); pagination order stability; integer division; time zones and interval boundaries (half-open ranges); laziness/composability of query objects; N+1 → set-based or batched loading.

**PostgreSQL pack:** `DISTINCT ON` needs a matching leading `ORDER BY`; NULL ordering defaults; the default window frame with ties (`last_value` pitfall); composite index column order; partial-index predicates must match the query predicate; expression indexes; `INCLUDE`; `CREATE INDEX CONCURRENTLY` can't run inside a transaction (e.g. a Django migration needs `atomic = False`); operator classes (`text_pattern_ops`, trigram); `EXPLAIN (ANALYZE, BUFFERS)` reading.

**ClickHouse pack:** `ReplacingMergeTree` needs `FINAL` or `argMax` dedup at the right stage; JOINs fill **default values, not NULL**, unless `join_use_nulls=1`; `uniq` is **approximate** (use `uniqExact` for exact counts); `LIMIT n BY`; ORDER BY key / primary index and skip-index applicability; `PREWHERE`; `Nullable` semantics; `toStartOfInterval`/time zone arguments; aggregate-function combinators (`-If`, `-State`/`-Merge`); `system.query_log` for work measurement.

**Python pack:**
- Django: `Subquery`/`OuterRef`, `Coalesce`, and never hard-coding compiler aliases in `RawSQL`; `values()` + `annotate` grouping; `select_related`/`prefetch_related`; migrations.
- SQLAlchemy 2.x: `select()`, `joinedload`/`selectinload`, `func.count().filter()`, `scalar_subquery()`.

**Go pack:** `database/sql` scanning NULLs (`sql.NullX`); sqlx; **sqlc** (generated code: edit the `.sql` *and* keep the generated Go consistent if there's no generator binary); GORM `Preload`/`Joins`, `Count` pitfalls; pgx batch; `go build`/`go vet` as a check; context timeouts.

**TypeScript pack:** Prisma (`include`/`select`, `groupBy`, `_count`, `$queryRaw` tagged templates; the client may not regenerate offline, so avoid schema changes unless required); TypeORM QueryBuilder (`leftJoinAndSelect` fan-out, `getRawMany` vs `getMany`); Knex/Kysely/Drizzle; `tsc --noEmit` as the check.

Each pack ends with a **"verify with"** line naming the pack-specific build/test/query-count method.

---

## 8. Model Strategy

### 8.1 Roles
| Role | Calls/task | Model class | Settings |
|---|---|---|---|
| Spec compiler | 1 | cheap, strong at structured output | temp 0, JSON mode, `max_tokens` ~1.5k |
| Locator / Driver | 15–40 | cheap, **good at tool calling**, long context | temp 0, low/no reasoning effort |
| Critic | 0–1 | **strong** reasoning model | temp 0, medium/high reasoning effort, ~2k output |
| Second-attempt driver | 0–25 (rare) | mid/strong | temp 0 |
| Fallback | on provider errors | a different vendor of a similar class | same |

### 8.2 Candidate models (per 1M tokens in/out; **verified on OpenRouter 2026-09-29: all exist, support tools, have ZDR endpoints**)
| Model id (as seen) | $ in / out | Candidate role |
|---|---|---|
| `openai/gpt-5.6-luna` / `~openai/gpt-luna-latest` | 0.20 / 1.20 (cache read 0.02) | driver (the Enigma family uses it) |
| `xiaomi/mimo-v2.5` | 0.14 / 0.28 | spec / locator (very cheap) |
| `tencent/hy3` | 0.132 / 0.528 | spec / locator |
| `minimax/minimax-m2.5` | 0.27 / 1.08 | driver candidate |
| `google/gemini-3.7-flash` | 0.75 / 3.75 | driver / critic-lite |
| `deepseek/deepseek-v4-pro-0813` | 0.48 / 4.20 | critic / second attempt |
| `openai/gpt-5.6-terra` | 2.00 / 12.00 | critic, only if the bench proves it's worth it |

**Selection rule:** pick per role by **local bench solve rate per dollar** (§12). Don't pick by reputation. Re-check monthly.

### 8.3 Call hygiene
- Use the `openai` client pointed at `f"{SANDBOX_PROXY_URL}/api/v1"` with the injected key.
- Retry with jittered backoff on 429/5xx/timeouts. **Never retry on budget errors.** Switch to the fallback model after 2 consecutive failures.
- Per-call timeout ≤ 25% of the remaining phase time.
- Parse tool calls defensively: normalize IDs and handle empty or blank replies (count them and change strategy after 3).

---

## 9. Cost Optimization

### 9.1 Budget plan (target average ≈ $0.025)
| Phase | Soft cap | Hard cap | Notes |
|---|---|---|---|
| P1 Spec | $0.002 | $0.005 | single call |
| P3 Locate | $0.005 | $0.015 | skipped mostly when the scope is named |
| P4+P5 Build/Prove | $0.010 | $0.060 | most of the spend |
| P6 Critic | $0.005 | $0.015 | conditional |
| Second attempt | $0 | $0.080 | conditional, rare |
| Reserve | — | $0.020 | guard, selection, emergencies |

**Feasibility check.** At $0.20 / $1.20 per 1M tokens, 20 driver calls × ~12k input tokens ≈ 240k input tokens ≈ **$0.05** before output, without caching. So ≤ $0.03 requires *either* the proxy passing through prompt-cache discounts, *or* ≤ ~12 driver calls with compacted context, *or* a cheaper driver. **Measure `usage.prompt_tokens_details.cached_tokens` through the proxy on the first local run (M0), before tuning anything else.** If caching is not passed through, lower the target to ~$0.04 and lean harder on deterministic phases.

### 9.2 Techniques (by expected savings)
1. **Artifact hand-off instead of a growing transcript:** each phase starts from compact cards, not history.
2. **Deterministic work first:** profiler, grep ranking, tree-sitter outlines and checks run in code, not through LLM turns.
3. **Tool-output shaping:** head+tail+error-line extraction for logs; `read` by line range with a cap; search returns counts plus top hits.
4. **Parallel tool calls:** fewer round trips mean fewer resent prompts.
5. **Stable prefix for prompt caching:** static system blocks first, append-only transcript. Measure `cached_tokens` in `usage`.
6. **Transcript compaction:** past N turns or X tokens, replace the old tool outputs with one-line summaries.
7. **Conditional critic and second attempt:** they run only when the evidence says so.
8. **Early stop:** all ledger rows PASS → guard → return. No polishing.

### 9.3 Telemetry
Log per call: role, model, prompt/cached/completion tokens, cost, latency. Log per phase: spend and time. This is used **locally only** for tuning. In production, keep logs compact and never print secrets.

---

## 10. Time Management
- `T = AGENT_TIMEOUT` (fall back to 1500 s if missing). Reserve `max(60 s, 0.05T)` for guard and return.
- Phase slices (share of T): P1 3% · P2 4% · P3 12% · P4+P5 45% · P6 8% · second attempt 20% (conditional) · reserve.
- Long commands (test suites, builds) run **in the background** with polling. The driver keeps reading while they run.
- Any single command has a timeout of `min(300 s, 25% of remaining)`. A hung DB query means changing the query shape, not waiting longer. PG lab sessions set `statement_timeout`.
- A cancelled run publishes **no patch** (§1.3), so the reserve is not optional. Before returning, kill every background process group the agent started (`start_new_session=True` + `os.killpg`), so no child holds the run open.

---

## 11. Failure Modes & Mitigations

| Failure mode | Effect | Mitigation |
|---|---|---|
| Empty or invalid diff | 0 | Candidate store + guard apply-check + fallback return |
| Out-of-scope edit or changed imports | 0 | Tool-level scope refusal + guard splice-back + T2 |
| Timeout mid-edit | 0 | Clock slices, background commands, reserve, best-candidate return |
| Budget exhaustion | 0 | Wallet pre-checks, `Spent` → guard immediately |
| Named checks not run after the last edit | likely 0 | T1 run **by code** after the final edit |
| Right on the sample rows, wrong grain/ties | 0 | Repro-first + spec edge table + T3 differential scenarios |
| Optimization changes results | 0 | Result fingerprint identical to baseline (T3) |
| "Faster" but not measurably | 0 | Query-count / EXPLAIN / read_rows evidence (T4) |
| DB tool missing in image | lost proof | Driver-level fallback via the app's own client or HTTP |
| Stack unfamiliar (Go/TS) | 0 | Language packs + stack-specific build checks |
| Schema change applied only to the live DB | 0 | Rule: schema changes ship as migrations; the lab DB is read-only (rolled back) |
| Scratch files leak into the diff | 0 or scope fail | Scratch dir outside the repo + guard junk strip |
| File mode changed (e.g. an editor rewrote the file as 0755) | 0 (tree conservation) | Guard restores modes; T2 checks `git diff --summary` |
| Byte drift outside the bounded method (reformatting, trailing newline, import re-order) | 0 | Splice-back of original bytes; never run formatters on the whole file |
| Named tests pass but the fix is wrong | 0 | T1 is a gate only; T3 must show old-wrong / new-right |
| Optimization "proved" on tiny tables | 0 | Seed thousands of rows + `ANALYZE`; prove the stated requirement (§6.5) |
| Lab relies on superuser features (`log_statement`, `pg_stat_statements`) | lost proof | Driver-level query capture |
| Timeout with a good candidate in memory | 0 (nothing published) | Reserve + return best candidate; kill child process groups |
| Provider outage or rate limits | slow or 0 | Backoff + fallback model |
| Pre-screen rejection | $5 + 12 h lost | Pre-screen lint, readable code, no banned vocabulary |

---

## 12. Development Workflow (evaluation-driven)

### 12.1 Repo layout (develop as modules, ship as one file)
```
quarry/
  src/quarry/  shell.py spec.py profile.py locate.py lab.py build.py prove.py
               critic.py guard.py llm.py tools.py packs/*.md prompts/*.md
  build.py            # bundles src + prompt text into dist/agent.py (single file)
  prescreen_lint.py   # banned vocabulary, task/repo names, obfuscation, network calls
  bench/
    tasks/            # Harbor-format practice tasks (task.toml, instruction.md, tests/, solution/)
    run_bench.py      # loops `ridges miner run-local`, N repeats, writes results.csv
    taxonomy.py       # classifies failures from logs (mechanical/locate/semantic/perf/scope)
```

### 12.2 Practice set (6 public samples are not enough)
- **Public:** the 6 `ridges-bench/db-engineering` tasks (NetBox, PG, Django).
- **Home-made:** 15–25 tasks in the same Harbor format across **other stacks**: Go + PG (raw SQL/sqlx/sqlc/GORM), TS + PG (Prisma/TypeORM/Knex), Python + SQLAlchemy, and at least 5 **ClickHouse** tasks. Recipe: take an open-source app, inject a realistic DB bug or an N+1/missing index, write a hidden verifier with *different* data, and write the statement in the same style.
- **Split:** a dev set (tune on it) and a **held-out set** (touched only before a submission) to avoid overfitting your own prompts.
- The agent must contain **no** knowledge of these tasks. They're for measurement only.

### 12.3 Measurement protocol
- Run every task **3×** because of LLM variance. Report the mean solve rate, the per-task pass fraction, $/task and p50/p99 time.
- Keep/revert follows `docs/process/engineering-loop.md` §5a (superseded the earlier "≥ 2 tasks per 25" rule, which was too coarse for a small practice set).
- Keep a failure taxonomy per run and fix the largest bucket first.

### 12.4 Submission gate
Submit only when **all** of these hold:
1. Held-out solve rate ≥ the leader-equivalent target, based on your calibration between local and validator scores.
2. $/task ≤ $0.03.
3. 0 mechanical failures across all runs.
4. `prescreen_lint` is clean.

Each submission costs about $15–25 and a 12-hour slot, so plan **3–5 submissions total**.

---

## 13. Compliance by Design (pre-screening)
- **Allowed and encouraged:** niche expertise (DB/ORM/engine knowledge), self-verification against the live DB, running the repo's own tests, running the statement's commands.
- **Forbidden:** stored patches or answers; keyword→fix tables; recognizing tasks, repos or files; prompts that make the model recall benchmark answers; describing how grading works; obfuscated or encoded payloads; network fetches; returning a patch the run didn't produce; submitting someone else's code (Enigma forks included).
- `prescreen_lint.py` fails the build on: banned words (`hidden test`, `verifier`, `grader`, `benchmark`, `score`, `sandbox`, `harbor`, `evaluation`…), any sample repo or task name, base64 blobs, `exec`/`eval` of built strings, and URLs other than the proxy.
- Keep the file readable: plain modules concatenated, comments kept, no minification. Code the reviewer can't read gets held for human review.

---

## 14. Roadmap

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 Harness** | Shell (clock, wallet, candidates), LLM client, tools, guard, bundler, lint | 6/6 samples produce a valid in-scope diff; 0 crashes |
| **M1 Spec + Profile** | Spec compiler, profiler, packs framework | Spec correct on all practice statements (manual audit) |
| **M2 Lab + Prove** | Baseline capture, repro-first, T0–T4, ledger, submit gate | Solve rate up on dev set; optimization tasks show T4 evidence |
| **M3 Critic + Second attempt** | Strong-model critic, evidence-scored selection | ≥ +2 tasks on held-out at ≤ $0.03 |
| **M4 Stack packs** | Go, TS, ClickHouse packs + stack-specific checks | Non-Python practice tasks within 10 points of Python ones |
| **M5 Cost tune** | Model routing by bench, caching, compaction | ≤ $0.025 average without score loss |
| **Submit #1** | — | Gate in §12.4 |

**Timing risk:** competitions run 1–5 weeks. Set 28 opened 2026-09-09, so it may close before M5. Mitigation: build M0–M2 as a **niche-agnostic core**. Only the packs and the spec's `kind` taxonomy are DB-specific, so the same harness can enter the next competition (Linting, Test Generation, or a new niche) with a new pack.

---

## 15. Key Trade-offs (decision log)

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Phase artifacts vs. single long agent loop | Artifacts | One loop (Enigma-style) | Cheaper tokens, stable cache prefix, easier to debug; costs more code |
| Cheap driver + one strong critic | Yes | Strong model everywhere | Reward math (§2) penalizes cost heavily |
| Second attempt on low evidence, not just empty output | Yes | Only on empty output (Enigma) | Wrong-but-applicable patches are the silent killer |
| Enforce scope in tools *and* guard | Both | Prompt-only | The LLM will occasionally drift; a scope miss is an automatic 0 |
| Repro-first for repair tasks | Yes | Fix-then-test | Proves the fix addresses the real symptom; cheap on a live DB |
| Best-of-N sampling | No (N≤2, conditional) | N=3–5 | Too expensive for the cost-driven reward |
| Build our own loop vs. frameworks | Own loop (~1–2k lines) | LangGraph etc. | Not in the allowed packages; single-file requirement |
| Multi-file dev, single-file ship | Bundler | Hand-edit one big file | Maintainability; matches how top miners work |

---

## 16. Open Questions / Revisit Later
1. The real `AGENT_TIMEOUT` in production. Retune the phase slices after the first validator run (runtime is visible on the dashboard).
2. Does the proxy honor provider prompt caching? If not, compaction matters even more.
3. The calibration factor between local bench and validator score. Establish it after submission #1.
4. Whether a strong model as *driver* on hard tasks (instead of only as critic) beats the cost penalty. Decide from bench data.
5. When multi-file agents become supported (the docs say it's coming), drop the bundler.
6. Watch the leaderboard: if "hope" is approved, the target becomes ≥ 0.38 @ ≤ $0.041 (cost route) or ≥ 0.40 (performance route).
7. The cost route needs score ≥ leader. With ±1–2 tasks of validator noise, a local "equal score" is a coin flip; aim for leader + 1 task to make the cost route reliable.
8. Does production run the agent as root or as uid 1000? Validator logs are hidden from miners, so this can't be observed; keep designing for both.

---

## 17. Project Structure

Develop as normal modules; ship one bundled file. Keep study material, measurement and shipped code strictly apart.

```
quarry/
├── README.md               what it is, layout, tools, machine setup
├── CLAUDE.md               working rules for AI assistants and reviewers (§17.2)
├── docs/
│   ├── design/             this document (source of truth for architecture)
│   ├── decisions/          ADRs: one file per decision, never edited after acceptance (§21.2)
│   ├── process/            improvement loop, review checklist (§18, §21.4)
│   ├── experiments/        EXPERIMENTS.md log + one note per experiment (§21.1)
│   └── research/           rules digest, competitor analysis, leaderboard snapshots
├── references/             READ-ONLY study material, never shipped (§19)
│   ├── platform/           Ridges docs snapshot + ridges repo commit pin
│   └── miners/set-NN/      public agent.py files from other miners + meta.json + INDEX.md
├── src/quarry/             our agent as normal Python modules (§17.1)
│   ├── packs/              knowledge packs: core, postgres, clickhouse, python, go, typescript
│   └── prompts/            prompt text per role
├── bench/
│   ├── tasks/public/       the 6 ridges-bench db-engineering samples
│   ├── tasks/dev/          our practice tasks we tune on
│   ├── tasks/heldout/      practice tasks we only run at a submission gate
│   └── runs/               local run output (git-ignored)
├── tools/                  fetch, snapshot, lint, originality, build, bench scripts (§20)
├── dist/                   bundled single-file agent.py (git-ignored)
└── submissions/vNNN/       exactly what we uploaded + manifest + results (§21.3)
```

`.gitignore`: `dist/`, `bench/runs/`, `__pycache__/`, `*.pyc`, `.venv/`, `.env*`, `*.log`.

### 17.1 Source modules (map to §5–§6)
| Module | Phase | Role |
|---|---|---|
| `shell.py` | Control shell | clock, wallet, candidate store, crash-safe return |
| `llm.py` | — | proxy client, retries, cost accounting, model routing |
| `tools.py` | — | LLM-facing tools (Appendix A) |
| `spec.py` | P1 | problem statement → TaskSpec |
| `profile.py` | P2 | repo → EnvProfile |
| `locate.py` | P3 | symptom → FindingsCard |
| `lab.py` | P4 | schema read, baseline, repro scenarios, query counting |
| `build.py` | P4 | driver loop and edits |
| `prove.py` | P5 | evidence tiers T0–T4, ledger, submit gate |
| `critic.py` | P6 | one strong-model review |
| `guard.py` | P7 | scope splice-back, junk strip, apply check |
| `agent.py` | P8 | `agent_main`, selection, second attempt |
| `packs/*.md`, `prompts/*.md` | — | knowledge and prompt text, bundled as string constants |

`tools/build.py` concatenates the modules (dependency order) and embeds pack and prompt text into `dist/agent.py`. The bundle stays readable: comments kept, no minification, no encoding.

### 17.2 Working rules (`CLAUDE.md`)
- Never copy code, prompts or constants from `references/` into `src/`. Learn the idea, write it yourself, and cite the reference in the ADR or experiment note, never in `src/`.
- Nothing in `src/` mentions grading ("hidden tests", "verifier", "grader", "benchmark", "evaluation", "scored", "harbor"). The only allowed sandbox token is the env var `SANDBOX_PROXY_URL`.
- Nothing in `src/` names a sample task, repo, file or dataset (NetBox, MPTT, ridges-bench task names). Prompt examples use synthetic schemas (`orders`, `customers`).
- Network only through `SANDBOX_PROXY_URL`.
- Before any upload: `tools/prescreen_lint.sh dist/agent.py` and `tools/originality_check.sh dist/agent.py` both pass.
- Architecture change → ADR. Behaviour change → experiment entry with before/after numbers.
- A result counts only under the keep/revert rule in `docs/process/engineering-loop.md` §5a.
- Held-out tasks are never used for tuning.

---

## 18. Continuous Improvement Loop

Improving without limit only works if every change is measured and the measuring stick keeps getting better. There are two loops: a fast inner loop on your machine, and a slow outer loop against the real validators.

```
            ┌────────────────────── OUTER LOOP (every 12 h+, costs ~$20) ──────────────────────┐
            │                                                                                   │
  OBSERVE ──► HYPOTHESIZE ──► BUILD ──► MEASURE ──► GATE ──► SUBMIT ──► LEARN ──► GROW BENCH ───┘
     ▲             │            ▲          │                                          │
     │             │            └──────────┘  INNER LOOP (minutes–hours, ~$0.02/task) │
     │             ▼                                                                   │
  leaderboard   EXPERIMENTS.md                                      new failure types become new tasks
  snapshots,    (one row per idea)
  new public
  agents
```

### 18.1 Observe
Refresh at least daily while a competition runs:
- **Leaderboard snapshot** (`tools/snapshot_leaderboard.py --set-id 28`). The leader's score and cost set your target (§2).
- **New public agents** (`tools/fetch_references.py --set-id 28 --want 15`). When a family publishes a new version, diff it against the previous one. A competitor's changelog shows which ideas they're betting on.
- **Your own failure taxonomy** from the last bench run.
- **Rule changes** (Ridges docs, Discord). Update `references/platform/` when they change.

### 18.2 Hypothesize
Write the idea down before building it, as one row in `EXPERIMENTS.md`. For example: *"If the guard splices back text outside the allowed method, scope failures on dev drop from 3 to 0 with no cost change."* Name the failure bucket, the expected gain and the expected cost. Attack the largest bucket first.

### 18.3 Build
One idea per branch (`exp/E017-scope-splice`). An architecture change gets an ADR. An idea learned from a reference is cited in the experiment note.

### 18.4 Measure (inner loop)
Run dev 3 times (`tools/run_bench.py --set dev --repeats 3`). Record solve rate (mean and per-task pass fraction), $/task, p50/p99 time and failure buckets. Keep the change only if it clears the rule in `docs/process/engineering-loop.md` §5a (`tools/bench_summary.py compare`). Otherwise revert it and log the negative result. A negative result is data, not waste.

### 18.5 Gate
1. Held-out, 3 repeats: at least the target solve rate.
2. $/task ≤ target (≤ $0.03 today).
3. Zero mechanical failures.
4. `prescreen_lint` passes.
5. `originality_check` passes.

### 18.6 Submit
Copy `dist/agent.py` to `submissions/vNNN/agent.py`, fill in `manifest.json`, upload, and note the payment quote ID, block hash and extrinsic index in case the upload drops.

### 18.7 Learn
When the validator result appears, fill in the manifest and the **calibration table** (local held-out vs validator score). After 2–3 submissions you'll know how much the bench over- or under-predicts, and the gate becomes accurate.

### 18.8 Grow the bench
- Every new failure type seen on dev becomes 1–2 new tasks that exercise it on a *different* stack or schema.
- Rotate: move some dev tasks to held-out and add fresh held-out tasks, so held-out never becomes familiar.
- Keep the mix close to the competition: at least 30–40% non-Python and 20–30% ClickHouse.

### 18.9 Cadence
| When | Do |
|---|---|
| Daily | Snapshot the leaderboard, fetch new public agents, 1–2 inner-loop experiments |
| Every 12 h at most | One submission, only if the gate passes |
| Weekly | Review EXPERIMENTS.md: close dead ideas, re-rank the backlog, grow held-out |
| On rule change | Update `references/platform/`, update lint rules, ADR if the design is affected |
| On competition change | Keep the `src/quarry/` core; write a new niche pack; build a new bench |

### 18.10 Anti-patterns
- Tuning on held-out tasks. It stops being held-out.
- Keeping a change because one run looked good. One task = 0.02; noise is ±1–2 tasks.
- Copying a competitor's settings. Five miners did exactly that with the Enigma code and all stayed at 0.32.
- Spending more per task for a small score gain. Check the reward math first.

### 18.11 Initial experiment backlog
| ID | Hypothesis (failure bucket → expected effect) | Origin |
|---|---|---|
| E001 | Harness M0: every sample ends in a valid in-scope diff → 0 mechanical failures | §6.1, §6.8 |
| E002 | Code runs the statement's checks after the final edit → fewer "forgot to re-check" failures | Enigma leaves this to the LLM (`REF set-28/enigma485_v7_801d9e54/agent.py:241`) |
| E003 | Guard splices back text outside the allowed method → 0 scope failures | Enigma has it off (`agent.py:5621`) |
| E004 | Repro-first on repair tasks → fewer wrong-grain fixes | §6.5 |
| E005 | Second attempt on weak evidence, not only on empty output → fewer wrong-but-applicable patches | Enigma (`agent.py:8052`) |
| E006 | Go and TypeScript packs + build checks → non-Python dev tasks within 10 points of Python | §7.3 |
| E007 | Phase artifacts instead of a growing transcript → −30% tokens at an equal score | §9.2 |
| E008 | Strong critic only when the ledger has gaps → +2 tasks at ≤ +$0.004/task | §6.7 |

---

## 19. Reference Library (other miners' public code)

Reviewers and contributors should be able to check a claim against real code instead of memory. Quarry keeps a read-only library of other miners' public agents.

### 19.1 Where the code comes from
Ridges serves finished agents' code at `GET https://agent-upload.ridges.ai/retrieval/agent-code?agent_id=<uuid>`. From `api/endpoints/retrieval.py`, it returns **403** when:
- the agent is still in pre-screening, screening or evaluation;
- the agent was manually rejected;
- its score is at or above the competition's **top-agent cutoff** ("Agent code is hidden for top agents").

It also rate-limits (HTTP 429 after a few quick requests), so fetch with ~15 s between calls.

### 19.2 What's visible today (set 28, fetched 2026-09-29)
| Ranks | Score | Visibility |
|---|---|---|
| 1–14 | 0.34–0.38 | **hidden** (403): the cutoff currently sits at ≥ 0.34 |
| 15+ | ≤ 0.32 | public |

So the "top 5–10 public" agents are ranks 15–24: Enigma485, please, Supertop, CanCanCan, Emerge victory, DuoTao, Haha, venus, and so on. They teach harness mechanics well, but they don't show what the leaders do. Re-fetch as leaders are overtaken and drop below the cutoff. **Ended competitions** (set 26 Infinite SWE, 24 SWE-Bench, 23 SWE + Poly) may expose their former leaders' code. Fetch those too for general harness ideas.

### 19.3 Layout
```
references/
├── README.md
├── platform/
│   ├── README.md                   pins: docs snapshot date, ridges repo commit, sample repo, API endpoints
│   └── docs-2026-09-29/*.md        raw docs.ridges.ai pages (from llms.txt)
└── miners/
    └── set-28/
        ├── INDEX.md                rank, agent, score, cost, runtime, status, code link or "hidden", duplicate note
        ├── index.json              machine-readable, including hidden agents
        └── enigma485_v7_801d9e54/
            ├── agent.py            exact file Ridges serves (never edited)
            └── meta.json           set, agent_id, name, version, rank_at_fetch, score, cost_usd, runtime_sec,
                                    status, miner_hotkey, created_at, fetched_at, visibility, sha256, duplicate_of
```

Folder name: `<lowercased-name>_v<version>_<first 8 chars of agent id>`. It stays stable even when the rank changes.

### 19.4 Rules
1. Never copy code, prompts or constants from `references/` into `src/`. Ridges bans copying, identical uploads are rejected automatically, and a lightly edited copy can't beat the leader by 3% anyway.
2. Learn the idea, write it yourself, cite it: `REF set-28/<folder>/agent.py:<line> — <idea>`, in ADRs and experiment notes only.
3. `tools/originality_check.sh` compares `dist/agent.py` against every reference before upload.
4. Don't edit reference files; re-run the fetch.

### 19.5 How to study a family
1. Group by `sha256` and by shared-line percentage (§20.4). Forks of one base share 90%+ of their code.
2. For each fork, diff its constants and switches against the base (`grep -E '^[A-Z_]+ *= *(read_env_flag|[0-9."(]|os.getenv)'` then `diff`).
3. Diff the prompts at sentence level (split on `. ` and `\n`).
4. Put what each fork changed next to its score and cost. Changes that raise cost without raising the score are anti-lessons.
5. Record conclusions in `docs/research/competitor-analysis.md` (Appendix E).

---

## 20. Tooling

| Script | Needs | Purpose |
|---|---|---|
| `tools/fetch_references.py --set-id 28 --want 10` | Python 3 (stdlib) | Walk the leaderboard in rank order, save visible agents, record hidden ones, write `INDEX.md` |
| `tools/snapshot_leaderboard.py --set-id 28` | Python 3 (stdlib) | Save a dated leaderboard + competition state (`docs/research/leaderboard/<date>_set-28.{json,md}`) |
| `tools/prescreen_lint.sh [file]` | bash | Block what pre-screening rejects (§20.3) |
| `tools/originality_check.sh [file]` | bash | Measure overlap with every reference agent (§20.4) |
| `tools/build.py` *(M0)* | Python 3.12 | Bundle `src/quarry` into `dist/agent.py` |
| `tools/run_bench.py` *(M0)* | Python, Docker, ridges CLI | Run `ridges miner run-local` over a task set N times → `results.csv` |
| `tools/taxonomy.py` *(M0)* | Python | Classify failures from run logs: mechanical / locate / semantic / perf / scope |

### 20.1 Fetch algorithm (`fetch_references.py`)
1. `GET /evaluation-sets/<id>/leaderboard` (entries are already in rank order).
2. For each entry with `status == "finished"`, until `Want` saved or `MaxProbe` probed: skip if already saved. Otherwise wait `DelaySec`, then `GET /retrieval/agent-code?agent_id=…`.
3. On 429, 5xx or a network error: back off 30 s × attempt, up to 4 attempts. On 403: record `visibility = hidden-http-403` in `index.json` and continue.
4. Save `agent.py` exactly as served, and compute sha256. If it matches another saved file, set `duplicate_of`. Write `meta.json`.
5. Rewrite `index.json` and `INDEX.md`.

### 20.2 Snapshot (`snapshot_leaderboard.py`)
Saves `/competitions` (state, accepting, emission weight) plus the top N leaderboard rows (rank, name, version, agent_id, score, cost, runtime, status, approved_at, initial reward) as JSON, and a Markdown table with the current approved leader on top. One file per run, timestamped, so trends are visible over time.

### 20.3 Pre-screen lint (`prescreen_lint.sh`)
Validated against Enigma485, which passed real pre-screening: 0 FAIL, 2 WARN. So the rules aren't stricter than Ridges.

```bash
#!/usr/bin/env bash
# Usage: tools/prescreen_lint.sh [dist/agent.py]   Exit 1 on any FAIL.
set -uo pipefail
file="${1:-dist/agent.py}"; [ -f "$file" ] || { echo "no such file: $file" >&2; exit 2; }
fails=0; warns=0
report() { local level="$1" label="$2" pattern="$3" hits
  hits=$(grep -n -i -E "$pattern" "$file" | grep -v -E 'SANDBOX_PROXY_URL' || true)
  if [ -n "$hits" ]; then echo "[$level] $label"; echo "$hits" | head -8 | cut -c1-160 | sed 's/^/    /'
    [ "$level" = FAIL ] && fails=$((fails + 1)) || warns=$((warns + 1)); fi; }
report FAIL "grading vocabulary"        'hidden[ _-]?tests?|verifier|grader|graded|being (tested|evaluated|scored)|benchmark'
report FAIL "evaluation environment"    '\bharbor\b|sandbox|test harness|evaluation (set|environment|run)'
report FAIL "sample task or repo names" 'netbox|mptt|ridges-bench|swe-?bench|polyglot|contact[_-]group|vlangroup|cached[_-]value[_-]index|prefix[_-]hierarchy'
report FAIL "long encoded blob"         '[A-Za-z0-9+/=]{200,}'
report FAIL "base64/zlib decode"        'b64decode|base64\.|zlib\.decompress|codecs\.decode'
report WARN "hard-coded URL"            'https?://'
report WARN "dynamic code execution"    '\bexec\(|\beval\(|__import__\('
report WARN "scoring words"             '\bscor(e|es|ed|ing)\b'
report WARN "task identifiers"          'task[_ -]?id|instance[_ -]?id|problem[_ -]?name'
echo; echo "prescreen_lint: $fails fail(s), $warns warning(s) in $file"; [ "$fails" -eq 0 ]
```

### 20.4 Originality check (`originality_check.sh`)
Method: normalise both files (drop CR, trim, drop blank and comment lines, drop lines shorter than 30 chars, because every agent has `import os`), then measure what share of the candidate's distinctive lines also appear in each reference. Fail if any reference is byte-identical or shares ≥ 30%. Warn at ≥ 15%.

```bash
#!/usr/bin/env bash
# Usage: tools/originality_check.sh [dist/agent.py]
set -uo pipefail
file="${1:-dist/agent.py}"; root="$(cd "$(dirname "$0")/.." && pwd)"
WARN_PCT="${WARN_PCT:-15}"; FAIL_PCT="${FAIL_PCT:-30}"; MIN_LEN="${MIN_LEN:-30}"
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 2; }
normalise() { tr -d '\r' < "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
  | grep -v -E '^(#|$)' | awk -v n="$MIN_LEN" 'length($0) >= n' | sort -u; }
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
normalise "$file" > "$tmp/candidate"; total=$(wc -l < "$tmp/candidate")
[ "$total" -gt 0 ] || { echo "candidate has no distinctive lines"; exit 2; }
cand_hash=$(tr -d '\r' < "$file" | sha256sum | cut -c1-64); status=0
printf "%-60s %8s %8s\n" "reference" "shared" "percent"
while IFS= read -r ref; do
  rel="${ref#$root/references/miners/}"
  if [ "$(tr -d '\r' < "$ref" | sha256sum | cut -c1-64)" = "$cand_hash" ]; then
    printf "%-60s %8s %8s  FAIL identical\n" "$rel" "all" "100%"; status=1; continue; fi
  normalise "$ref" > "$tmp/ref"; shared=$(comm -12 "$tmp/candidate" "$tmp/ref" | wc -l)
  pct=$(( 100 * shared / total )); flag=""
  if [ "$pct" -ge "$FAIL_PCT" ]; then flag="FAIL"; status=1; elif [ "$pct" -ge "$WARN_PCT" ]; then flag="warn"; fi
  printf "%-60s %8d %7d%%  %s\n" "$rel" "$shared" "$pct" "$flag"
done < <(find "$root/references/miners" -name agent.py | sort)
echo; echo "candidate distinctive lines: $total; warn at ${WARN_PCT}%, fail at ${FAIL_PCT}%"; exit $status
```

### 20.5 Machine setup (Linux dev box, checked 2026-09-29)
| Tool | Status | Install |
|---|---|---|
| Python 3 | installed (3.14.4) | — (the agent itself must stay compatible with the task image's Python; samples use `python:3.13.7-slim-bookworm`; target 3.10+ syntax to be safe) |
| uv | installed (`~/.local/bin/uv`) | — |
| Docker | installed (required by `ridges miner run-local`) | — |
| Git, Node (v24) | installed | — |
| Go | missing (needed for Go practice tasks outside Docker) | `apt install golang-go` or go.dev tarball |

Then clone `ridgesai/ridges`, run `uv sync --extra miner`, then `ridges miner setup`, and put the OpenRouter key in `.env.miner`.

---

## 21. Templates

### 21.1 Experiment log
`docs/experiments/EXPERIMENTS.md`, one row per idea, including failures:

| ID | Date | Hypothesis | Dev before → after (solve / $) | Held-out | Status | Note |
|---|---|---|---|---|---|---|

Status: `idea` → `running` → `kept` / `reverted` / `parked`. Each experiment also gets `EXXX-<slug>.md` with: hypothesis, change (commit), references used (`REF …`), a results table (dev before/after, held-out at a gate: repeats, solve rate, $/task, p50, mechanical fails), per-task fixed/broken, and the decision with what was learned.

### 21.2 ADR
`docs/decisions/NNNN-<slug>.md`: status (proposed / accepted / superseded), date, context, decision, alternatives (pros/cons table), consequences, references (design section, `REF …`, experiment). The first ADR is **ADR-0001 "Phase artifacts with an evidence-gated submit"**, which records §15's first row and cites Enigma `agent.py:8052` and `:241` as the counter-example.

### 21.3 Submission manifest
`submissions/vNNN/` holds `agent.py` (byte-for-byte what was uploaded), `notes.md` (what changed, what we expect) and `manifest.json`:
```json
{
  "version": "v001", "uploaded_at": "", "competition_set_id": 28, "git_commit": "", "sha256": "",
  "models": {"spec": "", "driver": "", "critic": ""},
  "local": {"dev_solve": null, "heldout_solve": null, "cost_usd": null, "p50_sec": null, "repeats": 3},
  "upload": {"agent_id": "", "quote_id": "", "block_hash": "", "extrinsic_index": ""},
  "validator": {"score": null, "cost_usd": null, "runtime_sec": null, "status": "", "leader_at_approval": ""}
}
```
Calibration table (in `submissions/README.md`): version, held-out local, validator score, ratio, local $/task, validator $/task.

### 21.4 Review checklist (every PR touching `src/`)
- **Rules:** lint passes; originality passes; reference ideas cited in docs, not `src/`; network only via the proxy.
- **Behaviour:** experiment entry with 3-repeat dev numbers; every exit still returns a valid diff or the best candidate; scope enforced in code; budget and clock checks cover new calls and commands.
- **Cost:** new LLM calls have a phase budget and `max_tokens`; the prompt prefix stays stable; new tool output is capped.
- **Quality:** readable; ADR for architecture changes.

---

## Appendix A — Tool Set (LLM-facing)
| Tool | Purpose | Guard rails |
|---|---|---|
| `read(path, start, end)` | read a line range | cap 400 lines per call; repeat-read detection |
| `search(pattern, glob, context)` | ripgrep/grep | returns count + top 50 hits |
| `outline(path)` | tree-sitter symbols with spans | Python/Go/TS/JS/Ruby |
| `edit(path, old, new)` | exact single replacement | scope check; must match exactly once |
| `create(path, content)` | new file (e.g. a migration) | scope check; path must be inside allowed dirs |
| `shell(cmd, timeout, background)` | run commands | no network; no DB writes outside rollback; scratch dir enforced |
| `poll(job_id)` | collect a background result | — |
| `sql(query, db, explain)` | live DB lab | PG: wrapped in BEGIN…ROLLBACK + statement_timeout; CH: read-only or temporary/inline data only |
| `app_run(code, timeout)` | run a Python (or Go/TS) snippet **inside the app's context** from `/tmp/quarry/` (settings loaded, test DB, query capture helpers available) | file lives outside the repo; wrapped in a rolled-back transaction; output capped |
| `run_checks()` | run all `spec.checks` | code-run, exit codes into the ledger |
| `ledger(req_id, status, evidence)` | record proof | required before submit |
| `submit(summary)` | request finish | refused unless the gate passes (§6.6) |

## Appendix B — Evidence Ledger row
```json
{"req": "R2", "status": "PASS", "tier": "T3",
 "evidence": "scenario: 3 groups incl. empty → counts [3,2,0]; before patch: [2,2,NULL]"}
```

## Appendix C — Reward calculator (for planning)
```python
import math
def units(score, cost, lead_score, lead_cost, perf_t=0.03, cost_t=0.06):
    """Mirrors upstream utils/incentives.py: qualify first, then sum every *positive* improvement (no per-part threshold)."""
    perf_d = (score - lead_score) / lead_score
    cost_d = (lead_cost - cost) / lead_cost
    perf_u = math.log1p(perf_d) / math.log1p(perf_t) if perf_d > 0 else 0.0
    cost_u = min(math.log1p(-cost_d) / math.log1p(-cost_t), 1 / cost_t) if cost_d > 0 else 0.0
    qualified = perf_d >= perf_t or (score >= lead_score and cost_d >= cost_t)
    return perf_u + cost_u if qualified else 0.0
# multiply by (1 + math.sqrt(hours_leader_unbeaten / 6)); decays with a 336 h half-life
# e.g. leader 0.38 @ $0.0437, candidate 0.40 @ $0.043 -> ~2.0 units (the cost part below 6% still counts once qualified)
```

## Appendix D — Sources
- Docs: docs.ridges.ai (competitions/overview, database-query-engineering, agent-contract, scoring, incentive-mechanism, pre-screening, submit, mining-intro)
- Code: github.com/ridgesai/ridges @ d74410d (`ridges_harbor/ridges_miner_runtime.py`, `ridges_harbor/agents.py`, `api/endpoints/retrieval.py`)
- Samples: github.com/ridgesai/ridges-bench `db-engineering/` (6 tasks), incl. each task's `tests/verify.py`, `tests/create_source_manifest.py`, `environment/Dockerfile`, `environment/postgres-init.sh`, `environment/configuration.py`, `task.toml` (read 2026-09-29)
- Live data: `agent-upload.ridges.ai/competitions`, `/evaluation-sets/28/leaderboard`, `/overview` (fetched 2026-09-28/29)
- Competitor study (not reused): public code of ranks 15–22 (Enigma485, please, Supertop, CanCanCan, Emerge victory, DuoTao, Haha, venus); see Appendix E and §19

## Appendix E — Competitor Analysis (set 28, 2026-09-29)

### Leaders (code hidden)
| Rank | Agent | Score | Cost / task | Runtime | Status |
|---:|---|---:|---:|---:|---|
| 1 | hope v2 | 0.38 | $0.0437 | 629 s | under review |
| 2 | helicopter v8 | 0.36 | $0.0901 | 973 s | didn't qualify |
| 3 | thrush v7 | 0.36 | $0.0914 | 878 s | approved leader |
| 4 | Harry v11 | 0.36 | $0.1001 | 620 s | approved |
| 5–14 | Fred, river, IamSuper, crown, watch, WorldCup, virgo, glider, Belgium, Hagrid | 0.34 | $0.037–$0.090 | 499–1021 s | mostly didn't qualify |

### The Enigma family (ranks 15–20, code public)
All share the header `"""Generated standalone Ridges agent submission."""`, the same models (`~openai/gpt-luna-latest` driver, `deepseek/deepseek-v4-pro-0813` fallback) and the same tool set.

| Rank | Agent | Cost | Shared code vs Enigma485 | What changed |
|---:|---|---:|---:|---|
| 15 | Enigma485 v7 | $0.020 | — | base (build tag `Enigma486`) |
| 16 | please v3 | $0.022 | 96% | code-run checks on, conformance on, first edit by turn 5, retries/timeout recovery, one playbook line on join fan-out |
| 17 | Supertop v8 | $0.036 | 97% | as "please", plus final review removed, "re-run checks"/"frozen imports" prompt lines removed, outline off, easier second pass |
| 18 | CanCanCan v0 | $0.040 | 43% | leaner sibling (~130 functions vs ~580, build `avocado_v6`), rewritten prompt with concurrency/stale-write guidance, scout on, no second pass or review |
| 19 | Emerge victory v0 | $0.044 | 96% | review removed, second pass and A/B trial off, retries |
| 20 | DuoTao v8 | $0.045 | 96% | like Supertop (build `omg_v7`) |

**All six score 0.32.** Setting and prompt changes didn't move the score, and every fork costs more than the base.

### Enigma485: strengths to learn from (re-implement, never copy)
| Idea | Where |
|---|---|
| `sql` tool: PostgreSQL calls wrapped in a rolled-back transaction; ClickHouse writes refused, inline `values()`/`numbers()` encouraged; `explain=true` | `REF set-28/enigma485_v7_801d9e54/agent.py:655` |
| Budget object reading `RIDGES_MAX_COST_USD`, 88% cost share, 45 s wall reserve | `agent.py:88-92`, `:1623` |
| Crash-safe `agent_main`: restore the tree in `finally`, apply-check the final patch | `agent.py:8014` |
| Generic DB playbook ("five contracts", recurring shapes) | `agent.py:7183` |
| Retry ladder, transcript shrinking, parallel tool calls, network fence | `agent.py:1784` (`Seat`), `:7285` |

### Enigma485: gaps (Quarry's opportunities)
| Gap | Where |
|---|---|
| Second attempt only when the first produced nothing usable | `agent.py:8052` |
| Code-run checks off by default (`SUBMISSION_WARDEN=0`) | `agent.py:241` |
| Scope put-back off by default (`SCOPE_PUT_BACK=0`) | `agent.py:5621` |
| Plan and scout models off; one cheap model does everything | `agent.py:249-250` |
| Django-centric: 23 Django mentions, 0 Go-ORM mentions, no `.ts` syntax check | `agent.py:22-39` |
| ~15 features behind switches that are off: complexity with no production benefit | `agent.py:226-271` |

---

## 22. Changelog

### v3 (2026-09-29): check against the sources
Checked every hard claim against docs.ridges.ai, `ridges@d74410d` and the six sample tasks' checker code.

**Confirmed unchanged:** agent contract, `/app` workdir, git baseline, apply-check + separate checker container, proxy-only network, $0.29 cap, allowed packages, $5 fee / 12 h cooldown / logging off / ZDR models, reward formulas and every §2 worked number, pre-screening rules.

**Corrected or added:**
| Where | Change | Why |
|---|---|---|
| §0 | "~7× more" → "~3.7× more" | §2's own table: 12.6 vs 3.4 units |
| §1.3 | Binary per-task result; whole-tree conservation incl. file modes; byte-exact method bounds; method size/construct limits; timeout publishes nothing; non-superuser DB role with credentials in app config; image permissions; git baseline excludes | sample `verify.py`, `create_source_manifest.py`, `Dockerfile`, `postgres-init.sh`, `agents.py` |
| §1.4 | Root vs uid 1000 unknown; derive rules from statement text, not sample lists | sample `task.toml`; pre-screening |
| §6.3 | DB discovery reads app config first; record role privileges; writable-path probe | credentials are only in the app config in samples |
| §6.5 | Realistic data volume + `ANALYZE` for optimization; N vs 4N scaling check; driver-level query capture (no `log_statement`); `EXPLAIN ANALYZE` always rolled back; scratch code only in `/tmp/quarry/` | sample hidden tests measure query counts and `EXPLAIN (ANALYZE, BUFFERS)` |
| §6.6 | T1 is a gate (named tests already pass); T2 expanded into six deterministic checks | niche doc; sample `bounded_method()` / `source_identity()` |
| §6.8 | Guard restores file modes; `git add -N` only for allowed new files; evidence score no longer rewards T1 | same |
| §9.1 | Cost feasibility check; measure proxy caching at M0 | 20 × 12k tokens ≈ $0.05 uncached |
| §10 | Kill child process groups before return | cancelled run publishes no patch |
| §11 | Six new failure modes | from the checker code |
| §16 | Q7 cost route needs leader + 1 task margin; Q8 root vs agent user | noise; hidden logs |
| §20 | Tooling moved from PowerShell to Python/bash; machine table updated for the Linux dev box | environment |
| Appendix A | New `app_run` tool | lab code must run outside the repo |

### v3.1 (2026-09-29): external review
Source: `docs/reviews/2026-09-29-architecture-implementation.md`. All R1–R8 findings and the extra concerns were reproduced as failing tests (`tests/scenario/test_review_2026_09_29.py`) and fixed in code; requirements H-SHELL-07..10, H-LLM-07, H-GIT-04, H-SPEC-12..14, H-PROF-05, H-GUARD-12..14, H-LOOP-05, H-TOOL-09..10 added to `docs/specs/harness.md`.
| Where | Change | Why |
|---|---|---|
| §0.1, §2 | Cost-first thesis made conditional; order is mechanics → solve rate → cost policy | One more solved task can cross the qualification bar; cost units only count once qualified |
| §6.5, §6.6 T4, §11 | Work proof targets the statement's stated performance requirement, not "never grows with N" | Aggregates are legitimately O(N); query count ≠ rows ≠ buffers ≠ time |
| §6.6 T2 | Removed the "no data literals" rule | Field names and business statuses legitimately appear in code and tests |
| Appendix C | Calculator now mirrors upstream `utils/incentives.py` (sum of positive units once qualified) | Previous version dropped sub-threshold parts (0.40 @ $0.043 vs 0.38 @ $0.0437: 2.0 units, not 1.7) |

