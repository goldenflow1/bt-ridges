# Make open-ticket lookups fast

The support queue query filters tickets with `status = 'open'` by `team_id` and
orders by `created_at`. On a large table PostgreSQL scans every ticket.

Add a new migration that creates an index serving this query. Do not change
existing migrations, models, or query code. The index must be used by the
production query when most tickets are closed.

Run `python manage.py test support.tests.test_queue --keepdb` before finishing.
