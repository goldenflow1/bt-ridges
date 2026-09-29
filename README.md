# Quarry

An agent for the Ridges (SN62) **Database Query Engineering** competition: given a repository, a live PostgreSQL/ClickHouse database and a problem statement, it changes the production data path and returns a unified diff.

| Where | What |
|---|---|
| `architecture.md` | System design (v3, checked against docs, `ridges@d74410d` and the sample tasks' checker code) |
| `docs/specs/harness.md` | Requirements with IDs (H-*) — every one traced to a test |
| `docs/specs/bench-catalog.md` | Practice-task catalog beyond the 6 public samples (24 tasks, both engines, Python/Go/TS) |
| `docs/plans/M0-harness.md` | Current milestone plan and exit gate |
| `docs/process/engineering-loop.md` | Spec → plan → implement → test → gate → feedback |
| `docs/experiments/EXPERIMENTS.md` | Experiment log |
| `src/quarry/` | Agent modules (stdlib only, Python 3.9+) + `prompts/`, `packs/` |
| `tools/` | `build.py` (bundle), `prescreen_lint.py`, `gate.py` (G0–G5), `run_bench.py` (G6/G7) |
| `tests/` | `unit/`, `scenario/` (statements + repos for many stacks), `e2e/` (bundle vs fake proxy) |
| `bench/tasks/` | `public/` (6 ridges-bench samples), `dev/`, `heldout/` practice tasks; `bench/validate_task.py` |

## Daily commands
```bash
uv sync                                   # dev tools (pytest, ruff)
uv run python tools/gate.py               # G0–G5: lint, tests, bundle, py3.9 import, e2e, pre-screen lint, traceability
uv run python tools/build.py              # -> dist/agent.py
python3 bench/validate_task.py bench/tasks/dev/<id>          # practice-task validity (B-VALID-01..06)
uv run python tools/run_bench.py --set public --repeats 3 --ridges "uv run --project ../ridges-cli ridges"   # live (needs key)
```

## Live runs (not set up yet on this machine)
1. Clone `ridgesai/ridges`, `uv sync --extra miner`, `ridges miner setup` (OpenRouter key with logging off, ZDR models).
2. Optional local model override: `QUARRY_DRIVER_MODEL`, `QUARRY_FALLBACK_MODEL` (production uses the defaults in `src/quarry/shell.py`; verify model ids and prices on OpenRouter first).
