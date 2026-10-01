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


def proxy_summary(log_path):
    """Per-trial totals from a fault proxy log (B-FAULT-03): every request of the trial passed through it."""
    import json
    import os

    entries = []
    if log_path and os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as handle:
            entries = [json.loads(line) for line in handle if line.strip()]
    forwarded = [e for e in entries if e.get("upstream_status") is not None]
    real = [amount(e.get("real_cost")) for e in forwarded if e.get("upstream_status") == 200]
    models = {}
    for entry in entries:
        models[entry.get("model") or "?"] = models.get(entry.get("model") or "?", 0) + 1
    return {
        "proxy_requests": len(entries),
        "proxy_injected_before": sum(1 for e in entries if e.get("stage") == "before"),
        "proxy_injected_after": sum(1 for e in entries if e.get("stage") == "after" and e.get("rule") != "cost_multiplier"),
        "proxy_real_cost": round(sum(c for c in real if c is not None), 6),
        "proxy_reported_cost": round(sum(amount(e.get("reported_cost")) or 0.0 for e in forwarded), 6),
        "proxy_real_cost_complete": all(c is not None for c in real),
        "proxy_models": json.dumps(models, sort_keys=True),
    }


def reconcile_proxy(delta, summary):
    """Fault runs: the agent's reported cost is deliberately altered, so match key usage against the proxy's real cost."""
    real = amount(summary.get("proxy_real_cost"))
    if amount(delta) is None:
        reason = "key usage unavailable or invalid"
    elif real is None or not summary.get("proxy_real_cost_complete"):
        reason = "proxy real cost incomplete"
    elif abs(delta - real) > max(0.0001, 0.05 * max(delta, real)):
        reason = "key usage differs from proxy real cost"
    else:
        return {"key_usage_delta": delta, "reconciled_cost": delta, "cost_reconciliation": "matched-proxy"}
    return {"key_usage_delta": delta, "reconciled_cost": None, "cost_reconciliation": reason}
