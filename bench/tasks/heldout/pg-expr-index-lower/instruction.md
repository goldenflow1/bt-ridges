# Make library sign-in lookups use an expression index

Case-insensitive e-mail lookup becomes expensive on a full library membership table. The application lookup is already correct; repair its database access path through Django model state and a new migration in `/app`.

Only the value of `Member.Meta.indexes` in `library/models.py` and a new `library/schema_migrations/0002_email_lookup.py` may change. Preserve everything else in the model file and all existing migrations, application code, tests and configuration. The new migration must depend on `library.0001_initial`, use Django `AddIndex`, and add only the index named `library_member_lower_email`. Use Django migration/model/expression imports only; no raw SQL, custom Python migration operations, planner settings, new constraints, columns, table rewrites, data changes or unrelated side effects.

Requirements:
- Add an expression index on the existing lower-case e-mail expression used by `email_lookup`; the immutable lookup filters a branch's active members on `Lower(email)` and returns ascending member IDs. E-mail fixtures are ASCII and may use mixed case.
- Keep model state and migration state synchronized. `makemigrations --check --dry-run` must remain clean before and after applying the migration.
- At 100,000 memberships distributed over five branches, PostgreSQL must naturally use `library_member_lower_email` for the real lookup. For several present addresses and a missing address, measured shared buffer work must be at most 64 blocks and at least ten times lower than the pre-index lookup. Do not force the planner.
- Preserve lookup results and every existing row, column, constraint and index. The only schema addition is the named expression index.
- Applying migrations twice must leave the second application a no-op. Reversing to `0001_initial` must remove the new index and preserve data and results; applying again must restore the index and its benefit.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
python manage.py makemigrations --check --dry-run
ruff check --no-cache library/models.py library/schema_migrations
```
