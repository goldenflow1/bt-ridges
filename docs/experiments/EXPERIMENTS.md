# Experiments

One row per idea, including negative results. Status: `idea` → `running` → `kept` / `reverted` / `parked`.
A change counts only if it holds across 3 repeats and moves held-out by ≥ 2 tasks per 25, or cuts cost ≥ 15% at an equal score.

| ID | Date | Hypothesis | Dev before → after (solve / $) | Held-out | Status | Note |
|---|---|---|---|---|---|---|
| E000 | 2026-09-29 | M0 harness: every run ends in a valid, in-scope, apply-checked diff; 0 crashes | — | — | running | Offline gates green. External review found a P0 hand-off bug (tree left dirty ⇒ platform apply-check fails) + 7 P1/P2 issues; all reproduced and fixed (docs/reviews/2026-09-29-response.md), 75/75 requirements traced. Live baseline on `public` pending. |
| E001 | — | Measure proxy prompt caching (`cached_tokens`) on the first live run; decides the $0.03 target (architecture §9.1) | — | — | idea | |
| E002 | — | Lab phase (M2): repro-first + T3 differential proof reduces wrong-but-valid patches | — | — | idea | |
| E003 | — | Critic (M3) on candidates without T3 evidence: +2 tasks at ≤ +$0.004 | — | — | idea | |
| E004 | — | Go/TS symbol splice via tree-sitter-free brace matching (M4) removes byte drift on non-Python tasks | — | — | idea | |
| E005 | 2026-09-29 | Smoke test: the agent spent 1,343 of 1,493 s re-running a slow Django check that timed out each round (25%-of-remaining timeout, re-run unchanged), and its output was never logged. Baseline check run before editing (warms the test DB, measures duration) + timeouts derived from it + skip-as-unknown when the baseline is too slow + full check observations in the log/telemetry → fewer wasted minutes, no false 'last-resort' from checks that fail before any change | — | — | running | Reliability fix under W6 (requirements H-SHELL-11..13, `tests/scenario/test_check_policy.py`). Needs the re-run smoke test and the offline timing of the NetBox check to confirm. |
