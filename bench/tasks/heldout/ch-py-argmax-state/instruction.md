# Regional meter panel retains disconnected and relocated meters

An electricity utility's operations panel sometimes shows a meter online in a region after it disconnected or moved. Trace and repair the reporting path in `/app`.

The editable area is the existing Python files in `grid/reports/` (`__init__.py` is not editable). The faulty function is not specified. Keep public function names, signatures and return annotations, existing imports, all files outside that area, and the source-tree paths and modes unchanged. Private helpers inside the allowed files are permitted. Do not alter the transport, API, schemas, data, tests or configuration. Reports may only call the existing `client.query` API: no DDL, inserts, direct HTTP, file/process/network, dynamic-code or global-cache side effects.

Required behavior:
- The panel selects meters belonging to the requested utility. A meter's identity is its utility plus meter ID.
- Current state is the event with greatest `observed_at`; if event times tie, greatest `version` wins. Event time takes precedence over version and ingestion order. If both values tie, stored events have identical payloads.
- Determine the current event before selecting online meters in the requested region. An old online event must not resurrect a disconnected meter. A meter that moved region belongs only to its current region.
- Each selected meter appears once, ordered by meter ID ascending. Include meters with a single event. Empty selections return an empty list.
- Preserve the winning event's `meter_id`, `state`, `region`, `reading`, `version`, and `observed_us` (UTC Unix microseconds). Numeric fields are integers; zero and negative readings are valid. Full timestamp precision matters.
- Utility and region strings are bound parameters, including strings containing quotes. The connection-panel path must use one read-only query and return only selected current rows from the database, not load history to deduplicate/filter in Python. Calls reflect newly stored events without persistent caching.
- Preserve the separate event-count report.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache grid/reports
```
