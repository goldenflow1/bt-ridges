# pantry

Community recipe site — JSON API (Django + PostgreSQL).

- `GET /api/recipes/?tag=<slug>&page=<n>` — published recipes, newest first, 20 per page.
- `GET /api/recipes/<slug>/` — one recipe with ingredients and latest reviews.
- `python manage.py seed_demo` — load the demo data set used by the development database.

Database settings come from `PANTRY_DB_*` environment variables (see `pantry_site/settings.py`).
Tests: `python manage.py test recipes --keepdb --noinput`.
