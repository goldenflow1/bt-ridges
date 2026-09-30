# Library Card Access

Library branches identify active members by a case-insensitive ASCII e-mail address. The sign-in lookup uses the model's lower-case expression. At production volume, this scan dominates lookup latency.

The immutable lookup is in `library/repositories/members.py`, used by the access service and API. Membership exports have a separate query path. Model state and Django migrations must agree. Development schema is initialized with `python manage.py migrate`.
