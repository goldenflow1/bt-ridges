# Freight dashboard shows the wrong depot after a scan backfill

Dispatch operators report that importing older scans can move a parcel backwards on the carrier dashboard. Repair the current-scan query in `/app`.

Change only the body of `current_scans` in `freight/repositories/tracking.py`. Keep its signature and docstring, existing imports, neighboring functions, and every other file unchanged. Follow the existing SQLAlchemy expression API; raw SQL is not allowed. Do not alter schemas, data, tests, configuration, or database settings, and do not introduce file, process, network, dynamic-code, or transaction-commit side effects. The complete edited file must remain below 15,000 Unicode characters.

The required contract is:
- A carrier sees only its own parcels. Parcels with no scans contribute no row; an empty carrier returns an empty list.
- Each scanned parcel appears exactly once, including parcels with just one scan.
- Current means greatest `recorded_at`, regardless of insertion order or scan ID. When event times are equal, greatest scan ID wins. Timestamps use their full stored precision and represent instants, including equivalent time-zone offsets.
- Return the existing `parcel_id`, `scan_id`, `recorded_at`, `depot`, and `condition` fields from that same winning scan, preserving their Python types and values. Return rows by ascending parcel ID.
- Keep the unrelated timeline and volume-report behavior unchanged. Use one read-only database query for `current_scans`; do not fetch all historical scans to choose winners in Python or cache results across calls.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache freight/repositories/tracking.py
```
