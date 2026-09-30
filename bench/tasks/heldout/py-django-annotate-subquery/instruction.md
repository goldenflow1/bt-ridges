# Add future open-appointment counts to the clinic roster

Scheduling staff can see approved session minutes, but the roster's open-appointment column is still a placeholder. Implement it in `/app` without disturbing the existing allocation totals.

Change only the body of `doctor_workload` in `clinic/repositories/workload.py`. Preserve its signature and docstring, existing imports, neighboring functions and every other file. Use Django ORM expressions; no raw SQL or Python queries per doctor. No schema, data, test, configuration, file/process/network, dynamic-code or transaction-commit side effects. The complete edited file must remain below 15,000 Unicode characters.

The contract is:
- Return a lazy Django queryset for all doctors in the requested clinic, ordered by `display_name` ascending and then unique doctor ID ascending. Include doctors with no appointments or sessions.
- `open_appointments` counts only that doctor's appointments whose state is exactly `open` and whose `starts_at` is at or after the supplied aware `as_of` instant. An appointment exactly at the boundary is included. Other states and earlier appointments are excluded. Equivalent time-zone offsets mean the same instant.
- With no matching appointments, the annotation is integer `0`, never `None`; every count must be a Python `int` when evaluated.
- Preserve `approved_minutes`: sum approved session minutes once per session, or integer zero if none qualify. Multiple appointments must not multiply session minutes, and multiple sessions must not multiply appointment counts.
- Evaluating the roster uses exactly one read-only query for one doctor or many doctors. Use a correlated count annotation with an integer output type and a zero fallback; do not load appointments or loop over doctors to count them. Results must reflect writes committed before the next call, without persistent caching.
- Keep calendar and administrative summary behavior unchanged.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache clinic/repositories/workload.py
```
