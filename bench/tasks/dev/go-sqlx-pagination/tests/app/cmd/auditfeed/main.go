// Command auditfeed serves a tenant's audit trail as a paginated JSON feed.
//
//	GET /tenants/{tenant}/events?cursor=...&limit=...
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	"auditfeed/internal/store"
)

func main() {
	addr := flag.String("addr", ":8080", "listen address")
	dump := flag.String("dump", "", "print every event of a tenant, page by page, and exit")
	pageSize := flag.Int("limit", 0, "page size for -dump")
	flag.Parse()

	db, err := store.Open(os.Getenv("AUDITFEED_DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	s := store.New(db)

	if *dump != "" {
		if err := dumpTenant(s, *dump, *pageSize); err != nil {
			log.Fatal(err)
		}
		return
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /tenants/{tenant}/events", func(w http.ResponseWriter, r *http.Request) {
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		page, err := s.ListEvents(r.Context(), r.PathValue("tenant"), r.URL.Query().Get("cursor"), limit)
		if errors.Is(err, store.ErrBadCursor) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err != nil {
			log.Printf("list events: %v", err)
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(page)
	})
	fmt.Fprintf(os.Stderr, "auditfeed listening on %s\n", *addr)
	log.Fatal(http.ListenAndServe(*addr, mux))
}

// dumpTenant walks every page of a tenant's feed and prints one line per event.
func dumpTenant(s *store.Store, tenant string, limit int) error {
	ctx := context.Background()
	cursor := ""
	for n := 1; ; n++ {
		page, err := s.ListEvents(ctx, tenant, cursor, limit)
		if err != nil {
			return err
		}
		for _, e := range page.Events {
			fmt.Printf("page %-3d %6d  %s  %-10s %-16s %s\n",
				n, e.ID, e.CreatedAt.UTC().Format("2006-01-02 15:04:05.000000"), e.Actor, e.Action, e.Target)
		}
		if page.NextCursor == "" {
			return nil
		}
		cursor = page.NextCursor
	}
}
