# PLAN — v004 screening recovery

Status: planned, not implemented · updated 2026-10-01.

This records and corrects the proposed recovery plan after v003 failed screening. The next candidate is **v004**. Creating this document does not change the runtime, promote a release, authorize additional spending, or demonstrate readiness to upload.

Sequence: preserve evidence → **per-request billing export (gates priorities, §6 step 0)** → specify and reproduce defects → deadline, routing-defect and hand-off fixes → **v004 minimum release (§6a)** → routing-policy, transcript and progress experiments → rehearsal → freeze and evaluate the exact release → submission.

## 1. Goal and release identity

Make Quarry finish useful work within its time and spending limits when inference requests fail, cache savings disappear, or other workers share provider capacity. Demonstrate the improvement through attributable measurements and the existing keep/revert protocol before another upload.

- Uploaded release: [v003](../../submissions/v003/manifest.json), agent `3cb91034-fe6f-5271-94be-c8be974fefdf`.
- Submitted SHA-256: `060edea3568360c90aea234bf5227257c79a3e9926b8cd7275ec24af1dfeae1c`.
- v001 is historical; v002 is an abandoned candidate. Do not reuse either name or overwrite v003's measured bundle.
- Keep `submissions/READY` unchanged until a new release passes its declared gates. Its current selection of v003 is historical local approval, not evidence that v003 passed production screening.
- Add production screening evidence to v003's record; create `submissions/v004` only when a candidate is frozen.

## 2. Evidence and uncertainty

These findings describe the reviewed snapshot, not a live platform status check.

| Finding | Evidence and limits | Consequence |
|---|---|---|
| Screening failed: 18 solved, one wrong patch, six error-1000 results, five error-3060 pruned results out of 30 slots | Saved [public study](../reviews/public-agent-study-20261001/analysis.json); error 1000 can mean no patch **or an exception** | Investigate termination and hand-off as well as first-edit timing. Do not label all six as confirmed budget exhaustion. |
| Mean reported production cost was about $0.147227 | Denominator is the 25 cost-reported runs; five pruned slots have missing cost. Reported subtotal is about $3.680686 | Do not present this as a complete billed total or a measured mean across all 30 slots. |
| Primary failures can leave later calls permanently on fallback | [ProxyClient](../../src/quarry/llm.py) retains model failure counters across calls; fallback success does not reset the primary counter | Reproduce with a deterministic test and introduce bounded recovery. |
| A socket timeout does not enforce the complete call deadline | [Slow-response probe](../reviews/public-agent-study-20261001/timeout-probe.json): a 0.1 s timeout allowed a roughly 0.636 s successful body read | Enforce the absolute deadline throughout response reading, not just connection setup. This reproduction does not establish the production cause. |
| Temporary and terminal budget refusals are treated alike | [Budget probe](../reviews/public-agent-study-20261001/budget-probe.json): both `in_flight_budget_exhausted` and a hard cap terminate immediately | Classify structured errors before deciding whether retry is permissible. |
| Local cache savings were substantial, but cache loss alone does not explain the production gap | [Cache review](../reviews/public-agent-study-20261001/cache-review.json): 284 calls, 21 trials, 91.79% reported cache-read share; actual mean $0.006700 versus estimated uncached mean $0.018478, maximum $0.039626 | The same local traces still pass the $0.03 mean G7 limit without cache. Broaden workloads and error conditions. Prices are the v003 table, not independently verified historical tariffs. |
| About 40k tokens is a compaction trigger, not a strict serialized-request ceiling | Current conversation policy can retain recent messages and tool/schema content beyond that trigger | Measure the entire request. The proposed 1–1.8M input tokens over 45 turns is a scenario estimate, not measured production usage. |
| Agent execution intervals overlapped, with a measured peak of 14 | Reviewed production timestamps | This is not a measurement of simultaneous inference requests, and does not establish 30 concurrent requests or a rate-limit cause. |
| **The fallback model carried most production inference** (step-0 result, 2026-10-01) | OpenRouter daily export by model: DeepSeek V4 Pro 0813 appears **only on 2026-10-01 (UTC)** — 30.2M prompt, 437,177 completion tokens; none before. None of the 33 local trials since 2026-09-30 17:00 PDT called it (runtime logs). So 0813 usage is attributable to the v003 screening, ≈ 1.2M prompt / 17k completion tokens per cost-reported run. Daily granularity, not per request | Completion alone at the v003 table price ($4.20/M) is ≈ $1.84 of the $3.68 reported. Uncached, 30.2M prompt tokens would cost $14–20, far above the bill, so its prompts were **mostly cache hits** (roughly 85–95%). Cause = expensive fallback + long runs, **not cache loss**: A1a first; A3 less urgent. Luna's Oct 1 tokens mix local and production and cannot be split by day. A second, 3-hour export covering the screening window holds **all** 437,177 DeepSeek 0813 completion tokens, 105,069 Luna completion tokens, and **no DeepSeek 0423** (the other key user was idle then, so the window is not contaminated by it). If no local trial overlapped the window, ≈ 81% of production completion tokens came from the fallback; the export's exact start time decides whether the v003 held-out run (started 04:42 UTC) contributed Luna tokens. |
| Another client uses the same key | DeepSeek V4 Pro 0423 (8,405 completion tokens on 09-30, 73,324 on 10-01) is never requested by Quarry; also the unexplained key-usage gap during the E010 run | Identify and stop it, or move bench and production to dedicated keys, before attributing any shared-key costs. |
| An 80% screening threshold is plausible | Stopping after seven failures makes 24/30 unreachable, but does not uniquely establish the platform rule; the public docs only quote competition 23 (45%) | Treat ~80% (24/30) as the working assumption and aim for 27/30. To verify: ask in the Ridges miner channel, or compare the pruning point of other agents' screener-1 records. |

