from django.db.models import Exists, OuterRef, Q

from app.models import Block, Customer

__all__ = ["Exists", "OuterRef", "eligible_customers"]


def eligible_customers(tenant_id, as_of):
    """Return eligible customer IDs in ascending order for one tenant at as_of."""
    blocked = Block.objects.filter(tenant_id=tenant_id, active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=as_of)).values('customer_id')
    return list(Customer.objects.filter(tenant_id=tenant_id).exclude(pk__in=blocked).order_by('id').values_list('id', flat=True))
