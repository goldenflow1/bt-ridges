package builds

import (
	"context"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

func ProjectCount(ctx context.Context, conn driver.Conn, project uint16) (uint64, error) {
	var count uint64
	err := conn.QueryRow(ctx, "SELECT count() FROM builds WHERE project_id=?", project).Scan(&count)
	return count, err
}
