#!/bin/bash
set -euo pipefail
cd /app
python - <<'PYFIX'
from pathlib import Path
p = Path('migrations/ready_jobs.py')
assert p.read_text() == 'import sqlalchemy as sa\nfrom alembic import op\n\nrevision = \'0002_ready_jobs\'\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade():\n    op.create_index(\'ix_jobs_ready\', \'jobs\', [\'tenant_id\', \'created_at\', \'id\'],\n                    postgresql_where=sa.text("status = \'waiting\' AND deleted_at IS NULL"))\n\n\ndef downgrade():\n    op.drop_index(\'ix_jobs_ready\', table_name=\'jobs\')\n', "source anchor changed"
p.write_text('import sqlalchemy as sa\nfrom alembic import op\n\nrevision = \'0002_ready_jobs\'\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade():\n    op.create_index(\'ix_jobs_ready\', \'jobs\', [\'tenant_id\', \'created_at\', \'id\'],\n                    postgresql_where=sa.text("status = \'ready\' AND deleted_at IS NULL"))\n\n\ndef downgrade():\n    op.drop_index(\'ix_jobs_ready\', table_name=\'jobs\')\n')
PYFIX
