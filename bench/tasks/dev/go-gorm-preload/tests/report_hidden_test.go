package store

import (
	"context"
	"testing"
)

func TestHiddenBoundedQueries(t *testing.T) {
	for _, n := range []int{1, 8, 40} {
		s, c := fixture(t)
		seed(t, s, n, 3)
		c.queries.Store(0)
		rows, err := s.Customers(context.Background(), "a")
		queries := c.queries.Load()
		if err != nil || len(rows) != n {
			t.Fatalf("n=%d rows=%d err=%v", n, len(rows), err)
		}
		if queries > 3 {
			t.Fatalf("query budget n=%d: got %d, want <=3", n, queries)
		}
		for _, row := range rows {
			if len(row.Orders) != 3 {
				t.Fatalf("incomplete orders: %+v", row)
			}
			for _, o := range row.Orders {
				if len(o.Items) != 2 {
					t.Fatalf("incomplete items: %+v", o)
				}
			}
		}
	}
}
func TestHiddenCompleteGraph(t *testing.T) {
	s, _ := fixture(t)
	seed(t, s, 3, 3)
	if err := s.DB.Create(&Customer{ID: 99, Tenant: "a", Name: "empty"}).Error; err != nil {
		t.Fatal(err)
	}
	if err := s.DB.Create(&Customer{ID: 100, Tenant: "other", Name: "other"}).Error; err != nil {
		t.Fatal(err)
	}
	if err := s.DB.Create(&Order{ID: 1, CustomerID: 1, Cancelled: true}).Error; err != nil {
		t.Fatal(err)
	}
	if err := s.DB.Create(&Order{ID: 2, CustomerID: 100}).Error; err != nil {
		t.Fatal(err)
	}
	rows, err := s.Customers(context.Background(), "a")
	if err != nil || len(rows) != 4 {
		t.Fatalf("customers=%+v err=%v", rows, err)
	}
	for i, row := range rows[:3] {
		if row.ID != int64(i+1) || len(row.Orders) != 3 {
			t.Fatalf("complete graph: %+v", row)
		}
		for j, o := range row.Orders {
			if o.ID != int64((i+1)*100+j+1) || o.Cancelled || len(o.Items) != 2 {
				t.Fatalf("ordered active orders: %+v", o)
			}
			if o.Items[0].ID >= o.Items[1].ID {
				t.Fatalf("unordered items: %+v", o.Items)
			}
		}
	}
	if rows[3].ID != 99 || len(rows[3].Orders) != 0 {
		t.Fatalf("empty parent lost: %+v", rows)
	}
	// A second call after a write must not serve a cached graph.
	if err := s.DB.Create(&Order{ID: 9901, CustomerID: 99}).Error; err != nil {
		t.Fatal(err)
	}
	again, err := s.Customers(context.Background(), "a")
	if err != nil || len(again[3].Orders) != 1 {
		t.Fatalf("stale graph: %+v %v", again, err)
	}
}
