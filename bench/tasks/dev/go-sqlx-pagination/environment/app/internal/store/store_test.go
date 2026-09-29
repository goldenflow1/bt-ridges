package store_test

import (
	"context"
	"errors"
	"os"
	"testing"
	"time"

	"github.com/jmoiron/sqlx"

	"auditfeed/internal/store"
)

var base = time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC)

// openTestStore connects to the scratch database, applies the schema and
// empties the table.
func openTestStore(t *testing.T) (*store.Store, *sqlx.DB) {
	t.Helper()
	url := os.Getenv("AUDITFEED_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("AUDITFEED_TEST_DATABASE_URL is not set")
	}
	db, err := store.Open(url)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	schema, err := os.ReadFile("../../migrations/001_audit_events.sql")
	if err != nil {
		t.Fatal(err)
	}
	db.MustExec(string(schema))
	db.MustExec(`TRUNCATE audit_events RESTART IDENTITY`)
	return store.New(db), db
}

func record(t *testing.T, s *store.Store, tenant, actor, action string, at time.Time) store.Event {
	t.Helper()
	e, err := s.RecordEvent(context.Background(), store.Event{
		TenantID: tenant, Actor: actor, Action: action, Target: "doc/1", CreatedAt: at,
	})
	if err != nil {
		t.Fatal(err)
	}
	return e
}

// walk follows NextCursor until the feed is exhausted and returns the ids in
// the order they were served.
func walk(t *testing.T, s *store.Store, tenant string, limit int) []int64 {
	t.Helper()
	var ids []int64
	cursor := ""
	for pages := 0; ; pages++ {
		if pages > 10000 {
			t.Fatal("pagination does not terminate")
		}
		page, err := s.ListEvents(context.Background(), tenant, cursor, limit)
		if err != nil {
			t.Fatal(err)
		}
		for _, e := range page.Events {
			ids = append(ids, e.ID)
		}
		if page.NextCursor == "" {
			return ids
		}
		cursor = page.NextCursor
	}
}

func equalIDs(a, b []int64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestCursorRoundTrip(t *testing.T) {
	c := store.Cursor{CreatedAt: base.Add(1234567 * time.Microsecond), ID: 42}
	got, err := store.DecodeCursor(c.Encode())
	if err != nil {
		t.Fatal(err)
	}
	if !got.CreatedAt.Equal(c.CreatedAt) || got.ID != 42 {
		t.Fatalf("round trip: got %+v want %+v", got, c)
	}
	if none, err := store.DecodeCursor(""); err != nil || none != nil {
		t.Fatalf("empty cursor: got %v, %v", none, err)
	}
}

func TestDecodeCursorRejectsGarbage(t *testing.T) {
	for _, bad := range []string{"%%%", "bm90LWEtY3Vyc29y", "MjAyNi0wNi0wMXx4"} {
		if _, err := store.DecodeCursor(bad); !errors.Is(err, store.ErrBadCursor) {
			t.Errorf("DecodeCursor(%q) = %v, want ErrBadCursor", bad, err)
		}
	}
}

func TestListEventsFirstPage(t *testing.T) {
	s, _ := openTestStore(t)
	a := record(t, s, "kestrel", "mia", "login", base)
	b := record(t, s, "kestrel", "mia", "doc.view", base.Add(time.Second))
	record(t, s, "kestrel", "raj", "doc.edit", base.Add(2*time.Second))

	page, err := s.ListEvents(context.Background(), "kestrel", "", 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Events) != 2 || page.Events[0].ID != a.ID || page.Events[1].ID != b.ID {
		t.Fatalf("first page = %+v", page.Events)
	}
	if page.NextCursor == "" {
		t.Fatal("expected a next cursor")
	}
}

func TestListEventsWalksAllPages(t *testing.T) {
	s, _ := openTestStore(t)
	var want []int64
	for i := 0; i < 7; i++ {
		want = append(want, record(t, s, "kestrel", "mia", "doc.view", base.Add(time.Duration(i)*time.Minute)).ID)
	}
	for _, limit := range []int{1, 3, 7, 10} {
		if got := walk(t, s, "kestrel", limit); !equalIDs(got, want) {
			t.Errorf("limit %d: got %v want %v", limit, got, want)
		}
	}
}

func TestListEventsOrdersByTimeNotID(t *testing.T) {
	s, _ := openTestStore(t)
	late := record(t, s, "kestrel", "sync", "import", base.Add(time.Hour))
	early := record(t, s, "kestrel", "sync", "import", base)

	got := walk(t, s, "kestrel", 1)
	if want := []int64{early.ID, late.ID}; !equalIDs(got, want) {
		t.Fatalf("got %v want %v", got, want)
	}
}

func TestListEventsTenantIsolation(t *testing.T) {
	s, _ := openTestStore(t)
	mine := record(t, s, "kestrel", "mia", "login", base)
	record(t, s, "osprey", "lee", "login", base.Add(time.Second))

	if got := walk(t, s, "kestrel", 5); !equalIDs(got, []int64{mine.ID}) {
		t.Fatalf("got %v", got)
	}
	if got := walk(t, s, "heron", 5); len(got) != 0 {
		t.Fatalf("unknown tenant got %v", got)
	}
}

func TestListEventsClampsLimit(t *testing.T) {
	s, _ := openTestStore(t)
	for i := 0; i < store.DefaultPageSize+1; i++ {
		record(t, s, "kestrel", "bot", "ping", base.Add(time.Duration(i)*time.Second))
	}
	page, err := s.ListEvents(context.Background(), "kestrel", "", 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Events) != store.DefaultPageSize || page.NextCursor == "" {
		t.Fatalf("got %d events, cursor %q", len(page.Events), page.NextCursor)
	}
}

func TestListEventsRejectsBadCursor(t *testing.T) {
	s, _ := openTestStore(t)
	if _, err := s.ListEvents(context.Background(), "kestrel", "%%%", 5); !errors.Is(err, store.ErrBadCursor) {
		t.Fatalf("got %v", err)
	}
}

func TestCountEvents(t *testing.T) {
	s, _ := openTestStore(t)
	record(t, s, "kestrel", "mia", "login", base)
	record(t, s, "kestrel", "mia", "logout", base.Add(time.Minute))
	n, err := s.CountEvents(context.Background(), "kestrel")
	if err != nil || n != 2 {
		t.Fatalf("count = %d, %v", n, err)
	}
}
