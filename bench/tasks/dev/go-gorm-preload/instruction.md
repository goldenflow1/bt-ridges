# Speed up customer graph responses

The customer listing endpoint slows down as customer count grows, even though each customer only has a few orders. Trace the database access in `/app` and fix the query growth.

Production edits are restricted to `internal/store/report.go`; this task does not prescribe a function. Preserve public types and signatures, tenant isolation, all customers including those without orders, only non-cancelled orders, and every item of every retained order. Customers, orders and items must each be ordered by ID ascending. Repeated calls must reflect committed writes. Use GORM associations; no raw SQL, schema changes, caching, concurrency, test edits or dependency changes. The endpoint must execute at most three database queries for any number of customers and orders, including 1, 8 and 40 customers.

Run these checks before finishing:
```bash
go test -count=1 ./...
go vet ./...
```
