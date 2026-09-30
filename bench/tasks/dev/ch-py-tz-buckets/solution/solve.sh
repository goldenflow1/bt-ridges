#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('observatory/report.py')
old='"""Tenant analytics backed by ClickHouse."""\n\n\ndef daily_events(client, tenant, start_day, end_day, zone):\n    """Count events on local calendar days, including empty days."""\n    return []\n\n\ndef service_name():\n    return "observatory"\n'
new='"""Tenant analytics backed by ClickHouse."""\n\n\ndef daily_events(client, tenant, start_day, end_day, zone):\n    """Count events on local calendar days, including empty days."""\n    return client.query("WITH toDate({start:String}) AS first, toDate({end:String}) AS stop SELECT toString(days.day) AS day, ifNull(totals.events, 0) AS events FROM (SELECT addDays(first, number) AS day FROM numbers(toUInt64(greatest(dateDiff(\'day\', first, stop), 0)))) days LEFT JOIN (SELECT toDate(happened, {zone:String}) AS day, count() AS events FROM events WHERE tenant = {tenant:String} AND happened >= toDateTime(first, {zone:String}) AND happened < toDateTime(stop, {zone:String}) GROUP BY day) totals ON days.day = totals.day ORDER BY days.day", {"tenant": tenant, "start": start_day, "end": end_day, "zone": zone})\n\n\ndef service_name():\n    return "observatory"\n'
assert p.read_text() == old, 'source drift'
p.write_text(new)
PYFIX
