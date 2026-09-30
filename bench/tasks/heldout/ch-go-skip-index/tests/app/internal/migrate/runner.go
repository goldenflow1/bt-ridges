package migrate

import (
	"context"
	"fmt"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Apply follows the repository's versioned Up/Down convention. Missing pending files are a no-op.
func Apply(ctx context.Context, conn driver.Conn, directory, filename string, down bool) error {
	if !regexp.MustCompile(`^[0-9]{4}_[a-z_]+\.sql$`).MatchString(filename) {
		return fmt.Errorf("invalid migration filename")
	}
	raw, err := os.ReadFile(filepath.Join(directory, filename))
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	parts := strings.Split(string(raw), "-- +migrate Down")
	if len(parts) != 2 || !strings.HasPrefix(parts[0], "-- +migrate Up") {
		return fmt.Errorf("expected Up and Down sections")
	}
	version64, err := strconv.ParseUint(filename[:4], 10, 32)
	if err != nil {
		return err
	}
	version := uint32(version64)
	if err = conn.Exec(ctx, "CREATE TABLE IF NOT EXISTS schema_migrations(version UInt32,active UInt8,stamp UInt64) ENGINE=ReplacingMergeTree(stamp) ORDER BY version"); err != nil {
		return err
	}
	var active uint8
	if err = conn.QueryRow(ctx, "SELECT ifNull(argMax(active,stamp),0) FROM schema_migrations WHERE version=?", version).Scan(&active); err != nil {
		return err
	}
	if (!down && active == 1) || (down && active == 0) {
		return nil
	}
	section := parts[0]
	next := uint8(1)
	if down {
		section = parts[1]
		next = 0
	}
	lines := []string{}
	for _, line := range strings.Split(section, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "--") || strings.HasPrefix(trimmed, "#") || strings.HasPrefix(trimmed, "//") {
			continue
		}
		lines = append(lines, line)
	}
	for _, query := range strings.Split(strings.Join(lines, "\n"), ";") {
		query = strings.TrimSpace(query)
		if query != "" {
			if err = conn.Exec(ctx, query); err != nil {
				return err
			}
		}
	}
	return conn.Exec(ctx, "INSERT INTO schema_migrations VALUES (?,?,?)", version, next, uint64(time.Now().UnixNano()))
}
