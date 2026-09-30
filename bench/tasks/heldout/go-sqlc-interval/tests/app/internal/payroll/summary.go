package payroll

import "salarybook/internal/db"

func Gross(entries []db.PayEntry) int64 {
	var total int64
	for _, entry := range entries {
		total += entry.GrossCents
	}
	return total
}
