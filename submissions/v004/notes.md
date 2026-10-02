# v004 — screening recovery

**Bundle** `5406e4dd` (source: `src/` at `a2bbc42`, rebuilt byte-identically by `tools/build.py`).

**What changed since v003** (`060edea3`, failed screening 1: 18/30, six no-patch runs at ≈ $0.19):
- **A1a — routing defect fixed (E012):** two transient primary failures no longer pin a run to the expensive fallback (DeepSeek V4 Pro 0813 carried most of v003's production inference). Failures counted per call; 60 s primary cooldown with recovery probe; temporary vs hard budget refusals; Retry-After within the deadline.
- **A0 — whole-exchange deadlines (E012):** connect, send and body reads bounded by one deadline; truncated and oversized bodies rejected.
- **B2/B3 — finalization (E013):** wrap-up notice at the finishing reserve, one refused empty `finish`, a finalization round on the reserve when no candidate exists.

**Evidence:**
- E016 (synthetic budget pressure ×25, 102 paired trials + confirmation): B2/B3 **keep** — 2 tasks newly 3/3, the one drop not reproduced; limits recorded with the experiment.
- Normal conditions vs promoted baselines: dev 50/51 (baseline 51/51), NetBox 16/18 (17/18); no material regressions; dev cost $0.0058 vs $0.0097 per trial. ch-py-tz-buckets drop not reproduced in its confirmation block (v004 3/3, baseline 2/3).
- **Exception (user decision, 2026-10-01 18:07 PDT):** the prefix-hierarchy confirmation block (NetBox, 2/3 → 1/3) was stopped after 1 of 6 trials to ship sooner; that drop is **unconfirmed**. The task has varied between 1/3 and 2/3 on every bundle.
- Held-out G7 on this exact file: see manifest (`local.heldout`).
- Upload firewall: whole file reaches API validation (evidence/firewall-check.json).

**What to expect:** routing should keep production on the primary model, so cost per task should fall toward the local scale; screening 1 needs ≈ 24/30 (inferred). This is the first production test of A0/A1a/B2/B3.
