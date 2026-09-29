# Fix duplicated rows across pages

`ListEvents` pages through events with a keyset cursor. When many events share the
same `created_at`, clients see some events twice and never see others.

Only edit `internal/store/events.go`, specifically `Store.ListEvents`. Keep the
function signature unchanged.

- pages are stable when timestamps tie;
- no event is skipped or repeated;
- page size is respected.

Run these checks before finishing:

```sh
go test ./internal/store/... -run TestListEvents
go vet ./internal/store/...
```
