#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('internal/store/report.go')
old='package store\n\nimport (\n\t"context"\n\t"database/sql"\n)\n\ntype Store struct{ DB *sql.DB }\ntype Summary struct {\n\tRows     int64\n\tMeasured int64\n\tTotal    sql.NullInt64\n}\n\n// Summarize returns all matching rows and their non-null measurement aggregate.\nfunc (s *Store) Summarize(ctx context.Context, tenant string, start, end int64) (Summary, error) {\n\tvar out Summary\n\tvar total int64\n\terr := s.DB.QueryRowContext(ctx, `SELECT COUNT(value), COUNT(value), SUM(value) FROM readings WHERE tenant=$1 AND observed_at >= $2 AND observed_at < $3`, tenant, start, end).Scan(&out.Rows, &out.Measured, &total)\n\tout.Total = sql.NullInt64{Int64: total, Valid: true}\n\treturn out, err\n}\n'
assert p.read_text()==old, 'source anchor changed'
p.write_text('package store\n\nimport (\n\t"context"\n\t"database/sql"\n)\n\ntype Store struct{ DB *sql.DB }\ntype Summary struct {\n\tRows     int64\n\tMeasured int64\n\tTotal    sql.NullInt64\n}\n\n// Summarize returns all matching rows and their non-null measurement aggregate.\nfunc (s *Store) Summarize(ctx context.Context, tenant string, start, end int64) (Summary, error) {\n\tvar out Summary\n\terr := s.DB.QueryRowContext(ctx, `SELECT COUNT(*), COUNT(value), SUM(value) FROM readings WHERE tenant=$1 AND observed_at >= $2 AND observed_at < $3`, tenant, start, end).Scan(&out.Rows, &out.Measured, &out.Total)\n\treturn out, err\n}\n')
PYFIX
