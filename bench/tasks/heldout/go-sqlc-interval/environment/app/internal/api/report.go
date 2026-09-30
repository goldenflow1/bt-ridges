package api

import (
	"context"
	"database/sql"
	"salarybook/internal/db"
	"salarybook/internal/payroll"
)

type PeriodReport struct {
	Entries    []db.PayEntry
	GrossCents int64
}

func Export(ctx context.Context, connection *sql.DB, organization int64, first, last, zone string) (PeriodReport, error) {
	entries, err := payroll.Report(ctx, connection, organization, first, last, zone)
	if err != nil {
		return PeriodReport{}, err
	}
	return PeriodReport{Entries: entries, GrossCents: payroll.Gross(entries)}, nil
}
