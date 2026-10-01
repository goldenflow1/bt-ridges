# PROTOCOL — E016: B2/B3 under synthetic budget pressure

Status: **declared 2026-10-01, before any E016 trial**; amended 2026-10-01 after the [follow-up review](../reviews/2026-10-01-e016-followup.md) (enforced limits, reservation hold, outcome contract, evidence rules); ×15 pilot passed; calibration amendment §3a: ×25 pilot passed and ×25 frozen; main cohort complete; **decision: keep** (gain on 2 tasks; the one drop not reproduced in the confirmation block) — see E016.
Reviews: [readiness](../reviews/2026-10-01-e016-readiness.md), [follow-up](../reviews/2026-10-01-e016-followup.md).

## 1. Question and what this can show

Do the B2/B3 finalization mechanisms (H-LOOP-06/07, H-SHELL-15) change outcomes when a run is under budget pressure — the condition in which v003 returned six no-patch results in screening? Locally, runs never approach the budget, so B2/B3 never engage (E015); a §5a gain cannot appear in normal cohorts.

**What the condition is.** `cost-x15` multiplies the `usage.cost` **returned** to the agent by 15. The agent's pre-call estimates, affordability checks and reservations stay at real prices, so a call can fit its estimate and then consume 15× after completion. This tests *unexpected billing pressure*. It is **not** a faithful expensive-fallback simulation (model behavior and token counts are unchanged) nor a provider hard cap. The factor comes from $0.147 (25 cost-reported screening runs) / $0.0097 (local dev mean) ≈ 15; that ratio compares different tasks, routing and conditions and is not an identified per-call multiplier. Real billing per forwarded request is unchanged, but total spending can differ between arms because the altered feedback changes behavior.

## 2. Frozen inputs

| Item | Identity |
|---|---|
| Arm A — without B2/B3 | `d8d965c67e98ed6294cc2ac4448803bee83bb4f9a0ae0003b46e8a7a7d1decfe`, built by `tools/build.py` from commit `eb9e6ee` (A0/A1a after review). Local copy `bench/variants/v004-a-only-eb9e6ee.py` (not committed; rebuild is byte-identical). |
| Arm B — with B2/B3 | `5406e4dd79608e0109e8d1c283879f63b78099a11cd422193623a4a7f5a49637`, built from `src/` as of `a2bbc42` (A0/A1a + B2/B3 after both reviews + finalization-event logging). Local copy `bench/variants/v004-b2b3-5406e4dd.py` (not committed; rebuild is byte-identical). |
| Scenario | `bench/faults/cost-x15.json`, SHA-256 `2b8f28ecb53301ea209bfe6defa9b78bac07f81dddee5928154fae0db4a13ae3` |
| Tasks | `bench/tasks/dev/*` at the digests the runner records (17 tasks); unchanged by decision, including py-django-n-plus-one's unstated `__dict__` rule |
| Runner | `tools/run_bench.py --agent A --agent-b B --fault-scenario bench/faults/cost-x15.json`: each task × repeat is a pair, order A,B on even and B,A on odd pairs, trials serial; one cohort per arm |
| Runtime | this host, Ridges CLI `d74410d8`, cap `RIDGES_MAX_COST_USD` default 0.29 (driver phase ≈ $0.222 as the agent sees it) |

**Launch only through `bench/launch/e016.sh pilot|main`**, which refuses to start unless both bundles and the scenario match the hashes above and passes every limit in §6 as an enforced runner flag. Each arm's bundle is copied into its run folder at start; a change to either source file afterwards does not affect the cohort, and the input-mutation check marks any trial whose inputs moved as unresolved.

## 3. Technical pilot (before the main cohort; excluded from it)

Four preselected dev tasks, one A/B pair each (8 trials), `--purpose diagnostic`:

| Task | Why |
|---|---|
| py-django-n-plus-one | among the costliest dev tasks (≈ $0.016 real; reached the reserve at ×10) |
| py-sqla-orders-fanout | occasionally long (one run at $0.079 real) |
| ts-prisma-groupby | mid-cost, other language |
| ch-py-prewhere-orderkey | cheapest (≈ $0.003–0.005): pressure should *not* trigger |