**Working hypothesis:** transient primary-model failures lead to persistent fallback, more expensive requests, and less time or budget for a patch. The routing defect is confirmed in code, and the step-0 export confirms the fallback carried most production inference. Still unconfirmed: *why* the primary failed (429, 5xx, timeouts) and how many runs switched — no per-request data. Deadline overruns, temporary reservation refusals, and exceptions remain additional explanations, especially for the six error-1000 results.

The v003 price table makes the configured DeepSeek fallback 2.4× the primary's uncached input price and 3.5× its output price. That does not imply every complete run costs 3–4× more: token mix, caching, retries, and behavior differ.

## 3. Acceptance criteria declared before runs

| Check | Target | Interpretation |
|---|---|---|
| Screening rehearsal | **Pass criteria are robustness:** at most one no-patch outcome; no exception terminations; no run past its absolute deadline; no permanent model switch; cost targets below. Solve rate (aim ≥ 27/30) is **reported, not gating** | Local solve rates do not predict screening (dev 51/51, NetBox 17/18 locally vs 18/30 in production on different tasks), and only 23 distinct non-held-out tasks exist. Report distinct tasks and repeat counts. |
| Rehearsal cost | Attributable mean ≤ $0.04 and maximum ≤ $0.10 per task | Separate successful, failed, and unresolved attempts; missing billing cannot pass cost approval. These are targets, not provider-enforced billing guarantees. |
| Reliability | No new agent mechanical failure, no unexplained loss of an available candidate patch | The existing mechanical-failure rule still blocks promotion even if the aggregate no-patch allowance is met. |
| Behavioral comparison | Existing §5a protocol | At least one additional task solved 3/3, or comparable cost ≤ 85% of baseline while preserving covered tasks; no confirmed regression or new mechanical failure. |
| Held-out G7 | Complete three-trial cohort on the exact frozen bundle; existing declared solve, cost, and mechanical targets | The existing v003 target was ≥ 50% solved, zero mechanical failures, and mean ≤ $0.03. G7 runs **without fault injection**; the rehearsal's $0.04 target applies **under injected faults**, so the two limits measure different conditions and the rehearsal does not relax G7. |
| Cost stress reporting | Uncached estimate, cache-write stress where applicable, peak request estimate, and accounting coverage | Report estimates separately from billed cost. Declare any new stress threshold in the spec before viewing candidate results. |

