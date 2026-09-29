# PLAN — M0 Harness (+ deterministic spec compiler and guard)

Status: offline gates green (live bench pending an OpenRouter key) · 2026-09-29 · Spec: `docs/specs/harness.md`

## Goal
A bundled `dist/agent.py` that, for any statement and repo, returns a valid, in-scope, apply-checked diff or the best candidate, never crashes, never overruns time or budget. Offline-testable end to end with a fake proxy.

## Work items
| # | Item | Module(s) | Requirement IDs | Tests |
|---|---|---|---|---|
| 1 | Clock, deadline, phase slices | `clock.py` | H-SHELL-02, H-SHELL-06 | unit |
| 2 | Wallet | `wallet.py` | H-WALLET-01..05 | unit |
| 3 | Process runner (process groups, caps) | `proc.py` | H-SHELL-04, H-TOOL-05 | unit |
| 4 | Git wrapper | `git.py` | H-GIT-01..03 | unit |
| 5 | TaskSpec model + deterministic compiler | `spec.py` | H-SPEC-01..11 | scenario (6 public + synthetic statements) |
| 6 | Environment profiler | `profile.py` | H-PROF-01..04 | scenario |
| 7 | Python symbol locator + splice | `pysource.py` | H-GUARD-04..07 | scenario |
| 8 | Guard (repairs + checks as registered strategies) | `guard.py` | H-GUARD-01..11 | scenario |
| 9 | LLM client (proxy, retries, fallback, telemetry) | `llm.py` | H-LLM-01..06 | unit (fake HTTP server) |
| 10 | Tools + registry | `tools.py` | H-TOOL-01..08 | unit |
| 11 | Driver loop | `loop.py` | H-LOOP-01..04 | unit (scripted fake LLM) |
| 12 | Candidate store + shell + `agent_main` | `shell.py`, `agent.py` | H-SHELL-01,03,05 | unit, e2e |
| 13 | Prompts + core pack | `prompts/*.md`, `packs/*.md` | — | lint |
| 14 | Bundler | `tools/build.py` | H-BUILD-01..03 | unit |
| 15 | Pre-screen lint | `tools/prescreen_lint.py` | H-LINT-01 | unit |
| 16 | Gate runner + traceability | `tools/gate.py` | G0–G5 | self |
| 17 | Offline e2e: bundle + fake proxy + fixture repo | `tests/e2e/` | H-SHELL-01,03 | e2e |

## Workflow inside `agent_main` (M0)
```
spec = compile(statement)            # deterministic (LLM normalisation arrives in M1)
profile = profile(repo)              # deterministic
driver loop (cheap model) with tools, spec checklist pinned
  → on finish / deadline / budget: run spec.checks (T1), guard (T2), store candidate
return best candidate
```

## Exit gate (M0)
- G0–G5 green.
- Offline e2e: scripted model edits a fixture repo out of scope, changes a mode, adds a junk file and breaks the bounded method's neighbour → returned diff contains only the in-scope method change.
- When an OpenRouter key is available: 6/6 public samples return an apply-able in-scope diff via `ridges miner run-local`, 0 crashes (bench G6 baseline recorded, solve rate not a target yet).
