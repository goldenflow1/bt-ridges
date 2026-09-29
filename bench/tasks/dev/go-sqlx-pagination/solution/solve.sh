#!/bin/bash
set -euo pipefail

cd /app
ANCHOR=$(cat <<'EOF'
	if after != nil {
		query += ` AND created_at > $2`
		args = append(args, after.CreatedAt)
	}
	query += fmt.Sprintf(` ORDER BY created_at LIMIT %d`, limit+1)
EOF
)
REPLACEMENT=$(cat <<'EOF'
	if after != nil {
		query += ` AND (created_at, id) > ($2, $3)`
		args = append(args, after.CreatedAt, after.ID)
	}
	query += fmt.Sprintf(` ORDER BY created_at, id LIMIT %d`, limit+1)
EOF
)
export ANCHOR REPLACEMENT
perl -0777 -i -pe '
  BEGIN { $anchor = $ENV{ANCHOR}; $replacement = $ENV{REPLACEMENT}; }
  $count = () = /\Q$anchor\E/g;
  die "frozen ListEvents anchor changed\n" unless $count == 1;
  s/\Q$anchor\E/$replacement/;
' internal/store/events.go

test -z "$(gofmt -l internal/store/events.go)"
go vet ./internal/store/
