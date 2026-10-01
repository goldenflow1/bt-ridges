# v001 — first (calibration) upload

**Retired before successful upload.** The updated firewall lint rejects SQL function-call text in this frozen file. Keep these historical bytes and measurements; use the release selected by `submissions/READY` after its own evaluation passes.

**Bundle** `2b2d1281` (src unchanged since `550c4f8`): the M0 harness with the E005 check policy. No behaviour change since reconnaissance.

**Why now:** G7 passed against the target declared before any held-out result existed (wave3 plan §6). The main purpose is calibration: how local solve rates map to validator scores.

**Local evidence (3 trials per task, bundle fixed):**

| Set | Solve | $/trial | Notes |
|---|---|---|---|
| Dev, 17 tasks | 51/51 | $0.0095 | Too easy to discriminate (waves 1–2) |
| NetBox public, 6 tasks | 17/18 | $0.0153 | prefix-hierarchy-annotations 2/3, the only miss |
| Held-out, 7 tasks | 17/21 | $0.0061 | pg-expr-index-lower 0/3 (checks failed), ch-go-skip-index 2/3 |

**What we expect:** a validator score well below local rates; the leader is 0.36 on hidden tasks while we solve 94% of the public samples locally. Cost should stay far below the leader's $0.090/task, so the cost route (≥ 0.36 at ≤ $0.086) depends on the score alone.

**Known gaps:** E008 (extra fix rounds) not included: on NetBox it is not better and costs ~2× (comparison in progress). Held-out tasks were not written in a fresh session. Production time limit and run-as-root are unobserved.

**After approval:** fill `upload` and `validator` in manifest.json and the calibration table in `submissions/README.md`.
