package store

import (
	"context"
	"database/sql"
	_ "github.com/jackc/pgx/v5/stdlib"
	"os"
	"testing"
)

func fixture(t *testing.T) *Store {
	t.Helper()
	url := os.Getenv("AUDITFEED_TEST_DATABASE_URL")
	db, err := sql.Open("pgx", url)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	_, err = db.Exec(`DROP TABLE IF EXISTS readings; CREATE TABLE readings(id bigint PRIMARY KEY,tenant text NOT NULL,observed_at bigint NOT NULL,value bigint)`)
	if err != nil {
		t.Fatal(err)
	}
	return &Store{DB: db}
}
func TestVisibleSummary(t *testing.T) {
	s := fixture(t)
	if _, err := s.DB.Exec(`INSERT INTO readings VALUES (1,'a',10,2),(2,'a',20,5),(3,'b',10,99)`); err != nil {
		t.Fatal(err)
	}
	got, err := s.Summarize(context.Background(), "a", 10, 30)
	if err != nil || got.Rows != 2 || got.Measured != 2 || !got.Total.Valid || got.Total.Int64 != 7 {
		t.Fatalf("summary=%+v error=%v", got, err)
	}
}
