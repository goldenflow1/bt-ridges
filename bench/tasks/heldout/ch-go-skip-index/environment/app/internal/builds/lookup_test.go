package builds

import (
	"buildvault/internal/connection"
	"buildvault/internal/migrate"
	"context"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"os"
	"testing"
)

func testConn(t *testing.T) driver.Conn {
	t.Helper()
	conn, err := connection.Open(os.Getenv("BUILDVAULT_TEST_DATABASE"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	ctx := context.Background()
	for _, table := range []string{"builds", "schema_migrations"} {
		if err = conn.Exec(ctx, "DROP TABLE IF EXISTS "+table); err != nil {
			t.Fatal(err)
		}
	}
	if err = migrate.Apply(ctx, conn, "../../migrations", "0001_schema.sql", false); err != nil {
		t.Fatal(err)
	}
	return conn
}

func TestVisibleJobLookupAndProjectTimeline(t *testing.T) {
	conn := testConn(t)
	ctx := context.Background()
	if err := conn.Exec(ctx, "INSERT INTO builds VALUES (1,7,'job-A','2026-01-01 12:00:00','success'),(2,8,'job-B','2026-01-02','failed')"); err != nil {
		t.Fatal(err)
	}
	if err := migrate.Apply(ctx, conn, "../../migrations", "0002_job_index.sql", false); err != nil {
		t.Fatal(err)
	}
	rows, _, err := Lookup(ctx, conn, "job-A")
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || rows[0].BuildID != 1 || rows[0].Outcome != "success" {
		t.Fatalf("unexpected rows: %#v", rows)
	}
	count, err := ProjectCount(ctx, conn, 7)
	if err != nil || count != 1 {
		t.Fatalf("project count=%d err=%v", count, err)
	}
}

func TestVisibleMissingJob(t *testing.T) {
	conn := testConn(t)
	rows, _, err := Lookup(context.Background(), conn, "absent")
	if err != nil || rows == nil || len(rows) != 0 {
		t.Fatalf("missing result=%v err=%v", rows, err)
	}
}