The fault matrix also includes intentionally unrecoverable cases, such as a hard spending cap before any edit. Such cases must terminate correctly; they are not expected to solve the task. Keep this diagnostic matrix separate from the declared 30-slot solve-rate cohort. Never remove inconvenient failures from that cohort after the run.

## 4. Requirements and work items

The IDs below refer to the current [harness spec](../specs/harness.md) and [bench catalog](../specs/bench-catalog.md). Several requirements need revision; this plan does not silently change their current wording. Register additions and revisions, with requirement-named tests, before implementation. All work items below remain pending.

| Item | Requirement mapping | Classification / dependency |
|---|---|---|
| A0 — Whole-operation deadlines | H-LLM-07, H-LOOP-05, H-SHELL-03/07/11/12 | Mechanical; first |
| A1a — Routing defect: no permanent fallback; error classification | Revise H-LLM-02/03 and H-WALLET-04; extend H-LLM-06 | **Reliability fix** (deterministic regression tests + no regression under §5a's reliability row); depends on A0 |
| A1b — Routing policy: retry counts, cooldown, fallback choice | H-LLM-02/03 | Behavioral; §5a comparison; after v004 minimum unless the step-0 export shows fallback dominated the screening window |
| A2 — Request and session accounting | H-WALLET-01/02/03/05/06, H-LLM-06/08 | Accounting plus separately evaluated spending policy; before live concurrency |
| A3 — Conversation size and prefix stability | Revise H-LOOP-03; H-LLM-05/08 | Behavioral; depends on A2 measurements |
| B1–B3 — Progress and candidate hand-off | H-LOOP-01, H-SHELL-03/07/08/10/11/12/13; add explicit progress requirements | Prompt/phase behavior plus mechanical hand-off tests; depends on A0/A2 |
| C1 — Deterministic fault harness | B-RUN-01/02/04; new fault-scenario requirements | Offline support for A/B |
| C2–C3 — Concurrency and attributable reporting | B-RUN-01/03/04, H-WALLET-06; new reservation/attribution requirements | Accounting and resource isolation before paid concurrent trials |
| C4 — Rehearsal and release gate | B-RUN-03/05 | Depends on retained A/B changes and validated C1–C3 |

### A0. Enforce absolute deadlines

- Use one monotonic absolute deadline through connection setup, successful and error response-body reads, retries, backoff, tools, and bounded cleanup.
- Bound total response size as well as time. A server that keeps sending small chunks must not extend the whole operation indefinitely.
- Reserve sufficient time for candidate extraction and repository restoration; launching a long check must not consume hand-off time.
- Preserve possibly billed reservations on ambiguous timeout or response loss. A client deadline does not prove the provider stopped work or charged nothing.
- Tests: fake-clock attempt/backoff boundaries; real local HTTP slow-body reproduction for success and error paths; deadline during tool work; existing candidate survives timeout and can be applied to the restored tree.

### A1. Recover from transient errors without persistent fallback

Split for classification (§5a): **A1a** is the defect — failure counters persist across calls and a successful fallback never lets the primary recover, so two transient primary failures move the rest of the run to the fallback. Fixing that (per-call retry counts, bounded cooldown, primary recovery probe, error classification) is a reliability fix with deterministic tests. **A1b** is the policy — retry counts, cooldown length, which fallback (if any) — and is behavioral. The bullets below cover both; the A1a tests are the first five in the test list.

- Distinguish 429, retryable 5xx, temporary reservation exhaustion, hard budget caps, invalid credentials/requests, and ambiguous transport failures using status and structured error fields. Avoid classifying an arbitrary mention of “budget” as a terminal spending cap.
- Extend the transport result to expose headers. Honor `Retry-After` within the remaining absolute deadline and bounded retry allowance; never sleep past finalization time.
- Scope retry counts to a logical call. Track bounded cooldown/recovery state separately so a successful fallback cannot permanently disable the primary, while an unavailable primary is not hammered on every turn.
- After cooldown, permit a bounded primary recovery probe. Record the transition and reason. Freeze retry counts and cooldown settings before comparison runs.
- Evaluate primary-only bounded retries against a measured fallback configuration. A fallback may be more expensive if its complete request reservation fits the remaining budget and evidence justifies it. “Always cheaper” is not sufficient evidence of useful recovery.
- Tests: primary failure then success; exhausted primary attempts then fallback; primary recovery after cooldown; persistent primary outage; fallback failure; unaffordable fallback; bounded temporary 402 recovery; immediate hard-cap termination; malformed errors and headers.
- Log requested/actual model when available, attempts, status/error class, switch reason, latency, and reservation outcome without keys or prompt content.

### A2. Account for the complete request and protect finishing budget

- Maintain dated, sourced input/output/cache-read/cache-write prices for each allowed model. Validate current model availability, pricing, and proxy compatibility before a live comparison; do not silently inherit an old table as current truth.
- Estimate the full serialized messages and tools plus reserved output using the model actually dispatched. Each retry or fallback receives its own reservation.
- Use **uncached input prices** for the conservative no-cache guard. A transcript formula based on cached prices cannot bound uncached spending. Account for cache-write charges where applicable and token-estimation error.
- Make the guard **adaptive** rather than permanently uncached: plan turns with the expected (cached) price, measure each call's reported cache share, and switch to uncached sizing — earlier compaction or finalization — once misses appear. Locally ~92% of prompt tokens are cache reads; always assuming 0% would make every run needlessly conservative. Missing cache fields count as misses for this guard.
- Keep reported cost, usage-based estimates, and unknown costs separate. Unknown attempts retain their reservations until evidence permits reconciliation; missing cache data is not zero cache hits.
- When another exploration turn threatens finishing headroom, compact or finalize before dispatch. Handle unexpectedly high actual charges explicitly; an estimate is not a billing guarantee.
- The current driver allocation is already approximately `0.9 × 0.85 = 0.765` of the full cap. Make a usable finalization reserve within the phase allocation instead of blindly subtracting another 20% and stranding more budget.
- Tests: tool/schema-heavy requests; expensive fallback; all-cache-miss requests; cache writes; missing usage; response loss followed by retry; output reservation; actual overrun; finalization can spend its reserved allowance.

### A3. Bound conversation cost while preserving useful context

- Measure request bytes/tokens and unchanged-prefix length before adding ID rewriting: Quarry already stores tool-call IDs and reuses them. Keep call/result correspondence intact.
- Use hysteresis: compact in meaningful steps with explicit trigger and lower target, rather than rewriting old content a little every turn. Treat 40k → 20k as an experimental configuration, not a fixed requirement.
- Preserve the statement, current candidate state, relevant failures, and recent tool-call/result pairs. Keep unchanged messages byte-stable between compactions.
- Choose the request cap from uncached cost, remaining budget, output allowance, model context limit, and a conservative token estimate. Cache savings are measured upside, not required for affordability.
- Test prefix stability, tool-pair validity, oversized recent results, complete request sizing, and bounded compaction frequency. Compare task outcomes and costs under §5a; fewer tokens alone is not acceptance.

### B1–B3. Reach a useful edit and preserve it

- **B1 — Progress:** when no candidate exists by a predeclared turn/time/spend threshold, add one concise instruction to make an evidence-backed edit or identify the specific missing evidence. Test the proposed 25% threshold; never force an arbitrary edit just to avoid an empty diff.
- **B2 — Finalization:** make the transition explicit and reachable before hard exhaustion. Use the reserved allowance to finish a candidate, run affordable statement-derived checks, extract the complete patch, and restore the working tree. Do not rerun a known slow check unchanged until the deadline expires.
- **B3 — Empty finish:** if time and budget remain, allow a bounded recovery attempt when the model finishes with no candidate. At a hard cap or deadline, return the best available candidate under the existing eligibility/last-resort policy, or record an honest no-patch result.
- An edit does not guarantee a valid patch: it may be reverted, out of scope, or incomplete. Preserve a complete candidate and its check evidence; do not construct an arbitrary partial-file patch at hand-off.
- Tests: long exploration; finish before edit; edit followed by timeout/exception/budget refusal; reverted edit; candidate requiring multiple files; check timeout; no candidate and no remaining budget. Assert applicability and repository restoration where a valid candidate existed.

## 5. Bench changes and experimental design

### C1. Deterministic faults first

Build a local test transport/proxy with named scenarios and fixed seeds: 429 with `Retry-After`, transient 5xx, temporary 402, hard 402, invalid credentials, slow body reads, malformed success, and response loss. Keep model traffic within the existing proxy path.

Separate faults injected **before forwarding** (no provider request) from faults injected **after forwarding** (possibly billed). Record which occurred. A random “5% error” switch is optional later; it cannot replace reproducible boundary scenarios.

Use scripted responses and fake clocks for most offline tests, with the local HTTP regression for transport timing. Paid tests begin only after offline correctness and accounting checks pass.

### C2. Concurrency without corrupting trials or billing

The reviewed [Ridges miner FAQ](https://docs.ridges.ai/guides/miner-faq) warns against multiple simultaneous `run-local` instances because Docker resources can collide. Start with concurrent inference-client/proxy tests and run full repository trials serially.

Full-trial concurrency is a later experiment, conditional on unique runtime resources, sufficient measured CPU/memory/I/O headroom, independent cleanup, and compatible result capture. Core count alone does not justify six to eight Docker trials. Measure request overlap separately from agent execution overlap.

Before any concurrent paid workers:

- Attribute requests to trial IDs using generation/request IDs and provider usage metadata. Overlapping per-trial key-balance deltas double-count shared spending and cannot establish trial costs.
- Reconcile attributable request totals against one isolated batch's key usage, recording reconciliation delay and any discrepancy.
- Reserve worker allowances atomically in the shared session ledger; preserve crash/restart and unknown-attempt reservations. Do not simply remove the existing ledger or key locks.
- Verify that the dedicated bench key has no unrelated usage. A separate key improves attribution but does not necessarily isolate account-level or provider-level quotas.

### C3. Required reports

Record bundle/task/runtime identity, trial and attempt IDs, fault scenario/seed, execution and request overlap, outcome, termination reason, first-edit time/turn/spend, patch applicability, check status, model mix, retry/switch counts, input/output/cache fields and coverage, per-attempt cost provenance, peak estimated turn cost, and actual/estimated/unknown totals.

Report mean and maximum trial cost, no-cache counterfactuals, and applicable cache-write stress estimates. Fallback share is a diagnostic, not an arbitrary pass threshold: a useful recovery call must not fail a gate merely because it used fallback.

### C4. Rehearsal, comparison, and held-out separation

- Freeze a 30-slot rehearsal manifest before running: task versions, distinct-task count, repeat allocation, fault schedule, route settings, cost targets, and validity/replacement rules. Include long-context and delayed-edit cases beyond the small local workloads that already pass uncached repricing.
- Repeated trials are not independent task coverage. If the available validated development set has fewer than 30 distinct tasks, state that limitation rather than calling 30 runs “30 tasks.”
- Exercise concurrency initially at the inference/proxy layer; label full-task rehearsals as serial until C2 proves safe isolation. Do not claim production concurrency has been reproduced by a serial run.
- Keep dev/rehearsal data separate from held-out evidence. Existing held-out cases remain useful regression checks, but cases used to tune changes become dev cases; obtain a fresh independent holdout when needed.
- Compare behavioral changes using [engineering-loop §5a](../process/engineering-loop.md): three planned trials per version on matching inputs, immediate rejection of material regressions, and at most one paired confirmation block for other drops. Missing evidence leaves the decision pending.
- Routing, prompts, compaction, and new phases are behavioral changes even when motivated by reliability. Keep mechanical deadline/accounting fixes independently testable and report each experiment's classification.

## 6. Execution and release checklist

0. **Billing export (gates the order of A0/A1/A2) — done 2026-10-01 at daily granularity.** Export per-model usage from OpenRouter Activity (CSV works with prompt logging off). Result in §2: the fallback dominated production, so A1a leads. If a per-request export for 05:50–06:10 UTC Oct 1 becomes available, add it to the incident archive (status codes and switch timing per run); it is not required to start.
1. **Preserve the incident.** Archive the production response and available per-generation billing metadata for the exact screening window. Update v003's screening status and calibration entry without replacing local evidence. Do not enable prompt/response content logging or store API keys.
2. **Register requirements and regressions.** Add the A0/A1/A2 reproductions and C1 fixtures. Revise conflicting 402/routing requirements explicitly before implementation.
3. **Fix mechanical defects.** Complete deadline enforcement, accounting, and candidate hand-off protections. Pass focused tests and G0–G5, including bundled Python 3.9 execution and firewall/prescreen lint.
4. **Evaluate behavior in small changes.** Test routing first, then transcript/progress policies as separate experiments where feasible. Use frozen comparable dev and public cohorts, including the six-task NetBox cohort where runtime compatibility is established. Apply §5a and log retained/reverted changes.
5. **Validate attribution and rehearse.** Complete C2's client/proxy concurrency checks, then C4's declared cohort within available spending headroom. Full Docker concurrency remains conditional. Meet the targets in §3 without hiding unresolved costs or mechanical failures.
6. **Freeze v004.** Record source revision/patch, model configuration, task identities, and full bundle hash. Run G0–G5 and held-out G7 against that exact upload file with three valid trials per task and no unresolved attempts. A code change after freezing requires new applicable evidence.
7. **Check upload prerequisites.** Verify current competition, endpoint, quote, cooldown, model access, and full-file firewall acceptance through supported checks. Use the controlled wallet and uncompromised hotkey, with a dedicated production runtime key. Check required funds and key headroom without exposing credentials.
8. **Promote and submit only after gates pass.** Create the release manifest/evidence and update `submissions/READY`. Preserve the quote ID, payment block/index, and agent ID. If a paid upload is interrupted, recover using its receipt rather than initiating another burn.
9. **Calibrate after submission.** Save stage-specific results and costs under v004, distinguish screening from validator scoring, and compare observed production behavior with the rehearsal predictions.

## 6a. v004 minimum release (line drawn 2026-10-01)

The leaders release new versions every few days and each upload costs a 12-hour cooldown, so v004 ships the smallest change set that removes the confirmed failure:

| In v004 | After v004 |
|---|---|
| Step 0 export (done) and step 1 incident archive | A1b routing policy tuning (retry counts, cooldown, fallback choice) |
| A0 absolute deadlines | A3 transcript size and compaction policy |
| A1a routing defect + error classification (reliability fix) | B1 first-edit pressure (prompt change) |
| B2/B3 finalization and candidate hand-off | C2 full-trial concurrency |
| C1 deterministic fault tests, offline | C4 30-slot rehearsal |
| Reliability check against the promoted dev and public baselines (no regression) | Further behavioral experiments (§8) |
| G0–G5, firewall lint, G7 on the frozen bundle (no fault injection) | |

The adaptive cost guard (A2) joins v004 only if its tests are ready without delaying the items on the left; otherwise it is the first item after v004.

## 7. Spending and schedule

Re-estimate after the offline work and first measured pilot. The original $1.5–2 total and seven-hour run estimate do not account adequately for paired baselines, repeats, confirmations, and uncertain retries.

| Illustrative workload | Assumption | Estimated inference |
|---|---|---|
| One 30-run rehearsal | $0.04 mean | $1.20 |
| Same cohort at the proposed $0.10 per-run target ceiling | 30 × $0.10 | $3.00; this is not an enforced spending allowance |
| Baseline and candidate, 30 tasks × three repeats each | 180 runs × $0.04 mean | $7.20 before confirmations and diagnostics |
| Hypothetical production schedule of 210 runs | Every run reaches $0.29 | $60.90 before upload fees; actual stage counts and caps must be verified |
| Expected production schedule (for funding the production key) | 30 screener-1 + 30 screener-2 + 150 validator runs at $0.05–0.10 | ≈ $10–21; the leaders' observed stage costs are $0.03 (screening) and $0.06–0.10 (validators) |

Use the existing shared local spending ceiling and remaining ledger headroom; this plan does not increase it or automatically raise a production key limit to $30. Reserve each live block before scheduling it, retain ambiguous charges, and reconcile before freeing headroom. A $30 production limit is a funding choice, not proof that every possible evaluation stage fits.

Upload fees are separate and depend on the current quote. Engineering and wall-time estimates remain provisional until offline tests, a resource pilot, and measured task durations establish a schedule.

## 8. Reference study, later work, and housekeeping

The [three-reference review](../reviews/public-agent-study-20261001/three-reference-review.json) and [five-public-agent study](../reviews/public-agent-study-20261001/analysis.json) are study material. Their similar implementations provide correlated observations, not independent proof of which feature improves performance. Older public versions do not reveal the behavior of newer hidden versions.

Corrections to retain when discussing the references:

- The value 50 is used in a transcript-sizing formula; it is not evidence that a 50-turn planning pass runs. The inspected planning feature defaults to disabled.
- Fallback configuration differs between the inspected agents. Source defaults do not establish their production configuration.
- Deterministic IDs and cached-price transcript formulas do not guarantee cache hits or an uncached spending bound.
- Screening results and final validator scores are different measurements; compare costs within the same stage.

After reliable screening performance, consider a short read-only planning pass, statement-derived patch-shape checks, and equivalent development cases for observed weaknesses. Each behavior change gets its own paired experiment. Never copy reference code, prompts, or constants into `src/`; derive our own requirements and implementation.

The extra-fix-round experiment is **E010**, currently parked, despite its historical run log calling it E008. Its cost attribution was suspect and no paired confirmation was completed. Do not claim it proved higher cost without more solves. E008 in the experiment register is task-authoring work.

Housekeeping includes recording v003's failed screening, preserving reference provenance, identifying unrelated OpenRouter key use, and maintaining the calibration table. Keep credentials and recovery phrases outside repository records.

## 9. Completion record

| Stage | Status | Required evidence |
|---|---|---|
| Plan correction | Documented | This plan and linked review artifacts |
| Step 0 billing export | Done (daily granularity) | [openrouter-daily-by-model.csv](../reviews/public-agent-study-20261001/openrouter-daily-by-model.csv); §2 step-0 row |
| Incident archive / requirement revisions | Pending | v003 production record; revised spec IDs |
| A0 inference transport and A1a | Implemented and corrected after [review](../reviews/2026-10-01-a0-a1a.md) (E012); corrected-build no-regression baseline check pending | 40 focused cases; deadline, classification, retry and telemetry corrections. See review for current gate results. Broader tool/cleanup deadline coverage remains with B2/B3; the earlier live diagnostic measured the previous build. |
| B2 and B3 | Implemented (E013), corrected after [review](../reviews/2026-10-01-b2-b3.md); finalization events logged. Check of the pre-review build `ca8e92f3` (E014): NetBox no regression; dev **material regression** on py-django-n-plus-one (3/3 → 1/3; v003 bundle 3/3) → revert that build. Corrected build pending a diagnostic and its own comparison (behavioral, §5a) | `tests/unit/test_finalization.py` (16), G0–G5 (98/98) |
| A2 and C1 | Pending | Focused regressions, accounting proof, G0–G5 |
| A3 and B1–B3 experiments | Pending | Compatible paired comparisons and keep/revert decisions |
| C2–C4 | Pending | Attribution/isolation evidence; declared rehearsal results |
| v004 freeze / G7 | Pending | Exact bundle hash, complete held-out evidence, release checks |
| Upload / production calibration | Pending | Receipt, agent ID, stage results and costs |
