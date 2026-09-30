# Quarry — working rules

Design: `architecture.md`. Specs: `docs/specs/`. Plans: `docs/plans/`. Process: `docs/process/engineering-loop.md`.

## Loop
Spec (requirement ID) → plan item → implement → test named after the ID → `uv run python tools/gate.py` → experiment log.

## Rules for `src/`
- Standard library only; Python 3.9 syntax (the bundle must run on the task image's `python3`).
- Cross-module imports only as top-level `from quarry.<module> import A, B` (parenthesised is fine). No other intra-package import form. Top-level names must be unique across modules (the bundler concatenates files).
- No grading vocabulary anywhere in `src/` (hidden tests, verifier, grader, benchmark, evaluation, harbor, sandbox except the env var `SANDBOX_PROXY_URL`, scoring words). `tools/prescreen_lint.py` enforces it on the bundle.
- No sample/practice task, repo, schema or file names in `src/`. Prompt examples use synthetic `orders`/`customers`.
- Network only through `SANDBOX_PROXY_URL` (or the local-run `RIDGES_INFERENCE_BASE_URL`).
- Every rule the agent enforces on a patch must be derived from the statement text, never from knowledge of how tasks are checked.
- Never copy code, prompts or constants from `references/`.

## Tests
- `uv run pytest` — unit + scenario + offline e2e.
- Test names contain the requirement ID: `test_H_GUARD_03_...`.
- Practice tasks: `python3 bench/validate_task.py bench/tasks/<set>/<id>`; live runs need `ridges miner run-local` and an OpenRouter key.

## Keep or revert
The rule is in `docs/process/engineering-loop.md` §5a (reliability fixes vs behaviour changes, the paired confirmation protocol, provisional until ≥ 15 dev tasks). Use `tools/bench_summary.py compare`; never keep a change on a single run.
