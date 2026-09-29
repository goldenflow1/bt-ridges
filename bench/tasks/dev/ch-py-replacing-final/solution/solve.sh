#!/bin/bash
set -euo pipefail

cd /app
python - <<'PY'
from pathlib import Path

path = Path('meterline/balances.py')
text = path.read_text()
anchor = """        SELECT
            currency,
            count() AS accounts,
            sum(balance_minor) AS balance_minor
        FROM account_balances
        WHERE tenant_id = {tenant_id:String}
          AND status = 'active'
        GROUP BY currency
        ORDER BY currency
"""
replacement = """        SELECT
            currency,
            count() AS accounts,
            sum(balance_minor) AS balance_minor
        FROM
        (
            SELECT
                account_id,
                argMax(currency, revision) AS currency,
                argMax(balance_minor, revision) AS balance_minor,
                argMax(status, revision) AS status
            FROM account_balances
            WHERE tenant_id = {tenant_id:String}
            GROUP BY account_id
        )
        WHERE status = 'active'
        GROUP BY currency
        ORDER BY currency
"""
if text.count(anchor) != 1:
    raise SystemExit('frozen tenant balance summary anchor changed')
path.write_text(text.replace(anchor, replacement, 1))
PY

ruff check --no-cache meterline/balances.py
