"""Versioned run telemetry: one JSON record per run (cost provenance, cache coverage, attempts), plus a readable line.

The JSON line is the contract with the bench runner. Missing values stay null; nothing is coerced to zero.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

TELEMETRY_PREFIX = "[quarry-telemetry] "
TELEMETRY_VERSION = 1
TELEMETRY_LINE = re.compile(r"\[quarry-telemetry\] (\{.*\})\s*$", re.M)


def _coverage(reported: int, total: int) -> str:
    if total == 0 or reported == 0:
        return "none"
    return "complete" if reported == total else "partial"


def cache_summary(records: List) -> Dict:
    """Read and write coverage, each with its own denominator (successful calls)."""
    ok = [r for r in records if r.ok]
    out: Dict = {"successful_calls": len(ok)}
    for key, field in (("read", "cached_tokens"), ("write", "cache_write_tokens")):
        reported = [getattr(r, field) for r in ok if getattr(r, field) is not None]
        out[key] = {
            "reported_calls": len(reported),
            "coverage": _coverage(len(reported), len(ok)),
            "tokens": sum(reported) if reported else None,
        }
    share_calls = [r for r in ok if r.cached_tokens is not None and r.prompt_tokens]
    prompt_total = sum(r.prompt_tokens for r in share_calls)
    out["read_share"] = {
        "value": round(sum(r.cached_tokens for r in share_calls) / prompt_total, 4) if prompt_total else None,
        "over_calls": len(share_calls),
        "coverage": _coverage(len(share_calls), len(ok)),
    }
    discounts = [r.cache_discount for r in ok if r.cache_discount is not None]
    out["reported_discount"] = {"sum": round(sum(discounts), 6) if discounts else None, "reported_calls": len(discounts)}
    return out


def call_rows(records: List) -> List[Dict]:
    rows = []
    for r in records:
        rows.append({
            "role": r.role, "model": r.model, "status": r.status, "ok": r.ok, "latency": round(r.latency, 2),
            "cost": None if r.cost is None else round(r.cost, 8), "cost_source": r.cost_source,
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "cached_tokens": r.cached_tokens, "cache_write_tokens": r.cache_write_tokens,
            "cache_discount": r.cache_discount, "note": (r.note or "")[:120],
        })
    return rows


def build_record(records: List, wallet, extra: Optional[Dict] = None) -> Dict:
    record = {
        "version": TELEMETRY_VERSION,
        "attempts": len(records),
        "cost": wallet.summary(),
        "cache": cache_summary(records),
        "calls": call_rows(records),
    }
    record.update(extra or {})
    return record


def format_line(record: Dict) -> str:
    return TELEMETRY_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def human_summary(record: Dict) -> str:
    cost, cache = record["cost"], record["cache"]
    parts = [f"attempts={record['attempts']}", f"cost: provider ${cost['provider_usd']:.4f} + estimate ${cost['estimate_usd']:.4f}"]
    if cost["estimated_calls"]:
        parts.append(f"({cost['estimated_calls']} estimated call(s))")
    if cost["unknown_attempts"]:
        parts.append(f"+ {cost['unknown_attempts']} unknown-cost attempt(s), ${cost['unknown_reserved_usd']:.4f} reserved; total unknown")
    read, write, share = cache["read"], cache["write"], cache["read_share"]
    parts.append(
        f"cache read reported {read['reported_calls']}/{cache['successful_calls']} (tokens {read['tokens']}), "
        f"write reported {write['reported_calls']}/{cache['successful_calls']} (tokens {write['tokens']}), "
        f"read share {share['value']} over {share['over_calls']} call(s)"
    )
    return " ".join(parts)


def parse_log(text: str) -> Optional[Dict]:
    """The last telemetry record in a log, or None. An unknown version is returned flagged, never trusted."""
    matches = TELEMETRY_LINE.findall(text or "")
    if not matches:
        return None
    try:
        record = json.loads(matches[-1])
    except ValueError:
        return {"version": None, "unsupported": True, "reason": "unparseable telemetry line"}
    if record.get("version") != TELEMETRY_VERSION:
        return {"version": record.get("version"), "unsupported": True, "reason": "unsupported telemetry version"}
    return record
