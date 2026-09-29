package store

import (
	"context"
	"fmt"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib" // registers the "pgx" driver
)

// RecordEvent appends an event and returns it with its assigned id.
func (s *Store) RecordEvent(ctx context.Context, e Event) (Event, error) {
	if e.CreatedAt.IsZero() {
		e.CreatedAt = time.Now().UTC()
	}
	err := s.db.QueryRowxContext(ctx,
		`INSERT INTO audit_events (tenant_id, actor, action, target, created_at)
		 VALUES ($1, $2, $3, $4, $5)
		 RETURNING id, created_at`,
		e.TenantID, e.Actor, e.Action, e.Target, e.CreatedAt,
	).Scan(&e.ID, &e.CreatedAt)
	if err != nil {
		return Event{}, fmt.Errorf("store: record event: %w", err)
	}
	return e, nil
}

// ListEvents returns one page of a tenant's events in chronological order,
// oldest first, starting after the position encoded in cursor. Walking the
// pages by feeding NextCursor back in must visit every event exactly once.
func (s *Store) ListEvents(ctx context.Context, tenantID, cursor string, limit int) (Page, error) {
	after, err := DecodeCursor(cursor)
	if err != nil {
		return Page{}, err
	}
	limit = clampLimit(limit)

	query := `SELECT id, tenant_id, actor, action, target, created_at
		FROM audit_events
		WHERE tenant_id = $1`
	args := []any{tenantID}
	if after != nil {
		query += ` AND created_at > $2`
		args = append(args, after.CreatedAt)
	}
	query += fmt.Sprintf(` ORDER BY created_at LIMIT %d`, limit+1)

	events := make([]Event, 0, limit+1)
	if err := s.db.SelectContext(ctx, &events, query, args...); err != nil {
		return Page{}, fmt.Errorf("store: list events: %w", err)
	}

	page := Page{Events: events}
	if len(events) > limit {
		page.Events = events[:limit]
		last := page.Events[limit-1]
		page.NextCursor = Cursor{CreatedAt: last.CreatedAt, ID: last.ID}.Encode()
	}
	return page, nil
}

// CountEvents returns how many events a tenant has.
func (s *Store) CountEvents(ctx context.Context, tenantID string) (int64, error) {
	var n int64
	err := s.db.GetContext(ctx, &n,
		`SELECT count(*) FROM audit_events WHERE tenant_id = $1`, tenantID)
	if err != nil {
		return 0, fmt.Errorf("store: count events: %w", err)
	}
	return n, nil
}
