package calendar

import (
	"fmt"
	"time"
	_ "time/tzdata"
)

// Bounds maps an inclusive civil-date range to an exclusive ending instant.
func Bounds(first, last, zone string) (time.Time, time.Time, error) {
	loc, err := time.LoadLocation(zone)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	start, err := time.ParseInLocation("2006-01-02", first, loc)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	end, err := time.ParseInLocation("2006-01-02", last, loc)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	if end.Before(start) {
		return time.Time{}, time.Time{}, fmt.Errorf("reversed period")
	}
	return start, end.AddDate(0, 0, 1), nil
}
