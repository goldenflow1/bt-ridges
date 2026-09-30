#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('observatory/report.py')
old='"""Tenant analytics backed by ClickHouse."""\n\n\ndef visitor_count(client, tenant, start, end):\n    """Count identified visitors in a half-open UTC interval."""\n    return client.query(\'SELECT uniq(visitor) AS visitors FROM visits WHERE tenant = {tenant:String} AND happened >= {start:DateTime} AND happened < {end:DateTime}\', {"tenant": tenant, "start": start, "end": end})\n\n\ndef service_name():\n    return "observatory"\n'
new='"""Tenant analytics backed by ClickHouse."""\n\n\ndef visitor_count(client, tenant, start, end):\n    """Count identified visitors in a half-open UTC interval."""\n    return client.query(\'SELECT uniqExact(visitor) AS visitors FROM visits WHERE tenant = {tenant:String} AND happened >= {start:DateTime} AND happened < {end:DateTime}\', {"tenant": tenant, "start": start, "end": end})\n\n\ndef service_name():\n    return "observatory"\n'
assert p.read_text() == old, 'source drift'
p.write_text(new)
PYFIX
