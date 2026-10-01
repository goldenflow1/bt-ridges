# Submissions

One folder per upload (`vNNN/`): `agent.py` byte-for-byte as uploaded, `manifest.json`, `notes.md` (architecture §21.3). Gate before any upload: `uv run python tools/submission_gate.py --with-gates submissions/vNNN bench/runs/<heldout run>` (G7, B-RUN-05).

## Calibration

| Version | Held-out local | Validator score | Ratio | Local $/task | Validator $/task |
|---|---|---|---|---|---|
| v001 | 0.81 (17/21) | — | — | $0.0061 | — |
