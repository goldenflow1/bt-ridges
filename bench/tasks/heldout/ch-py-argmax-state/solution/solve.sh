#!/bin/bash
set -euo pipefail
cd /app
python - <<'PYFIX'
from pathlib import Path
p = Path('grid/reports/current.py')
assert p.read_text() == 'def online_query():\n    """SQL for the regional operations panel."""\n    return "SELECT meter_id, snapshot.1 AS state, snapshot.2 AS region, snapshot.3 AS reading,\\n       toUnixTimestamp64Micro(snapshot.4) AS observed_us, snapshot.5 AS version\\nFROM (\\n  SELECT meter_id, argMax(tuple(state, region, reading, observed_at, version), observed_at) AS snapshot\\n  FROM meter_events\\n  WHERE utility = {utility:String} AND state = \'online\' AND region = {region:String}\\n  GROUP BY meter_id\\n)\\nWHERE state = \'online\' AND region = {region:String}\\nORDER BY meter_id"\n', "source anchor changed"
p.write_text('def online_query():\n    """SQL for the regional operations panel."""\n    return "SELECT meter_id, snapshot.1 AS state, snapshot.2 AS region, snapshot.3 AS reading,\\n       toUnixTimestamp64Micro(snapshot.4) AS observed_us, snapshot.5 AS version\\nFROM (\\n  SELECT meter_id, argMax(tuple(state, region, reading, observed_at, version), tuple(observed_at, version)) AS snapshot\\n  FROM meter_events\\n  WHERE utility = {utility:String}\\n  GROUP BY meter_id\\n)\\nWHERE state = \'online\' AND region = {region:String}\\nORDER BY meter_id"\n')
PYFIX
