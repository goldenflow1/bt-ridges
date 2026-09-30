package api

import (
	"context"
	"database/sql"
	_ "github.com/jackc/pgx/v5/stdlib"
	"os"
	"testing"
)

func testDB(t *testing.T) *sql.DB {
	t.Helper()
	connection, err := sql.Open("pgx", os.Getenv("PAYROLL_TEST_DATABASE_URL"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { connection.Close() })
	if _, err = connection.Exec("TRUNCATE pay_entries"); err != nil {
		t.Fatal(err)
	}
	return connection
}

func TestVisibleMiddayExport(t *testing.T) {
	connection := testDB(t)
	_, err := connection.Exec("INSERT INTO pay_entries VALUES (1,7,'2026-01-15 12:00:00+00',12500,'regular'),(2,8,'2026-01-15 12:00:00+00',9,'other')")
	if err != nil {
		t.Fatal(err)
	}
	report, err := Export(context.Background(), connection, 7, "2026-01-15", "2026-01-15", "UTC")
	if err != nil {
		t.Fatal(err)
	}
	if len(report.Entries) != 1 || report.Entries[0].ID != 1 || report.GrossCents != 12500 {
		t.Fatalf("unexpected export: %#v", report)
	}
}

func TestVisibleEmptyAndInvalidPeriod(t *testing.T) {
	connection := testDB(t)
	report, err := Export(context.Background(), connection, 7, "2026-01-15", "2026-01-15", "UTC")
	if err != nil || report.Entries == nil || len(report.Entries) != 0 {
		t.Fatalf("empty contract: %#v %v", report, err)
	}
	if _, err = Export(context.Background(), connection, 7, "2026-02-01", "2026-01-01", "UTC"); err == nil {
		t.Fatal("reversed period accepted")
	}
}
