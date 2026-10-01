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
    if row.get("cost_reconciliation") == "matched-proxy":
        # Fault run: validate against the proxy evidence stored in the row, never against the (altered) agent cost.
        return cost if reconcile_proxy(cost, row)["reconciled_cost"] is not None else None
    if row.get("cost_reconciliation") not in (None, "", "matched"):
        return None
    if "cost_provider" in row and reconcile(row, cost)["reconciled_cost"] is None:
        return None
    return cost


def _flag(value) -> bool:
    return value is True or str(value).lower() == "true"


def proxy_summary(log_path):
    """Per-trial accounting from a fault proxy log (B-FAULT-03). Complete only with evidence for every request:
    the log exists with `proxy_start` and `proxy_stop`, nothing was outstanding at stop, every `request_start` has a
    `request_end`, and no forwarded request has an uncertain charge. A missing log is missing evidence, not $0."""
    import json
    import os

    if not log_path or not os.path.exists(log_path):
        return {"proxy_log_present": False, "proxy_complete": False, "proxy_requests": None, "proxy_real_cost": None,
                "proxy_reported_cost": None, "proxy_uncertain": None, "proxy_unscaled": None,
                "proxy_injected_before": None, "proxy_injected_after": None, "proxy_models": None}
    with open(log_path, encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    starts = {r["index"] for r in records if r.get("event") == "request_start"}
    ends = [r for r in records if r.get("event") == "request_end"]
    stops = [r for r in records if r.get("event") == "proxy_stop"]
    known = [amount(e.get("real_cost")) for e in ends if e.get("charge") == "known"]
    models = {}
    for entry in ends:
        models[entry.get("model") or "?"] = models.get(entry.get("model") or "?", 0) + 1
    uncertain = sum(1 for e in ends if e.get("charge") == "uncertain")
    unfinished = len(starts - {e["index"] for e in ends})
    complete = (any(r.get("event") == "proxy_start" for r in records) and len(stops) == 1
                and stops[0].get("outstanding") == 0 and unfinished == 0 and uncertain == 0
                and all(c is not None for c in known))
    return {
        "proxy_log_present": True,
        "proxy_complete": complete,
        "proxy_requests": len(ends),
        "proxy_unfinished": unfinished,
        "proxy_uncertain": uncertain,
        "proxy_injected_before": sum(1 for e in ends if e.get("stage") == "before"),
        "proxy_injected_after": sum(1 for e in ends if e.get("stage") in ("after", "forward_error") and e.get("rule") != "cost_multiplier"),
        "proxy_real_cost": round(sum(c for c in known if c is not None), 6),
        "proxy_reported_cost": round(sum(amount(e.get("reported_cost")) or 0.0 for e in ends if e.get("upstream_status") == 200), 6),
        "proxy_unscaled": sum(1 for e in ends if e.get("rule") == "cost_multiplier" and not e.get("scaled")),
        "proxy_models": json.dumps(models, sort_keys=True),
    }


def reconcile_proxy(delta, summary):
    """Fault runs: the agent's reported cost is deliberately altered, so match key usage against the proxy's real
    cost, and only when the proxy accounting is complete."""
    real = amount(summary.get("proxy_real_cost"))
    if amount(delta) is None:
        reason = "key usage unavailable or invalid"
    elif not _flag(summary.get("proxy_complete")) or real is None:
        reason = "proxy accounting incomplete"
    elif abs(delta - real) > max(0.0001, 0.05 * max(delta, real)):
        reason = "key usage differs from proxy real cost"
    else:
        return {"key_usage_delta": delta, "reconciled_cost": delta, "cost_reconciliation": "matched-proxy"}
    return {"key_usage_delta": delta, "reconciled_cost": None, "cost_reconciliation": reason}
