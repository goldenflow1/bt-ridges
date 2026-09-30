#!/bin/bash
set -euo pipefail
cd /app
python3 - <<'PYFIX'
from pathlib import Path
p=Path('observatory/report.py')
old='"""Tenant analytics backed by ClickHouse."""\n\n\ndef missing_devices(client, tenant):\n    """List events without an enabled device registration."""\n    return client.query(\'SELECT e.event_id AS event_id, e.device AS device FROM events e LEFT JOIN (SELECT tenant, device, device_id, label, 1 AS matched FROM devices WHERE enabled = 1) d ON e.tenant = d.tenant AND e.device = d.device WHERE e.tenant = {tenant:String} AND isNull(d.device_id) ORDER BY e.event_id\', {"tenant": tenant})\n\n\ndef service_name():\n    return "observatory"\n'
new='"""Tenant analytics backed by ClickHouse."""\n\n\ndef missing_devices(client, tenant):\n    """List events without an enabled device registration."""\n    return client.query(\'SELECT e.event_id AS event_id, e.device AS device FROM events e LEFT JOIN (SELECT tenant, device, device_id, label, 1 AS matched FROM devices WHERE enabled = 1) d ON e.tenant = d.tenant AND e.device = d.device WHERE e.tenant = {tenant:String} AND isNull(d.matched) ORDER BY e.event_id SETTINGS join_use_nulls = 1\', {"tenant": tenant})\n\n\ndef service_name():\n    return "observatory"\n'
assert p.read_text() == old, 'source drift'
p.write_text(new)
PYFIX
