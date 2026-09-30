# Repair the missing-device event report

Work in `/app`. Trace the missing-event report from observatory/report.py. You may change that production file only; do not change its public signatures.

The missing-device event report returns no events even when a tenant has unknown devices. Trace and repair it. Each event is missing when **no enabled registration with the same tenant and device string** exists. There is at most one registration per `(tenant, device)`. Disabled registrations do not count. Return each missing event as `{"event_id": integer, "device": string}` ordered by event ID. Device identifier `0`, empty labels and an empty device string are legitimate registered values. Do not treat them as evidence of absence. Keep tenant input parameterized.

Keep query work in ClickHouse through `client.query()`. The report must not write data or change the schema. Do not add imports, cache answers, or edit the client, tests, configuration or any other file. The development database is seeded; the separate test database may be used for local investigation.

Run these checks before finishing:

```bash
pytest tests/test_report.py
ruff check --no-cache observatory/report.py
```
