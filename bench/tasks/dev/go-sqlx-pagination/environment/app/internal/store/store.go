// Package store holds the audit event persistence layer.
package store

import (
	"encoding/base64"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jmoiron/sqlx"
)

// DefaultPageSize is used when a caller asks for a non-positive limit.
const DefaultPageSize = 50

// MaxPageSize caps the limit a caller may ask for.
const MaxPageSize = 500

// ErrBadCursor is returned when a page cursor cannot be decoded.
var ErrBadCursor = errors.New("store: malformed page cursor")

// Event is one entry of a tenant's audit trail.
type Event struct {
	ID        int64     `db:"id" json:"id"`
	TenantID  string    `db:"tenant_id" json:"tenant_id"`
	Actor     string    `db:"actor" json:"actor"`
	Action    string    `db:"action" json:"action"`
	Target    string    `db:"target" json:"target"`
	CreatedAt time.Time `db:"created_at" json:"created_at"`
}

// Page is one page of events plus the cursor for the next page.
// NextCursor is empty when there are no further events.
type Page struct {
	Events     []Event `json:"events"`
	NextCursor string  `json:"next_cursor,omitempty"`
}

// Cursor identifies the last event of a page.
type Cursor struct {
	CreatedAt time.Time
	ID        int64
}

// Encode returns the opaque string form handed to API clients.
func (c Cursor) Encode() string {
	raw := c.CreatedAt.UTC().Format(time.RFC3339Nano) + "|" + strconv.FormatInt(c.ID, 10)
	return base64.RawURLEncoding.EncodeToString([]byte(raw))
}

// DecodeCursor parses a cursor produced by Cursor.Encode. An empty string
// means "start from the beginning" and yields a nil cursor.
func DecodeCursor(s string) (*Cursor, error) {
	if s == "" {
		return nil, nil
	}
	raw, err := base64.RawURLEncoding.DecodeString(s)
	if err != nil {
		return nil, ErrBadCursor
	}
	ts, id, ok := strings.Cut(string(raw), "|")
	if !ok {
		return nil, ErrBadCursor
	}
	createdAt, err := time.Parse(time.RFC3339Nano, ts)
	if err != nil {
		return nil, ErrBadCursor
	}
	n, err := strconv.ParseInt(id, 10, 64)
	if err != nil {
		return nil, ErrBadCursor
	}
	return &Cursor{CreatedAt: createdAt, ID: n}, nil
}

// Store wraps the database handle.
type Store struct {
	db *sqlx.DB
}

// New returns a Store backed by db.
func New(db *sqlx.DB) *Store {
	return &Store{db: db}
}

// Open connects to PostgreSQL using the pgx stdlib driver.
func Open(url string) (*sqlx.DB, error) {
	db, err := sqlx.Open("pgx", url)
	if err != nil {
		return nil, fmt.Errorf("store: open: %w", err)
	}
	return db, nil
}

func clampLimit(limit int) int {
	if limit <= 0 {
		return DefaultPageSize
	}
	if limit > MaxPageSize {
		return MaxPageSize
	}
	return limit
}
