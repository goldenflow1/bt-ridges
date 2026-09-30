package connection

import (
	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"time"
)

func Open(database string) (driver.Conn, error) {
	return clickhouse.Open(&clickhouse.Options{Addr: []string{"clickhouse:9000"},
		Auth:     clickhouse.Auth{Database: database, Username: "buildvault", Password: "buildvault-task-local"},
		Settings: clickhouse.Settings{"max_threads": 1, "use_query_cache": 0}, DialTimeout: 15 * time.Second})
}
