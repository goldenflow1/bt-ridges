package payroll

import (
	"context"
	"database/sql"
	"salarybook/internal/calendar"
	"salarybook/internal/db"
)

func Report(ctx context.Context, connection *sql.DB, organization int64, first, last, zone string) ([]db.PayEntry, error) {
	start, end, err := calendar.Bounds(first, last, zone)
	if err != nil {
		return nil, err
	}
	return db.New(connection).ListPayEntries(ctx, db.ListPayEntriesParams{OrganizationID: organization, PeriodStart: start, PeriodEnd: end})
}
