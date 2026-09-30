#!/bin/bash
set -euo pipefail
cd /app
python - <<'PYFIX'
from pathlib import Path
p=Path('app/reports.py')
assert p.read_text() == 'from django.db.models import Exists, OuterRef, Q\n\nfrom app.models import Block, Customer\n\n__all__ = ["Exists", "OuterRef", "eligible_customers"]\n\n\ndef eligible_customers(tenant_id, as_of):\n    """Return eligible customer IDs in ascending order for one tenant at as_of."""\n    blocked = Block.objects.filter(tenant_id=tenant_id, active=True).filter(\n        Q(expires_at__isnull=True) | Q(expires_at__gt=as_of)).values(\'customer_id\')\n    return list(Customer.objects.filter(tenant_id=tenant_id).exclude(pk__in=blocked).order_by(\'id\').values_list(\'id\', flat=True))\n'
p.write_text('from django.db.models import Exists, OuterRef, Q\n\nfrom app.models import Block, Customer\n\n__all__ = ["Exists", "OuterRef", "eligible_customers"]\n\n\ndef eligible_customers(tenant_id, as_of):\n    """Return eligible customer IDs in ascending order for one tenant at as_of."""\n    blocked = Block.objects.filter(tenant_id=tenant_id, active=True, customer_id=OuterRef(\'pk\')).filter(\n        Q(expires_at__isnull=True) | Q(expires_at__gt=as_of)).values(\'customer_id\')\n    return list(Customer.objects.filter(tenant_id=tenant_id).filter(~Exists(blocked)).order_by(\'id\').values_list(\'id\', flat=True))\n')
PYFIX
