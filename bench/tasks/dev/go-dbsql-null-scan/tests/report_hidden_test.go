package store

import (
	"context"
	"testing"
)

func TestHiddenNullPopulation(t *testing.T) {
	s := fixture(t)
	if _, err := s.DB.Exec(`INSERT INTO readings VALUES (1,'a',10,NULL),(2,'a',11,0),(3,'a',12,-7),(4,'b',12,900),(5,'a',20,99)`); err != nil {
		t.Fatal(err)
	}
	got, err := s.Summarize(context.Background(), "a", 10, 20)
	if err != nil || got.Rows != 3 || got.Measured != 2 || !got.Total.Valid || got.Total.Int64 != -7 {
		t.Fatalf("nullable population: got %+v err=%v", got, err)
	}
}
func TestHiddenAbsentSum(t *testing.T) {
	s := fixture(t)
	if _, err := s.DB.Exec(`INSERT INTO readings VALUES (1,'a',10,NULL),(2,'a',11,NULL),(3,'zero',10,0)`); err != nil {
		t.Fatal(err)
	}
	for _, tenant := range []string{"a", "missing"} {
		got, err := s.Summarize(context.Background(), tenant, 0, 20)
		expected := int64(0)
		if tenant == "a" {
			expected = 2
		}
		if err != nil || got.Rows != expected || got.Measured != 0 || got.Total.Valid {
			t.Fatalf("absent sum %s: got %+v err=%v", tenant, got, err)
		}
	}
	zero, err := s.Summarize(context.Background(), "zero", 0, 20)
	if err != nil || !zero.Total.Valid || zero.Total.Int64 != 0 {
		t.Fatalf("zero is a present sum: %+v %v", zero, err)
	}
}
func TestHiddenRangeAndWideSum(t *testing.T) {
	s := fixture(t)
	if _, err := s.DB.Exec(`INSERT INTO readings VALUES (1,'a',-1,99),(2,'a',0,4000000000),(3,'a',9,5000000000),(4,'a',10,77),(5,'b',0,999)`); err != nil {
		t.Fatal(err)
	}
	got, err := s.Summarize(context.Background(), "a", 0, 10)
	if err != nil || got.Rows != 2 || got.Total.Int64 != 9000000000 || !got.Total.Valid {
		t.Fatalf("range/wide aggregate: %+v %v", got, err)
	}
}

func TestHiddenPropagatesDatabaseErrors(t *testing.T) {
	s := fixture(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := s.Summarize(ctx, "a", 0, 1); err == nil {
		t.Fatal("canceled query must return an error")
	}
	if _, err := s.DB.Exec("DROP TABLE readings"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Summarize(context.Background(), "a", 0, 1); err == nil {
		t.Fatal("database errors must propagate")
	}
}
