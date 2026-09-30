package api

import (
	"context"
	"reflect"
	"testing"
)

func checkIDs(t *testing.T, got PeriodReport, expected []int64) {
	t.Helper()
	actual := []int64{}
	for _, r := range got.Entries {
		actual = append(actual, r.ID)
	}
	if !reflect.DeepEqual(actual, expected) {
		t.Fatalf("entry IDs: got %v want %v", actual, expected)
	}
}

func TestHiddenFractionalEndAndExclusiveMidnight(t *testing.T) {
	connection := testDB(t)
	_, err := connection.Exec(`INSERT INTO pay_entries VALUES
 (6,7,'2026-01-31 23:59:59.999999+00',-5,'last microsecond'),
 (5,7,'2026-01-31 23:59:59.500000+00',9000000000000,'fraction'),
 (4,7,'2026-02-01 00:00:00+00',99,'next day'),
 (3,7,'2026-01-31 00:00:00+00',0,'start'),
 (2,7,'2026-01-30 23:59:59.999999+00',99,'before'),
 (1,8,'2026-01-31 12:00:00+00',99,'other organization')`)
	if err != nil {
		t.Fatal(err)
	}
	result, err := Export(context.Background(), connection, 7, "2026-01-31", "2026-01-31", "UTC")
	if err != nil {
		t.Fatal(err)
	}
	checkIDs(t, result, []int64{3, 5, 6})
	if result.GrossCents != 8999999999995 || result.Entries[2].Memo != "last microsecond" || result.Entries[2].PostedAt.Nanosecond() != 999999000 {
		t.Fatalf("lost payload: %#v", result)
	}
}

func TestHiddenDSTUsesSuppliedInstants(t *testing.T) {
	for _, day := range []string{"2026-03-08", "2026-11-01"} {
		connection := testDB(t)
		var sql string
		if day == "2026-03-08" {
			sql = `INSERT INTO pay_entries VALUES (1,7,'2026-03-08 05:00:00+00',1,'start'),(2,7,'2026-03-09 03:59:59.5+00',2,'last'),(3,7,'2026-03-09 04:00:00+00',3,'next'),(4,7,'2026-03-08 04:59:59+00',4,'before')`
		} else {
			sql = `INSERT INTO pay_entries VALUES (1,7,'2026-11-01 04:00:00+00',1,'start'),(2,7,'2026-11-02 04:59:59.5+00',2,'last'),(3,7,'2026-11-02 05:00:00+00',3,'next'),(4,7,'2026-11-01 03:59:59+00',4,'before')`
		}
		if _, err := connection.Exec(sql); err != nil {
			t.Fatal(err)
		}
		result, err := Export(context.Background(), connection, 7, day, day, "America/New_York")
		if err != nil {
			t.Fatal(err)
		}
		checkIDs(t, result, []int64{1, 2})
	}
}

func TestHiddenYearChangeFractionalZoneAndTies(t *testing.T) {
	connection := testDB(t)
	_, err := connection.Exec(`INSERT INTO pay_entries VALUES
 (10,7,'2026-01-01 00:00:00+05:45',10,'next'),
 (9,7,'2025-12-31 23:59:59.999999+05:45',9,'last'),
 (8,7,'2025-12-31 12:00:00+05:45',8,'tied later ID'),
 (7,7,'2025-12-31 12:00:00+05:45',7,'tied earlier ID'),
 (6,7,'2025-12-30 00:00:00+05:45',6,'first')`)
	if err != nil {
		t.Fatal(err)
	}
	result, err := Export(context.Background(), connection, 7, "2025-12-30", "2025-12-31", "Asia/Kathmandu")
	if err != nil {
		t.Fatal(err)
	}
	checkIDs(t, result, []int64{6, 7, 8, 9})
}
