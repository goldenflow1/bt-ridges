package store_test

import (
	"context"
	"testing"
	"time"

	"github.com/jmoiron/sqlx"

	"auditfeed/internal/store"
)

func expectedOrder(t *testing.T, db *sqlx.DB, tenant string) []int64 {
	t.Helper()
	var ids []int64
	if err := db.Select(&ids,
		`SELECT id FROM audit_events WHERE tenant_id = $1 ORDER BY created_at, id`, tenant); err != nil {
		t.Fatal(err)
	}
	return ids
}

func checkWalk(t *testing.T, s *store.Store, db *sqlx.DB, tenant string, limits ...int) {
	t.Helper()
	want := expectedOrder(t, db, tenant)
	for _, limit := range limits {
		got := walk(t, s, tenant, limit)
		if !equalIDs(got, want) {
			t.Errorf("tenant %s limit %d:\n got %v\nwant %v", tenant, limit, got, want)
		}
	}
}

func TestHiddenTiesAcrossPageBoundaries(t *testing.T) {
	s, db := openTestStore(t)
	groups := []int{5, 1, 7, 2, 4}
	for g, size := range groups {
		at := base.Add(time.Duration(g) * time.Second)
		for i := 0; i < size; i++ {
			record(t, s, "gannet", "importer", "row.upsert", at)
		}
	}
	checkWalk(t, s, db, "gannet", 1, 2, 3, 4, 5, 6, 7, 8, 19, 50)
}

func TestHiddenBackfilledEventsHaveIDsOutOfTimeOrder(t *testing.T) {
	s, db := openTestStore(t)
	for i := 0; i < 6; i++ {
		record(t, s, "gannet", "live", "doc.view", base.Add(time.Duration(10+i)*time.Minute))
	}
	// A backfill job replays older history after the live events were written.
	for i := 0; i < 9; i++ {
		record(t, s, "gannet", "backfill", "doc.view", base.Add(time.Duration(i/3)*time.Minute))
	}
	record(t, s, "gannet", "backfill", "doc.view", base.Add(12*time.Minute))
	checkWalk(t, s, db, "gannet", 1, 2, 3, 4, 7, 16)
}

func TestHiddenWholeFeedAtOneInstant(t *testing.T) {
	s, db := openTestStore(t)
	for i := 0; i < 24; i++ {
		record(t, s, "petrel", "bulk", "member.add", base)
	}
	checkWalk(t, s, db, "petrel", 1, 4, 5, 6, 24, 25)

	pages := 0
	cursor := ""
	for {
		page, err := s.ListEvents(context.Background(), "petrel", cursor, 6)
		if err != nil {
			t.Fatal(err)
		}
		pages++
		if len(page.Events) != 6 {
			t.Fatalf("page %d has %d events, want 6", pages, len(page.Events))
		}
		if page.NextCursor == "" {
			break
		}
		cursor = page.NextCursor
		if pages > 10 {
			t.Fatal("too many pages")
		}
	}
	if pages != 4 {
		t.Fatalf("24 events at limit 6 took %d pages, want 4", pages)
	}
}

func TestHiddenMicrosecondNeighboursAndTies(t *testing.T) {
	s, db := openTestStore(t)
	offsets := []int{0, 1, 1, 2, 0, 3, 1, 999999, 1000000, 1000000, 2}
	for _, us := range offsets {
		record(t, s, "petrel", "sync", "file.put", base.Add(time.Duration(us)*time.Microsecond))
	}
	checkWalk(t, s, db, "petrel", 1, 2, 3, 5)
}

func TestHiddenEventsWrittenAtCursorInstantAppearLater(t *testing.T) {
	s, db := openTestStore(t)
	for i := 0; i < 4; i++ {
		record(t, s, "skua", "api", "key.use", base)
	}
	page, err := s.ListEvents(context.Background(), "skua", "", 2)
	if err != nil {
		t.Fatal(err)
	}
	seen := []int64{page.Events[0].ID, page.Events[1].ID}
	late := record(t, s, "skua", "api", "key.use", base)
	cursor := page.NextCursor
	for cursor != "" {
		page, err = s.ListEvents(context.Background(), "skua", cursor, 2)
		if err != nil {
			t.Fatal(err)
		}
		for _, e := range page.Events {
			seen = append(seen, e.ID)
		}
		cursor = page.NextCursor
	}
	if want := expectedOrder(t, db, "skua"); !equalIDs(seen, want) || seen[len(seen)-1] != late.ID {
		t.Fatalf("got %v want %v", seen, want)
	}
}

func TestHiddenTenantsShareTimestamps(t *testing.T) {
	s, db := openTestStore(t)
	for i := 0; i < 5; i++ {
		at := base.Add(time.Duration(i%2) * time.Second)
		record(t, s, "gannet", "a", "login", at)
		record(t, s, "skua", "b", "login", at)
	}
	checkWalk(t, s, db, "gannet", 1, 2, 3)
	checkWalk(t, s, db, "skua", 1, 2, 3)
}
