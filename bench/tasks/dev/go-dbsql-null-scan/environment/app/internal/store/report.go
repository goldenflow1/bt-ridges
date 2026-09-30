package store

import (
	"context"
	"database/sql"
)

type Store struct{ DB *sql.DB }
type Summary struct {
	Rows     int64
	Measured int64
	Total    sql.NullInt64
}

// Summarize returns all matching rows and their non-null measurement aggregate.
func (s *Store) Summarize(ctx context.Context, tenant string, start, end int64) (Summary, error) {
	var out Summary
	var total int64
	err := s.DB.QueryRowContext(ctx, `SELECT COUNT(value), COUNT(value), SUM(value) FROM readings WHERE tenant=$1 AND observed_at >= $2 AND observed_at < $3`, tenant, start, end).Scan(&out.Rows, &out.Measured, &total)
	out.Total = sql.NullInt64{Int64: total, Valid: true}
	return out, err
}
