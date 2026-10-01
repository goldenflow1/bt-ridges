# Quarry

An agent for the Ridges (Bittensor SN62) **Database Query Engineering** competition. Given a repository, a live PostgreSQL or ClickHouse database and a problem statement, it changes the application's production data path and returns a unified diff.

- **Current status:** see [Status](#status) below.
- **Design:** [`architecture.md`](architecture.md).
- **How work is done here:** [`docs/process/engineering-loop.md`](docs/process/engineering-loop.md) and [`CLAUDE.md`](CLAUDE.md).

---

## Setup on a new device

### 1. Prerequisites
| Tool | Why | Check |
|---|---|---|
| Linux or macOS with **Docker** (Engine + Compose v2) | practice tasks and `ridges miner run-local` run in containers | `docker compose version` (Ubuntu's `docker.io` lacks it: `apt-get install docker-compose-v2`) |
| **git** | this repo and the Ridges CLI | `git --version` |
| **uv** | Python environments (installs Python itself) | `uv --version` (install: `curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| ~20 GB free disk, 8 GB+ RAM | task images | `df -h`, `free -g` |
| **A fast CPU**, if you want to run the NetBox public samples | their Django checks must finish in < 10 min cold; on the original dev host (Xeon E5-2680 v3 VM) they take ≈ 23 min; on a Ryzen 9 7950X3D, 198 s | see step 6 |

### 2. Get this repo and its dev tools
```bash
mkdir -p ~/bittensor && cd ~/bittensor
git clone <this-repo-url> ridges          # the project directory is named `ridges`
cd ridges
uv sync                                   # dev tools: pytest, ruff
uv run python tools/gate.py               # G0–G5: lint, tests, bundle, Python 3.9 import, e2e, pre-screen, originality, traceability
```
All gates should pass before you do anything live. The bundle is written to `dist/agent.py` (git-ignored; rebuild any time with `uv run python tools/build.py`).

### 3. Install the Ridges CLI (pinned commit)
The bench runner calls `ridges miner run-local`. Keep the CLI next to this repo at the commit the design was checked against:
```bash
cd ~/bittensor
git clone https://github.com/ridgesai/ridges.git ridges-cli
cd ridges-cli && git checkout d74410d8      # pinned; see architecture.md Appendix D
uv sync --extra miner
```
`bench/validate_task.py` reads the runtime's package list from `~/bittensor/ridges-cli/miners/baseline-requirements.txt`, so keep that path.

### 4. Configure the CLI and your OpenRouter key
Create the config (paths must match your home directory):
```bash
mkdir -p ~/.config/ridges ~/.ridges
cat > ~/.config/ridges/miner.toml <<EOF
[miner]
workspace = "$HOME/.ridges"
agent_path = "$HOME/bittensor/ridges/dist/agent.py"
provider = "openrouter"
EOF
printf 'RIDGES_OPENROUTER_API_KEY=\nRIDGES_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n' > ~/.ridges/.env.miner
chmod 600 ~/.ridges/.env.miner
nano ~/.ridges/.env.miner                   # paste your key after RIDGES_OPENROUTER_API_KEY=
```
In the OpenRouter dashboard: turn **Input & Output Logging off** (Plugins → Observability) — the Ridges proxy rejects keys with logging on — use only zero-data-retention models, and set a per-key credit limit.

Check the key without printing it:
```bash
python3 -c "import json,urllib.request;k=[l.split('=',1)[1].strip() for l in open('$HOME/.ridges/.env.miner') if l.startswith('RIDGES_OPENROUTER_API_KEY')][0];print(json.load(urllib.request.urlopen(urllib.request.Request('https://openrouter.ai/api/v1/key',headers={'Authorization':'Bearer '+k})))['data'])"
```

### 5. Validate the practice tasks (Docker, no inference cost)
```bash
python3 bench/validate_task.py bench/tasks/dev/py-sqla-orders-fanout    # ~5–10 min per task with warm images
```
Every task must end `RESULT: PASS`. Checks are defined in [`docs/specs/bench-catalog.md`](docs/specs/bench-catalog.md) §8.

### 6. Live runs (costs inference money)
```bash
uv run python tools/build.py
uv run python tools/run_bench.py --set dev --repeats 1 --ceiling 30 --allowance 0.29 \
    --ridges "uv run --project $HOME/bittensor/ridges-cli --no-sync ridges"
```
- Results: `bench/runs/<timestamp>-<set>/results.csv`, `summary.json`, `manifest.json`, raw logs.
- **Spending:** `bench/runs/ledger.json` is a shared envelope (default $30), reconciled against the key's own usage. It is git-ignored and **per device** — on a new device either start a fresh envelope or copy the old ledger over, and subtract what was already spent (see Status).
- **NetBox public samples** (`--set public`): only on a fast machine. First time the check offline: bring the task up and time `python netbox/manage.py test … --keepdb --noinput`; it must take well under 600 s cold, or every run times out in the checker regardless of the patch.
- Model override for experiments only: `QUARRY_DRIVER_MODEL=... QUARRY_FALLBACK_MODEL=...`.

### 7. Keeping long runs alive
Validation and bench runs take minutes to hours. Start them detached so a closed terminal doesn't kill them:
```bash
setsid nohup uv run python tools/run_bench.py ... > run.log 2>&1 < /dev/null &
tail -f run.log
```
Watch the agent live: `tail -f $(ls -td ~/.ridges/runs/*/*/ | head -1)agent/runtime.log | grep --line-buffered '^\[quarry\]'`.

### 8. Before any upload
`tools/gate.py` (G0–G5, G4 pre-screen lint, G4b originality against freshly fetched public agents: `uv run python tools/fetch_references.py --set-id 28 --want 10`), the held-out set 3×, and the upload gate in [`docs/process/engineering-loop.md`](docs/process/engineering-loop.md). Uploads cost ~$5 in Alpha plus inference and have a 12 h cooldown.

---

## Repository map
| Where | What |
|---|---|
| `architecture.md` | System design (v3.1, checked against the Ridges docs, `ridges@d74410d` and the sample checkers) |
| `docs/specs/harness.md` | Agent requirements (H-*), each traced to a test by gate G5 |
| `docs/specs/bench-catalog.md` | Practice-task catalog, validity checks and bench requirements (B-*, with stage/status/evidence) |
| `docs/plans/` | Milestone plans with results: `M0-harness.md`, `M0.5-pre-smoke-hardening.md` |
| `docs/reviews/` | External reviews and our responses |
| `docs/experiments/EXPERIMENTS.md` | Experiment log |
| `src/quarry/` | Agent modules (stdlib only, Python 3.9+), `prompts/`, `packs/` |
| `tools/` | `build.py`, `gate.py`, `prescreen_lint.py`, `originality_check.py`, `fetch_references.py`, `run_bench.py`, `bench_records.py` |
| `tests/` | `unit/`, `scenario/`, `e2e/` (bundle against a fake proxy) |
| `bench/` | `tasks/public` (6 ridges-bench samples), `tasks/dev` (5 practice tasks), `validate_task.py`, `runner_results.py` |
| `references/` | Other miners' public agents, read-only, for the originality check only — **never copy from here** |

---

## Status
_Last updated 2026-09-30._

| Area | State |
|---|---|
| Harness (M0) | Runtime deadline and malformed-response accounting fixes in v003; G0–G5 pass, 94/94 traced requirements |
| Measurement integrity (M0.5A, B1) | Confirmation checks enforce version identity and three unique trials; cost approval requires agreement between provider billing and key usage. Runner freezes its input and checkpoints each slot. |
| Smoke test | Passed on a dev task (solved, $0.0092) |
| Reconnaissance (dev set, 1 run each) | **5/5 solved**, $0.0102 per task on average (provider-reported = key usage), cache read share 83–95% |
| Baselines (3 trials per task, bundle `2b2d1281`) | Dev 17 tasks **51/51** ($0.009685/trial); NetBox public **17/18** ($0.015860); reconciled figures in `bench/baselines/` |
| Held-out gate G7 | **v003 uploaded** (`060edea3`): 17/21 solved, 0 mechanical, $0.006700/trial, 21/21 costs reconciled. Same per-task outcomes as v001; reliability comparison keeps the fixes. Full evidence is packaged in `submissions/v003/evidence/`. v001 is retired due to the firewall lint. |
| Originality | ≈ 1% overlap with 10 public agents (limit 30%) |
| Spend | See `bench/runs/ledger.json`; shared local envelope $30. Check the current OpenRouter key limit separately; historical dashboard values are not current evidence. |
| Competition (set 28, checked 2026-09-29) | Open, no end date, 90% of emissions. Best approved agent: 0.36 at $0.091/task. To qualify: ≥ 0.36 at ≤ $0.086 (cost route) or ≥ 0.38 (performance route) |

**Next steps**:
1. v003 uploaded successfully as agent `3cb91034-fe6f-5271-94be-c8be974fefdf`. The payment receipt is saved in `submissions/v003/manifest.json`; next record the screening/validator result and calibration metrics. No validator score has been recorded yet.
2. Extra fix rounds (`a76e441b`, historical log named E008): finished 16/18 vs 17/18. Confirmation is pending; do not promote it. Mean key delta $0.086119 differs from telemetry $0.021208, so the raw delta is not reliable per-trial cost evidence. E008 in the experiment catalog is a different, task-authoring experiment.
3. Weak spots from held-out: `pg-expr-index-lower` 0/3 (checks failed), `ch-go-skip-index` 2/3. Diagnose on dev-equivalent tasks, never by tuning on held-out.
