package main

import (
	"buildvault/internal/builds"
	"buildvault/internal/connection"
	"buildvault/internal/migrate"
	"context"
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	if len(os.Args) != 2 {
		panic("usage: buildvault JOB_ID")
	}
	conn, err := connection.Open(os.Getenv("BUILDVAULT_DATABASE"))
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	ctx := context.Background()
	if err = migrate.Apply(ctx, conn, "migrations", "0002_job_index.sql", false); err != nil {
		panic(err)
	}
	rows, stats, err := builds.Lookup(ctx, conn, os.Args[1])
	if err != nil {
		panic(err)
	}
	data, err := json.Marshal(struct {
		Builds  []builds.Build
		Metrics builds.Metrics
	}{rows, stats})
	if err != nil {
		panic(err)
	}
	fmt.Println(string(data))
}
