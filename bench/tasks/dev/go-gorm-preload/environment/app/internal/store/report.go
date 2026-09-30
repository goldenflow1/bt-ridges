package store

import (
	"context"
	"gorm.io/gorm"
)

type Store struct{ DB *gorm.DB }
type Customer struct {
	ID     int64 `gorm:"primaryKey"`
	Tenant string
	Name   string
	Orders []Order
}
type Order struct {
	ID         int64 `gorm:"primaryKey"`
	CustomerID int64
	Cancelled  bool
	Items      []Item
}
type Item struct {
	ID      int64 `gorm:"primaryKey"`
	OrderID int64
	SKU     string
}

func (s *Store) Customers(ctx context.Context, tenant string) ([]Customer, error) {
	var customers []Customer
	db := s.DB.WithContext(ctx)
	if err := db.Where("tenant = ?", tenant).Order("id").Find(&customers).Error; err != nil {
		return nil, err
	}
	for i := range customers {
		if err := db.Where("customer_id = ? AND cancelled = false", customers[i].ID).Order("id").Find(&customers[i].Orders).Error; err != nil {
			return nil, err
		}
		for j := range customers[i].Orders {
			if err := db.Where("order_id = ?", customers[i].Orders[j].ID).Order("id").Find(&customers[i].Orders[j].Items).Error; err != nil {
				return nil, err
			}
		}
	}
	return customers, nil
}
