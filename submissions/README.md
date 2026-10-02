# Submissions

One folder per upload (`vNNN/`): `agent.py` byte-for-byte as uploaded, `manifest.json`, `notes.md` (architecture §21.3). Gate before any upload: `uv run python tools/submission_gate.py --with-gates submissions/vNNN bench/runs/<heldout run>` (G7, B-RUN-05).

`v001` is retired: its historical 17/21 result remains valid for those bytes, but the updated lint rejects its SQL-call text. The firewall-only v002 evaluation stopped before completing; no v002 release was approved. **v003 is uploaded** (agent `3cb91034-fe6f-5271-94be-c8be974fefdf`; success receipt recorded from the CLI): its deadline/accounting fixes passed 221 offline tests, G0–G5, the reliability comparison, and a fresh 21-trial G7 evaluation. All evidence needed for preflight is packaged with the release.

The upload helper reads `submissions/READY`. It checks the selected manifest, agent checksum, packaged held-out evidence checksums and G7 before opening the paid uploader. A missing pointer or failed gate blocks uploading. Use `bash tools/ridges_submit.sh preflight` without keys or funds. For upload, explicitly set `RIDGES_WALLET_NAME` to your current wallet; use `RIDGES_HOTKEY_NAME` if its hotkey differs from `ridge-miner-v2`. Do not paste recovery phrases, wallet passwords or API keys into chat.

The v003 manifest now has status `uploaded`, so the helper blocks another paid upload of this release. Its payment receipt is saved in `v003/manifest.json`. Validator status and score have not yet been checked.

## Calibration

| Version | Held-out local | Validator score | Ratio | Local $/task | Validator $/task |
|---|---|---|---|---|---|
| v001 | 0.81 (17/21) | — | — | $0.0061 | — |
| v003 | 0.81 (17/21) | — | — | $0.0067 | — |
| v004 | 0.76 (16/21) | — | — | $0.0065 | — |
