# Repair customer eligibility exclusions

Work in `/app`. Repair only the body of `eligible_customers()` in `app/reports.py`, preserving imports, signature and docstring. Import jobs may create block records with a NULL customer ID; after these imports, unrelated customers disappear from the result.

Return ascending customer IDs for the requested tenant, excluding customers with at least one active block for that same tenant which has no expiry or expires strictly after `as_of`. A NULL block customer ID matches nobody. Expiry exactly at `as_of` is expired; inactive and other-tenant blocks have no effect. Duplicate blocks must not duplicate or remove unrelated rows.

Use Django ORM and one database query, with exclusion performed in PostgreSQL. No raw SQL, Python filtering, writes, caching, or external side effects. Do not change models, schema, tests, configuration or other files.

Use only the imports already present; do not add imports.

The complete `app/reports.py` file must contain fewer than 15,000 Unicode characters (code points), including imports, docstrings and whitespace. Newlines are counted after text-mode normalization to a single LF character.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache app/reports.py
```
