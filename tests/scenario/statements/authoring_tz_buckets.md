# Author daily signup buckets

The `daily_signups()` helper currently returns an empty list. Implement it so the
growth chart gets one row per day in the organisation's time zone.

Work in `/app`. Limit production changes to `growth/queries.py`, specifically
`daily_signups()`. Use only names the file already imports.

- days use half-open ranges `[start, end)` in the organisation's time zone;
- days without signups are present with count `0`;
- results are ordered by day ascending.

Write the function as a single ClickHouse query: no Python loops or
comprehensions.

```bash
python -m pytest tests/test_growth.py -q
```