The pilot passes only if all hold:
1. Every trial reaches the proxy from its container; `proxy_complete` true and `cost_reconciliation = matched-proxy` on all 8; `proxy_unscaled = 0`.
2. Outcome categories and `fin_*` event counts are populated; arm A shows no finalization events (it has none); the pair order alternates.
3. **Stress is real but not saturating:** at least one A trial and one B trial reach the finishing reserve (reported spend ≥ 75% of the driver phase), and not every trial of both arms ends without a patch.

If (3) fails, the factor is changed, saved as a **new scenario file with a new identity**, this protocol is amended with the date, and the pilot is repeated. Pilot results never enter the main cohort.

**Pilot limit:** `--spend-limit 0.50`, enforced before every dispatch: settled real cost + held unreconciled allowances + the next $0.29 allowance must fit, so the pilot cannot exceed $0.50 even if a trial spends its whole per-run cap.

## 3a. Calibration amendment (2026-10-01, after the ×15 pilot)

The ×15 pilot **passed** §3 (E016-pilot: 8/8 complete accounting, $0.07149 settled, nothing held) and is preserved as is. Its stress reached the finishing reserve on 1 of 4 deliberately selected tasks. An offline projection from two earlier dev cohorts (holding execution paths unchanged; different builds, so a calibration hint only) puts 1/17 tasks above the reserve threshold at ×15 versus 7–8/17 at ×25.

**Deliberate calibration change:** a second pilot under `bench/faults/cost-x25.json` (SHA-256 `f0166642b9c673203a69d8d2be0b0029e65a9255fe890f309f9bbc43e1f7714c`), with **the same two bundles, the same four tasks** and the **same pilot envelope** (`e016-pilot`, $0.50 total; $0.42851 left after the ×15 pilot). Launch: `bench/launch/e016.sh pilot x25`.

**Choosing the main condition** uses stress coverage and saturation only — **never whether B beats A**:
- ×25 is frozen for the main cohort if it passes §3 (1)–(2) and reaches the reserve on at least 2 of the 4 tasks in arm A without saturating (saturation: in both arms, 3 or more of the 4 tasks end without a passing-check patch because the budget ran out).
- If ×25 saturates, or still reaches the reserve on fewer than 2 tasks, the condition is decided in a further dated amendment before any main-cohort trial.
- The chosen condition is frozen by setting `MAIN_CONDITION` in `bench/launch/e016.sh` in the same commit as the amendment; until then `main` refuses to start.
- The §5 stress threshold (at least 6 of 17 tasks with an arm-A trial reaching the reserve) is unchanged.

**Activation is reported separately** for each mechanism: B2 — finalization notices (`fin_notices`) and finalization rounds (`fin_rounds`); B3 — refused and accepted empty finishes (`fin_refusals`, `fin_empty_accepts`). The ×15 pilot exercised only a B2 notice.

**Observation from the ×15 pilot (not evidence of a regression; one trial):** B's py-django-n-plus-one stopped on budget at turn 20 after its notice, with a mid-edit tree (visible tests failing, an unused import) returned as a last-resort candidate; no finalization round ran because H-SHELL-15 requires *no* candidate. A, which has no pre-request affordability quote, overshot to 101% and finished. The main-cohort analysis will report budget-stop-with-failing-candidate outcomes per arm.

**Calibration result (2026-10-01):** the ×25 pilot (`20261001-080347-dev-A/-B`) passed §3 (1)–(2): 8/8 matched-proxy and complete, 0 unscaled, 0 uncertain; categories and completion evidence on 8/8; arm A without events; order alternated. Arm A reached the finishing reserve on **2 of 4** tasks (py-django-n-plus-one 98%, py-sqla-orders-fanout 100%); not saturated (1 of 4 tasks per arm ended without a passing patch — py-django-n-plus-one in **both** arms, each a budget stop with a failing last-resort candidate). Activation: B2 notices 2, B2 rounds 0, B3 refusals 0, B3 accepts 0. Pilot envelope settled $0.125712 of $0.50, nothing held. Under the rule above, **×25 is frozen as the main-cohort condition** (`MAIN_CONDITION="x25"` in `bench/launch/e016.sh`, same commit). Outcomes (A 3/4, B 3/4) played no part in the choice.

## 4. Main cohort

17 dev tasks × 3 repeats × 2 arms = **102 trials**, `--purpose evaluation`, serial, counterbalanced as in §2. Estimate ≈ 4.5–5 h and ≈ $1–1.5 real (estimates, not limits).

