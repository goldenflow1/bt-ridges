# Repair distinct counts

Counts include duplicates. Limit changes to `app/counts.py`, specifically
`Counter.distinct_users()`.

Run `python app/manage.py test app.tests.CountTests
--keepdb --noinput` and `ruff check --no-cache app/counts.py` before
finishing.
