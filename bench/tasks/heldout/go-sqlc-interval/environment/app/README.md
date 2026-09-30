# Salary Book

Payroll exports collect ledger entries for inclusive local calendar dates. The civil-time adapter converts that period into a start instant and the following local midnight. The SQL selection currently loses postings near midnight.

`internal/api` calls the payroll service, which delegates date handling to `internal/calendar` and database reads to pinned sqlc 1.27.0 output in `internal/db`. Edit the query source, run `sqlc generate`, and retain synchronized generated code. Other generated files and the caller are protected.
