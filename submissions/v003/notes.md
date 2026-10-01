# v003 — reliability fixes and firewall-safe submission

**Uploaded successfully:** agent `3cb91034-fe6f-5271-94be-c8be974fefdf`, hotkey `5F75YfqeRcywNW7LR8HD1AHqzRhjMdfLR9HtBVN63JcD3GCB`. Payment receipt saved in `manifest.json` from the user-provided CLI success output. Validator status and score are not yet checked.

Frozen bundle: `060edea3568360c90aea234bf5227257c79a3e9926b8cd7275ec24af1dfeae1c`.
Base revision: `668138a`, plus the runtime patch preserved in `evidence/source.patch`.

Changes from v001:

- Baseline checks share one time budget, leaving time for editing and patch handoff. A minimum timeout cannot extend the deadline.
- Malformed HTTP 200 model responses retain their potentially billed reservation; any reported usage is still charged to the local budget.
- SQL-function examples use the firewall-safe prose already introduced by revision `668138a`.
- The default models and two fix rounds are unchanged. The extra-fix-round experiment is not included.

Offline validation: 221 tests, Ruff, Python 3.9 import, bundle end-to-end tests, lint, originality against 11 public agents, and 94/94 requirement links passed. The tested build is byte-identical to this file. See `evidence/offline-gates.json`.

The unsigned multipart check reached the Ridges API and returned HTTP 422 for missing authentication fields. This demonstrates that the exact file passed Cloudflare at that time; it does not certify authenticated admission. No agent or payment was created. See `evidence/firewall-check.json`.

Live validation **passed**: `bench/runs/20260930-214235-heldout` completed all 21 trials with 17 solved, zero mechanical failures, no unresolved trials, and all 21 costs reconciled. Mean cost was $0.006700 (total $0.140696); median wall time was 120 s. The predeclared target remains at least 11/21 solved and mean cost at most $0.03. The historical `2b2d1281` comparison returns **keep** under the reliability-change rule: identical per-task outcomes, no regressions, and no extra confirmation block required. No task contents or target were changed.

Five tasks solved 3/3, ClickHouse skip-index solved 2/3, and the expression-index task solved 0/3, matching v001. The failures are retained in the packaged CSV. See `evidence/submission-gate.json`, `evidence/comparison.json` and `evidence/heldout/` for the exact measurements.

Recheck the full gates against the packaged evidence with:

```bash
uv run --no-sync python tools/submission_gate.py --with-gates submissions/v003 submissions/v003/evidence/heldout
```

Only a passing release may be selected by `submissions/READY`. The following commands describe the original upload workflow; this release is now marked uploaded, which blocks another payment:

```bash
bash tools/ridges_submit.sh preflight
RIDGES_WALLET_NAME=YOUR_CURRENT_WALLET bash tools/ridges_submit.sh upload
```

The default hotkey is `ridge-miner-v2`; set `RIDGES_HOTKEY_NAME` if necessary. Confirm the selected wallet controls the intended registered hotkey after any wallet migration. Enter keys and wallet passwords only in the local hidden prompts. Record the quote ID and returned agent ID; use the helper's `resume` command with the same release if a paid upload is interrupted.

Local results are calibration evidence, not validator results. The seven held-out tasks were not authored in a fresh session. The upload receipt is recorded; validator metrics remain empty until results are available.