Recorded per trial: outcome category, reward, real (trusted) and simulated cost, proxy request counts and model mix, `fin_notices`/`fin_refusals`/`fin_empty_accepts`/`fin_rounds`, and pair id/position.

## 5. Decision rule (release acceptance unchanged: engineering-loop §5a)

**Diagnostic metric (reported, not acceptance):** no-patch outcomes per arm — `empty-output` and `harness-exception` kept separate; `not-started`/`missing-evidence` are evidence failures, not agent outcomes. This is not identical to production error 1000, which also covers exceptions.

**Acceptance of B over A** follows §5a as written:
- **Gain:** at least one more task solved 3/3 in B than in A, **or** B's attributable (real, trusted) cost ≤ 85% of A's with every task A covers still covered;
- **and** no confirmed regression and no new agent mechanical failure. A gain elsewhere never offsets a regression.
- **Drops:** 3/3 → 1/3 or 0/3 is a material regression (reject). Any other per-task drop (e.g. 3/3 → 2/3, 2/3 → 1/3) triggers **one** paired confirmation block: 3 more A/B pairs on the affected tasks only, same scenario, counterbalanced; the drop persists if B solves fewer of those than A. Reported cumulatively; nothing replaced.

**Evidence rules (amended):**
- *Solve-based acceptance* needs a known outcome for every planned slot; an unresolved slot (missing evidence, changed inputs, unknown reward) leaves its task **pending** under the comparison rules — it never passes acceptance by being left out.
- *Cost-based acceptance* needs **complete** trusted (proxy-reconciled) real cost for every counted trial of both arms; otherwise the cost branch is unavailable, not passed.
- *Diagnostic fields* — finalization counts (`fin_*`, unknown when `fin_observed` is false), simulated cost, model mix — may be missing for up to 10% of trials per arm without invalidating a decision; their coverage is reported.
- Outcome categories follow the completion contract (B-RUN-06): completion needs a parsed, supported telemetry record (truncated, malformed or unknown-version records are not completion); the agent's own no-change exit is `empty-output`; other exceptions are `harness-exception`; no completion record is `missing-evidence`.

**Outcomes:**

| Result | Meaning |
|---|---|
| **keep** | gain and no regression → B2/B3 enter v004 (then the normal-condition comparison and G7) |
| **reject** | confirmed or material regression |
| **no gain** | complete, valid, sufficiently stressed cohort without a §5a gain → B2/B3 stay out of v004 |
| **inconclusive** | insufficient stress (fewer than 6 of 17 tasks have an A trial reaching the finishing reserve), pending tasks under the evidence rules, a diagnostic coverage gap above 10%, or the run stopped early → no decision; not evidence that B2/B3 are ineffective |

## 6. Spending and stop conditions

- Key headroom at declaration: $20.72 of the key's $30 limit (proposal figure; refresh before starting). Keep ≥ $5 for the later normal-condition comparison (~$1), held-out G7 (~$0.2) and confirmations.
- The ledger now reserves each allowance before dispatch and releases it on reconciliation, so serial trials hold one $0.29 allowance at a time; worst-case 102 × $0.29 is never reserved at once.
- **Enforced by `bench/launch/e016.sh`** (B-RUN-06), all checked before every dispatch including setup replacements:
  - `--spend-limit 0.50 --experiment-id e016-pilot` (pilot) / `--spend-limit 4.00 --experiment-id e016-main` (main): settled real cost + held unreconciled allowances + next allowance. The envelope persists per experiment id (`bench/runs/envelopes/<id>.json`): a relaunch restores its settled cost and held reservations, and refuses a different limit;
  - `--keep-headroom 5`: the key's `limit_remaining` minus held and next allowances must stay ≥ $5; unknown headroom refuses dispatch;
  - `--stop-on-billing-mismatch` (another client on the key), `--stop-on-input-change`, `--max-blocked-slots 2`, `--max-consecutive-incomplete 3`.
- A trial without reconciled real cost keeps its $0.29 allowance held (also across restarts) until its cost is established; a stopped run is reported as inconclusive.
- The OpenRouter key must have no other active users during E016 (the unexplained DeepSeek 0423 usage must be stopped or the experiment run on a dedicated key).

## 7. Record

Results go to `docs/experiments/EXPERIMENTS.md` as E016 (pilot as E016-pilot), with per-task paired outcomes, outcome categories, real and simulated cost, budget overshoots (agent-reported spend above its phase cap), and activation rates. The decision cites this protocol's rule by section.
