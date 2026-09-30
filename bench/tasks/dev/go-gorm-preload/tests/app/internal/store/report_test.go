package store

import (
	"context"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"os"
	"sync/atomic"
	"testing"
	"time"
)

type counter struct {
	logger.Interface
	queries atomic.Int64
}

func (c *counter) Trace(ctx context.Context, begin time.Time, fc func() (string, int64), err error) {
	c.queries.Add(1)
	c.Interface.Trace(ctx, begin, fc, err)
}
func fixture(t *testing.T) (*Store, *counter) {
	t.Helper()
	c := &counter{Interface: logger.Default.LogMode(logger.Silent)}
	db, err := gorm.Open(postgres.Open(os.Getenv("AUDITFEED_TEST_DATABASE_URL")), &gorm.Config{Logger: c})
	if err != nil {
		t.Fatal(err)
	}
	raw, err := db.DB()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { raw.Close() })
	if err := db.Exec("DROP TABLE IF EXISTS items,orders,customers CASCADE").Error; err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&Customer{}, &Order{}, &Item{}); err != nil {
		t.Fatal(err)
	}
	return &Store{DB: db}, c
}
func seed(t *testing.T, s *Store, n int, orders int) {
	t.Helper()
	for i := n; i >= 1; i-- {
		if err := s.DB.Create(&Customer{ID: int64(i), Tenant: "a", Name: "customer"}).Error; err != nil {
			t.Fatal(err)
		}
		for j := orders; j >= 1; j-- {
			id := int64(i*100 + j)
			if err := s.DB.Create(&Order{ID: id, CustomerID: int64(i)}).Error; err != nil {
				t.Fatal(err)
			}
			for k := 2; k >= 1; k-- {
				if err := s.DB.Create(&Item{ID: id*10 + int64(k), OrderID: id, SKU: "part"}).Error; err != nil {
					t.Fatal(err)
				}
			}
		}
	}
}
func TestVisibleCustomers(t *testing.T) {
	s, _ := fixture(t)
	seed(t, s, 1, 1)
	rows, err := s.Customers(context.Background(), "a")
	if err != nil || len(rows) != 1 || len(rows[0].Orders) != 1 || len(rows[0].Orders[0].Items) != 2 {
		t.Fatalf("rows=%+v err=%v", rows, err)
	}
}
