#!/bin/bash
set -euo pipefail

cd /app
node - <<'JS'
const fs = require("node:fs");
const path = "src/reports.ts";
const text = fs.readFileSync(path, "utf8");
const anchor =
  "      COALESCE(COUNT(e.completed_at) * 100 / NULLIF(COUNT(e.id), 0), 0) AS completion_rate\n";
const replacement =
  "      COALESCE(ROUND(COUNT(e.completed_at) * 100.0 / NULLIF(COUNT(e.id), 0), 1), 0) AS completion_rate\n";
if (text.split(anchor).length !== 2) {
  console.error("frozen completion-rate anchor changed");
  process.exit(1);
}
fs.writeFileSync(path, text.replace(anchor, replacement));
JS

npx tsc --noEmit
