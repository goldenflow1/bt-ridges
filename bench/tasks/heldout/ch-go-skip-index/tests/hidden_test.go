package builds

import (
	"buildvault/internal/migrate"
	"context"
	"fmt"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"reflect"
	"testing"
)

func businessIdentity(t *testing.T, conn driver.Conn) string {
	t.Helper()
	var count, ids, hash, instants uint64
	err := conn.QueryRow(context.Background(), "SELECT count(),sum(build_id),sum(cityHash64(job_id,outcome)),sum(toUInt64(toUnixTimestamp64Milli(started_at))) FROM builds").Scan(&count, &ids, &hash, &instants)
	if err != nil {
		t.Fatal(err)
	}
	var engine, sorting, primary, columns string
	err = conn.QueryRow(context.Background(), "SELECT engine,sorting_key,primary_key FROM system.tables WHERE database=currentDatabase() AND name='builds'").Scan(&engine, &sorting, &primary)
	if err != nil {
		t.Fatal(err)
	}
	err = conn.QueryRow(context.Background(), "SELECT arrayStringConcat(groupArray(concat(name,':',type)),',') FROM (SELECT name,type FROM system.columns WHERE database=currentDatabase() AND table='builds' ORDER BY position)").Scan(&columns)
	if err != nil {
		t.Fatal(err)
	}
	return fmt.Sprintf("%d/%d/%d/%d/%s/%s/%s/%s", count, ids, hash, instants, engine, sorting, primary, columns)
}

func migration(t *testing.T, conn driver.Conn, down bool) {
	t.Helper()
	if err := migrate.Apply(context.Background(), conn, "../../migrations", "0002_job_index.sql", down); err != nil {
		t.Fatal(err)
	}
}

func TestHiddenExistingPartsReadRowsBoundAndLifecycle(t *testing.T) {
	conn := testConn(t)
	ctx := context.Background()
	const n = 1048576
	err := conn.Exec(ctx, "INSERT INTO builds SELECT number+1,toUInt16(modulo(number,16)),toString(cityHash64(number)),toDateTime64('2026-01-01',3)+toIntervalSecond(intDiv(number,16)),if(modulo(number,3)=0,'failed','success') FROM numbers(1048576)")
	if err != nil {
		t.Fatal(err)
	}
	rows, err := conn.Query(ctx, "SELECT job_id FROM builds WHERE build_id IN (17,200007,900019) ORDER BY build_id")
	if err != nil {
		t.Fatal(err)
	}
	jobs := []string{}
	for rows.Next() {
		var id string
		if err = rows.Scan(&id); err != nil {
			t.Fatal(err)
		}
		jobs = append(jobs, id)
	}
	if err = rows.Err(); err != nil {
		t.Fatal(err)
	}
	rows.Close()
	jobs = append(jobs, "50000000000000000000")
	before := make([][]Build, 0, len(jobs))
	for _, job := range jobs {
		result, work, err := Lookup(ctx, conn, job)
		if err != nil {
			t.Fatal(err)
		}
		if work.RowsRead < n*9/10 {
			t.Fatalf("invalid baseline measurement: rows=%d", work.RowsRead)
		}
		before = append(before, result)
	}
	original := businessIdentity(t, conn)
	migration(t, conn, false)
	for i, job := range jobs {
		result, work, err := Lookup(ctx, conn, job)
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(result, before[i]) {
			t.Fatalf("migration changed results for %q", job)
		}
		if work.RowsRead > 32768 {
			t.Fatalf("job %q read %d rows, bound 32768", job, work.RowsRead)
		}
	}
	if businessIdentity(t, conn) != original {
		t.Fatal("migration changed data or layout")
	}
	var indexes uint64
	if err = conn.QueryRow(ctx, "SELECT count() FROM system.data_skipping_indices WHERE database=currentDatabase() AND table='builds' AND name='ix_build_job_id'").Scan(&indexes); err != nil {
		t.Fatal(err)
	}
	if indexes != 1 {
		t.Fatalf("expected one named index, got %d", indexes)
	}
	var ledgerBefore, ledgerAfter uint64
	if err = conn.QueryRow(ctx, "SELECT count() FROM schema_migrations").Scan(&ledgerBefore); err != nil {
		t.Fatal(err)
	}
	migration(t, conn, false)
	if err = conn.QueryRow(ctx, "SELECT count() FROM schema_migrations").Scan(&ledgerAfter); err != nil {
		t.Fatal(err)
	}
	if ledgerBefore != ledgerAfter {
		t.Fatal("repeat migration was not a no-op")
	}
	migration(t, conn, true)
	if businessIdentity(t, conn) != original {
		t.Fatal("down changed data or layout")
	}
	if err = conn.QueryRow(ctx, "SELECT count() FROM system.data_skipping_indices WHERE database=currentDatabase() AND table='builds'").Scan(&indexes); err != nil {
		t.Fatal(err)
	}
	if indexes != 0 {
		t.Fatal("down did not restore original indexes")
	}
	migration(t, conn, false)
	result, work, err := Lookup(ctx, conn, jobs[0])
	if err != nil || !reflect.DeepEqual(result, before[0]) || work.RowsRead > 32768 {
		t.Fatalf("reapply result/work mismatch: %d %v", work.RowsRead, err)
	}
	if err = conn.Exec(ctx, "INSERT INTO builds VALUES (2000001,15,?,'2026-04-01','success'),(2000002,14,?,'2026-04-02','failed')", jobs[0], jobs[0]); err != nil {
		t.Fatal(err)
	}
	fresh, _, err := Lookup(ctx, conn, jobs[0])
	if err != nil || len(fresh) != len(before[0])+2 || fresh[len(fresh)-1].BuildID != 2000002 {
		t.Fatalf("new parts missing: %#v %v", fresh, err)
	}
}

func TestHiddenQuotedJobAndCompleteFields(t *testing.T) {
	conn := testConn(t)
	ctx := context.Background()
	job := "job'quoted"
	if err := conn.Exec(ctx, "INSERT INTO builds VALUES (2,8,?,'2026-01-01 12:00:00.123','failed'),(1,7,?,'2026-01-01 12:00:00.123','success')", job, job); err != nil {
		t.Fatal(err)
	}
	migration(t, conn, false)
	result, _, err := Lookup(ctx, conn, job)
	if err != nil {
		t.Fatal(err)
	}
	if len(result) != 2 || result[0].BuildID != 1 || result[1].BuildID != 2 || result[0].ProjectID != 7 || result[1].Outcome != "failed" || result[0].StartedAt.Nanosecond() != 123000000 {
		t.Fatalf("payload/order changed: %#v", result)
	}
}
