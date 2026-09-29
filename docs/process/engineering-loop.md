# Engineering Loop

How every change to Quarry moves from idea to submission. Spec-driven: a requirement exists (with an ID) before the code that satisfies it, and a test names the requirement it proves.

```
SPEC ──► PLAN ──► IMPLEMENT ──► TEST ──► GATE ──► FEEDBACK ──┐
  ▲                                                          │
  └──────────────── new requirement / new bench case ◄───────┘
```

## 1. Spec
- Requirements live in `docs/specs/*.md` with stable IDs (`H-SHELL-03`, `H-GUARD-07`, …).
- A requirement states *what* must hold and *how it is verified* (unit test, scenario test, bench task, or manual review).
- Changing behaviour means changing the spec first. Removing a requirement is an explicit edit, never silent.

## 2. Plan
- One plan per milestone in `docs/plans/`. Each plan lists work items, the requirement IDs they satisfy, and the exit gate.
- Architecture decisions that are hard to reverse get an ADR in `docs/decisions/`.

## 3. Implement
- Code in `src/quarry/` as normal modules. SOLID rules for this codebase:
  - **S**: one reason to change per module (clock, wallet, git, guard checks, tools, llm are separate).
  - **O**: new checks, tools, knowledge packs and stack probes are *added* by registering a class, not by editing a dispatcher.
  - **L**: every implementation of a protocol (`LLMClient`, `Check`, `Tool`, `Phase`) is usable wherever the protocol is.
  - **I**: small protocols (`Clock.now()`, `LLMClient.complete()`), not one big "context" object.
  - **D**: phases receive their collaborators (clock, wallet, repo, llm) through constructors, so tests inject fakes.
- Runtime code uses the standard library only (plus packages in `miners/baseline-requirements.txt` if ever needed). Python 3.9+ syntax.
- Cross-module imports use top-level `from quarry.<module> import ...`, which the bundler strips.

## 4. Test
| Layer | Where | Runs | Proves |
|---|---|---|---|
| Unit | `tests/unit/` | every save, < 10 s | one module against its requirement IDs |
| Scenario | `tests/scenario/` | every save, < 30 s | guard/spec behaviour on realistic repos and statements (many cases, all stacks) |
| End-to-end (offline) | `tests/e2e/` | before commit | bundled `dist/agent.py` against fixture repos through a fake proxy with scripted model replies |
| Bench (live) | `bench/tasks/{public,dev,heldout}` | on demand, needs OpenRouter key + `ridges` CLI | solve rate, $/task, time |

Every test names the requirement it proves: `test_H_GUARD_03_mode_change_is_restored`.

## 5. Gate
`tools/gate.py` runs the gates in order and stops at the first failure.

| Gate | Check | Blocks |
|---|---|---|
| G0 | `ruff check` on `src/ tools/ tests/` | commit |
| G1 | unit + scenario tests pass | commit |
| G2 | bundle builds; the bundle imports on Python 3.9+ syntax rules; no duplicate top-level names | commit |
| G3 | offline e2e tests pass against the bundle | commit |
| G4 | `tools/prescreen_lint.py dist/agent.py` clean | upload |
| G4b | `tools/originality_check.py dist/agent.py` passes against freshly fetched public agents (`tools/fetch_references.py`) | upload |
| G5 | traceability: every requirement ID in `docs/specs/` has ≥ 1 test or is marked `verify: bench`/`manual` | commit |
| G6 | bench: dev set 3× — solve rate and $/task not worse than the last kept result; 0 mechanical failures | merge of a behaviour change |
| G7 | held-out set 3× meets the submission target (architecture §12.4) | upload |

G0–G5 are automatic and free. G6–G7 cost inference money and are run deliberately.

## 6. Feedback
- Every bench run writes `bench/runs/<timestamp>/results.csv` and a failure taxonomy (mechanical / locate / semantic / perf / scope).
- Each behaviour change is an experiment row in `docs/experiments/EXPERIMENTS.md` with before/after numbers.
- Each new failure type becomes (a) a new requirement if the harness should prevent it, and (b) a new bench case in `docs/specs/bench-catalog.md` on a *different* stack than where it was seen.
- Validator results go into `submissions/README.md` (calibration table).
