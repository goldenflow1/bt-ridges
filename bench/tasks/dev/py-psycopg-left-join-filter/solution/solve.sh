#!/bin/bash
set -euo pipefail
cd /app
python - <<'PYFIX'
from pathlib import Path
p = Path('app/queries.py')
assert p.read_text() == 'def department_counts(conn, tenant_id, since, until):\n    """Department counts and total minutes for non-cancelled bookings in the requested window."""\n    query = """\n        SELECT d.id, COUNT(b.id), COALESCE(SUM(b.minutes), 0)\n        FROM departments d LEFT JOIN bookings b ON b.department_id = d.id\n        WHERE d.tenant_id = %s AND b.cancelled = false AND b.starts_at >= %s AND b.starts_at < %s\n        GROUP BY d.id ORDER BY d.id\n    """\n    return conn.execute(query, (tenant_id, since, until)).fetchall()\n', "source anchor changed"
p.write_text('def department_counts(conn, tenant_id, since, until):\n    """Department counts and total minutes for non-cancelled bookings in the requested window."""\n    query = """\n        SELECT d.id, COUNT(b.id), COALESCE(SUM(b.minutes), 0)\n        FROM departments d LEFT JOIN bookings b ON b.department_id = d.id\n          AND b.cancelled = false AND b.starts_at >= %s AND b.starts_at < %s\n        WHERE d.tenant_id = %s\n        GROUP BY d.id ORDER BY d.id\n    """\n    return conn.execute(query, (since, until, tenant_id)).fetchall()\n')
PYFIX
