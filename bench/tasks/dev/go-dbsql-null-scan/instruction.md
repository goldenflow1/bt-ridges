# Repair telemetry summary accounting

Work in `/app`. Change only the body of `(*Store).Summarize` in `internal/store/report.go`; preserve imports, signature, comments and every other byte outside that method.

The result counts all readings in the requested tenant and half-open numeric interval `[start,end)`, counts non-NULL measurements separately, and sums measured values. `Total.Valid` must be false when no measurements exist, including an empty population. A measured zero is valid. Signed values and sums larger than 32 bits are supported. Use one parameterized database query and propagate database errors; do not change schema, fixtures, dependencies, other files or introduce side effects.

Run these checks before finishing:
```bash
go test -count=1 ./...
go vet ./...
```
