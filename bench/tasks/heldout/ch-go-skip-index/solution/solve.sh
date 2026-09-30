#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
assert Path('migrations/0001_schema.sql').read_text()=="-- +migrate Up\nCREATE TABLE IF NOT EXISTS builds (\n  build_id UInt64, project_id UInt16, job_id String, started_at DateTime64(3,'UTC'), outcome String\n) ENGINE=MergeTree ORDER BY (project_id,started_at) SETTINGS index_granularity=8192;\n-- +migrate Down\nDROP TABLE IF EXISTS builds;\n", 'schema anchor changed'
p=Path('migrations/0002_job_index.sql')
assert not p.exists(), 'pending migration already exists'
p.write_text('-- +migrate Up\nALTER TABLE builds ADD INDEX IF NOT EXISTS ix_build_job_id job_id TYPE bloom_filter(0.0001) GRANULARITY 1;\nALTER TABLE builds MATERIALIZE INDEX ix_build_job_id SETTINGS mutations_sync=2;\n-- +migrate Down\nALTER TABLE builds DROP INDEX IF EXISTS ix_build_job_id;\n')
PYFIX
