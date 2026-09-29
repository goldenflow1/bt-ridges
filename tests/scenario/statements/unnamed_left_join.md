# Teams without members disappear from the report

The team roster report should list every team with its active member count.
Teams whose members are all inactive are missing from the response entirely.

Find the query that builds the roster and change only that function. Keep its
signature. Do not add raw SQL, and do not change tests or fixtures.

Also run `ruff check` on the file you changed, and `pytest tests/test_roster.py`.
