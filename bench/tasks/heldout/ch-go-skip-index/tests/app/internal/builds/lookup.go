package builds

import (
	"context"
	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"sync/atomic"
	"time"
)

type Build struct {
	BuildID   uint64
	ProjectID uint16
	JobID     string
	StartedAt time.Time
	Outcome   string
}

type Metrics struct{ RowsRead uint64 }

func Lookup(ctx context.Context, conn driver.Conn, jobID string) ([]Build, Metrics, error) {
	var read uint64
	measured := clickhouse.Context(ctx, clickhouse.WithSettings(clickhouse.Settings{"max_threads": 1, "use_query_cache": 0}),
		clickhouse.WithProgress(func(p *clickhouse.Progress) { atomic.AddUint64(&read, p.Rows) }))
	rows, err := conn.Query(measured, "SELECT build_id,project_id,job_id,started_at,outcome FROM builds WHERE job_id=? ORDER BY started_at,build_id", jobID)
	if err != nil {
		return nil, Metrics{}, err
	}
	defer rows.Close()
	result := []Build{}
	for rows.Next() {
		var row Build
		if err = rows.Scan(&row.BuildID, &row.ProjectID, &row.JobID, &row.StartedAt, &row.Outcome); err != nil {
			return nil, Metrics{}, err
		}
		result = append(result, row)
	}
	if err = rows.Err(); err != nil {
		return nil, Metrics{}, err
	}
	return result, Metrics{RowsRead: atomic.LoadUint64(&read)}, nil
}
