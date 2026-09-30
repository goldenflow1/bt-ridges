# Parcel Trace

Freight operators use the carrier dashboard to inspect a parcel's current depot and condition. Imported historical scans retain arrival order as their database IDs; recorded_at is the event time.

`freight/api.py` serializes the dashboard, `freight/service.py` composes current state with the existing volume report, and `freight/repositories/tracking.py` owns query construction. `freight/repositories/history.py` serves a separate timeline endpoint. Database mappings and presentation rules live in separate modules.

Local development data uses the PostgreSQL service. Run `pytest tests/test_visible.py` for the public contract checks.
