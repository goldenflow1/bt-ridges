#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('observatory/report.py')
old='"""Tenant analytics backed by ClickHouse."""\n\n\ndef settled_total(client, tenant, start, end):\n    """Sum settled amounts for one tenant and half-open UTC interval."""\n    return client.query("SELECT sum(amount) AS total FROM events WHERE cityHash64(tenant_id) = cityHash64({tenant:UInt32}) AND happened >= {start:DateTime} AND happened < {end:DateTime} AND status = \'settled\' SETTINGS max_threads = 1, use_query_cache = 0", {"tenant": tenant, "start": start, "end": end})\n\n\ndef service_name():\n    return "observatory"\n'
new='"""Tenant analytics backed by ClickHouse."""\n\n\ndef settled_total(client, tenant, start, end):\n    """Sum settled amounts for one tenant and half-open UTC interval."""\n    return client.query("SELECT sum(amount) AS total FROM events WHERE tenant_id = {tenant:UInt32} AND happened >= {start:DateTime} AND happened < {end:DateTime} AND status = \'settled\' SETTINGS max_threads = 1, use_query_cache = 0", {"tenant": tenant, "start": start, "end": end})\n\n\ndef service_name():\n    return "observatory"\n'
assert p.read_text() == old, 'source drift'
p.write_text(new)
PYFIX
