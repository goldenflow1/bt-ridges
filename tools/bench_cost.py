"""Trial cost attribution, independent of the account-wide spending envelope."""

import math


def amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def reconcile(row, delta):
    """Keep the raw delta even when it cannot be attributed to this trial."""
    provider = amount(row.get("cost_provider"))
    complete = str(row.get("accounting_complete")).lower() == "true"
    known = complete and amount(row.get("estimated_calls")) == 0 and amount(row.get("unknown_attempts")) == 0
    if amount(delta) is None:
        reason = "key usage unavailable or invalid"
    elif provider is None or not known:
        reason = "complete provider billing unavailable"
    elif abs(delta - provider) > max(0.0001, 0.05 * max(delta, provider)):
        reason = "key usage differs from provider billing"
    else:
        return {"key_usage_delta": delta, "reconciled_cost": delta, "cost_reconciliation": "matched"}
    return {"key_usage_delta": delta, "reconciled_cost": None, "cost_reconciliation": reason}


def trusted_cost(row):
    """Validate stored evidence too, so old contaminated records cannot pass a gate."""
    cost = amount(row.get("reconciled_cost"))
    if cost is None:
        return None
    if row.get("cost_reconciliation") not in (None, "", "matched"):
        return None
    if "cost_provider" in row and reconcile(row, cost)["reconciled_cost"] is None:
        return None
    return cost
