#!/usr/bin/env python3
"""Live bench (gates G6/G7): run dist/agent.py on a task set N times through `ridges miner run-local`.

Needs the ridges CLI (`uv sync --extra miner` in a ridges checkout, then `ridges miner setup` with an OpenRouter key)
and Docker. Writes bench/runs/<timestamp>/results.csv and prints a summary with a failure taxonomy.

Usage: python tools/run_bench.py --set public --repeats 3 [--tasks id1,id2] [--ridges "uv run --project ~/ridges ridges"]
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
from quarry.telemetry import parse_log  # noqa: E402  (shared parser: the agent's telemetry contract)
from tools.bench_records import (  # noqa: E402
    MAX_SETUP_REPLACEMENTS,
    auto_label,
    cli_version,
    expected_tasks,
    observe,
    task_digest,
    validity,
)

LEGACY_TELEMETRY = re.compile(r"\[quarry\] calls=(\d+) prompt_tokens=(\d+) cached_tokens=(\d+) cost=\$([\d.]+)")
KEY_ENDPOINT = "https://openrouter.ai/api/v1/key"
TELEMETRY_FIELDS = [
    "telemetry", "attempts", "cost_provider", "cost_estimate", "estimated_calls", "unknown_attempts",
    "unknown_reserved", "cost_accounted", "accounting_complete", "cache_read_reported", "cache_read_tokens",
    "cache_write_reported", "cache_write_tokens", "successful_calls", "read_share", "read_share_calls", "agent_sec",
]


def flatten_telemetry(record: Optional[Dict], legacy_text: str = "") -> Dict:
    """CSV fields from the agent's telemetry record. Anything not reported stays None (written as an empty cell)."""
    row: Dict = {field: None for field in TELEMETRY_FIELDS}
    if record is None:
        row["telemetry"] = "legacy-incomplete" if LEGACY_TELEMETRY.search(legacy_text or "") else "missing"
        return row
    if record.get("unsupported"):
        row["telemetry"] = f"unsupported ({record.get('reason')})"
        return row
    cost, cache = record.get("cost", {}), record.get("cache", {})
    row.update({
        "telemetry": f"v{record['version']}",
        "attempts": record.get("attempts"),
        "cost_provider": cost.get("provider_usd"),
        "cost_estimate": cost.get("estimate_usd"),
        "estimated_calls": cost.get("estimated_calls"),
        "unknown_attempts": cost.get("unknown_attempts"),
        "unknown_reserved": cost.get("unknown_reserved_usd"),
        "cost_accounted": cost.get("accounted_usd"),
        "accounting_complete": cost.get("accounting_complete"),
        "cache_read_reported": cache.get("read", {}).get("reported_calls"),
        "cache_read_tokens": cache.get("read", {}).get("tokens"),
        "cache_write_reported": cache.get("write", {}).get("reported_calls"),
        "cache_write_tokens": cache.get("write", {}).get("tokens"),
        "successful_calls": cache.get("successful_calls"),
        "read_share": cache.get("read_share", {}).get("value"),
        "read_share_calls": cache.get("read_share", {}).get("over_calls"),
        "agent_sec": record.get("elapsed_sec"),
    })
    return row


def telemetry_record(trial_dir: str):
    """(parsed record or None, raw log text) from the trial's agent logs."""
    texts = []
    for path in sorted(glob.glob(os.path.join(trial_dir, "**", "*.log"), recursive=True)):
        try:
            texts.append(open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            continue
    joined = "\n".join(texts)
    return parse_log(joined), joined


def telemetry_from(trial_dir: str) -> Dict:
    record, joined = telemetry_record(trial_dir)
    return flatten_telemetry(record, joined)


# ------------------------------------------------------------------ session ledger (host side, W1)


def read_key(environ: Optional[dict] = None) -> str:
    env = os.environ if environ is None else environ
    for name in ("RIDGES_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"):
        if env.get(name):
            return env[name].strip()
    path = os.path.expanduser("~/.ridges/.env.miner")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.strip().startswith("RIDGES_OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def fetch_key_usage(key: str) -> Optional[float]:
    """Cumulative USD usage of the key (free endpoint). None when unavailable; the key is never logged."""
    if not key:
        return None
    request = urllib.request.Request(KEY_ENDPOINT, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response).get("data", {})
        usage = data.get("usage")
        return float(usage) if isinstance(usage, (int, float)) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def settled_usage(fetch: Callable[[], Optional[float]], sleep: Callable[[float], None] = time.sleep,
                  wait: float = 5.0, tries: int = 6) -> Optional[float]:
    """Usage after billing has caught up: two equal reads `wait` seconds apart (bounded)."""
    last = fetch()
    for _ in range(tries):
        sleep(wait)
        current = fetch()
        if current is not None and current == last:
            return current
        last = current
    return last


class SessionLedger:
    """One shared spending envelope across runs, keyed by trial ID so re-recording a run never double-counts.

    Spent = key-usage delta since the ledger started when available (authoritative), else the sum of each run's
    best figure (reconciled > telemetry-consumed > its full allowance when nothing is known)."""

    def __init__(self, path: str, ceiling: float, fetch: Callable[[], Optional[float]]):
        self.path, self.ceiling, self.fetch = path, ceiling, fetch
        self.data = json.load(open(path)) if os.path.exists(path) else {"ceiling": ceiling, "start_usage": None, "runs": {}}
        if self.data.get("start_usage") is None:
            self.data["start_usage"] = fetch()
        self.data["ceiling"] = ceiling
        self.save()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as handle:
            json.dump(self.data, handle, indent=1)

    def spent(self) -> Dict:
        now, start = self.fetch(), self.data.get("start_usage")
        if now is not None and start is not None:
            return {"usd": round(now - start, 6), "source": "key-usage"}
        total = 0.0
        for run in self.data["runs"].values():
            for field in ("reconciled", "consumed", "allowance"):
                if isinstance(run.get(field), (int, float)):
                    total += run[field]
                    break
        return {"usd": round(total, 6), "source": "per-run records"}

    def fits(self, allowance: float) -> bool:
        return self.spent()["usd"] + allowance <= self.ceiling

    def record(self, trial_id: str, allowance: float, reconciled: Optional[float], consumed: Optional[float]) -> None:
        self.data["runs"][trial_id] = {"allowance": allowance, "reconciled": reconciled, "consumed": consumed}
        self.save()


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def run_one(ridges: List[str], task: str, agent: str, timeout: int, raw_path: str) -> Dict:
    started = time.time()
    cmd = ridges + ["miner", "run-local", "--non-interactive", "--task-path", task, "--agent-path", agent]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        output = f"FAILED: bench timeout\n{exc.stdout or ''}"
    with open(raw_path, "w", encoding="utf-8") as handle:
        handle.write(output)
    trial = re.search(r"^trial_dir:\s*(.+)$", output, re.M)
    trial_dir = trial.group(1).strip() if trial else ""
    record, joined = telemetry_record(trial_dir) if trial_dir else (None, "")
    obs = observe(trial_dir, output, record)
    row = {"task": os.path.basename(task), "reward": obs["reward"], "wall_sec": round(time.time() - started),
           "trial_dir": trial_dir}
    failed = re.search(r"^FAILED:\s*(.+)$", output, re.M)
    row["error"] = failed.group(1).strip() if failed else ""
    row.update({f"obs_{k}": v for k, v in obs.items() if k != "trial_dir"})
    row["validity"] = validity(obs)
    row["outcome"] = row["auto_label"] = auto_label(obs)
    row["manual_label"], row["manual_reason"] = "", ""
    row.update(flatten_telemetry(record, joined))
    return row


def format_cost(row: Dict) -> str:
    """Never prints an unknown cost as $0."""
    if row.get("reconciled_cost") is not None:
        return f"${row['reconciled_cost']:.4f} (key usage)"
    if row.get("cost_accounted") is not None:
        label = "complete" if row.get("accounting_complete") else f"partial, {row.get('unknown_attempts')} unknown"
        return f"${row['cost_accounted']:.4f} (telemetry, {label})"
    return "unknown"


def cost_report(rows: List[Dict]) -> str:
    reconciled = [r["reconciled_cost"] for r in rows if r.get("reconciled_cost") is not None]
    accounted = [r["cost_accounted"] for r in rows if r.get("cost_accounted") is not None]
    cache_rows = [r for r in rows if r.get("read_share") is not None]
    parts = [f"cost: key-usage reconciled on {len(reconciled)}/{len(rows)} runs"]
    if reconciled:
        parts.append(f"mean ${statistics.mean(reconciled):.4f} max ${max(reconciled):.4f}")
    parts.append(f"telemetry accounted on {len(accounted)}/{len(rows)}"
                 f" ({sum(1 for r in rows if r.get('accounting_complete'))} complete)")
    if cache_rows:
        parts.append(f"cache read share mean {statistics.mean(r['read_share'] for r in cache_rows):.0%}"
                     f" over {len(cache_rows)}/{len(rows)} runs reporting it")
    else:
        parts.append("cache read share: not reported")
    return "; ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", default="public", choices=["public", "dev", "heldout"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all in the set)")
    parser.add_argument("--agent", default=os.path.join(ROOT, "dist", "agent.py"))
    parser.add_argument("--ridges", default="ridges", help="command that runs the ridges CLI")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--min-solve", type=float, default=None, help="fail (exit 1) below this mean solve rate")
    parser.add_argument("--baseline", default="", help="results.csv of the last kept run; fail if tasks regress")
    parser.add_argument("--ceiling", type=float, default=30.0, help="shared local-inference envelope in USD")
    parser.add_argument("--allowance", type=float, default=0.29, help="per-run allowance reserved before launching")
    parser.add_argument("--ledger", default=os.path.join(ROOT, "bench", "runs", "ledger.json"))
    parser.add_argument("--no-key-usage", action="store_true", help="do not read the key's usage for reconciliation")
    args = parser.parse_args()

    tasks = sorted(glob.glob(os.path.join(ROOT, "bench", "tasks", args.set, "*", "task.toml")))
    tasks = [os.path.dirname(t) for t in tasks]
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if os.path.basename(t) in wanted]
    if not tasks:
        print("no tasks found", file=sys.stderr)
        return 2
    out_dir = os.path.join(ROOT, "bench", "runs", time.strftime("%Y%m%d-%H%M%S") + f"-{args.set}")
    os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
    manifest = {
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "set": args.set, "repeats": args.repeats,
        "agent": args.agent, "agent_sha256": sha256_file(args.agent),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain", "src"], cwd=ROOT, capture_output=True, text=True).stdout),
        "model_override": {k: v for k, v in os.environ.items() if k.startswith("QUARRY_")},
        "expected_tasks": expected_tasks(ROOT, args.set),
        "selected_tasks": [os.path.basename(t) for t in tasks],
        "tasks": {os.path.basename(t): task_digest(t) for t in tasks},
        "config": {"ceiling": args.ceiling, "allowance": args.allowance, "timeout": args.timeout, "ridges": args.ridges,
                   "max_setup_replacements": MAX_SETUP_REPLACEMENTS},
        "ridges_cli_commit": cli_version(os.path.expanduser("~/bittensor/ridges-cli")),
        "python": sys.version.split()[0],
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as handle:
        json.dump(manifest, handle, indent=1)
    key = read_key()
    fetch = (lambda: fetch_key_usage(key)) if not args.no_key_usage else (lambda: None)
    ledger = SessionLedger(args.ledger, args.ceiling, fetch)
    rows = []
    stopped = ""
    for repeat in range(1, args.repeats + 1):
        for task in tasks:
            if not ledger.fits(args.allowance):
                stopped = f"spending ceiling ${args.ceiling:.2f} reached ({ledger.spent()}); remaining runs not scheduled"
                break
            slot = f"{os.path.basename(out_dir)}/{os.path.basename(task)}/r{repeat}"
            for attempt in range(1, MAX_SETUP_REPLACEMENTS + 2):
                if attempt > 1 and not ledger.fits(args.allowance):
                    stopped = f"spending ceiling ${args.ceiling:.2f} reached during a setup replacement"
                    break
                trial_id = f"{slot}/a{attempt}"
                before = fetch()
                raw = os.path.join(out_dir, "raw", f"{os.path.basename(task)}-r{repeat}-a{attempt}.log")
                row = run_one(shlex.split(args.ridges), task, args.agent, args.timeout, raw)
                after = settled_usage(fetch) if before is not None else None
                row["reconciled_cost"] = round(after - before, 6) if (before is not None and after is not None) else None
                row.update({"repeat": repeat, "slot": slot, "attempt": attempt, "trial_id": trial_id,
                            "bundle_sha256": manifest["agent_sha256"][:16], "task_digest": manifest["tasks"][os.path.basename(task)]})
                ledger.record(trial_id, args.allowance, row["reconciled_cost"], row.get("cost_accounted"))
                rows.append(row)
                print(f"[{repeat}.{attempt}] {row['task']}: {row['outcome']} ({row['validity']}) reward={row['reward']} "
                      f"cost={format_cost(row)} wall={row['wall_sec']}s {row['error']}", flush=True)
                if row["validity"] != "void-infrastructure":
                    break
            else:
                print(f"slot {slot}: infrastructure-blocked after {MAX_SETUP_REPLACEMENTS} setup replacements")
            if stopped:
                break
        if stopped:
            break
    if stopped:
        print(stopped)
    if not rows:
        print("no runs executed", file=sys.stderr)
        return 1
    obs_fields = sorted({k for r in rows for k in r if k.startswith("obs_")})
    fields = ["trial_id", "slot", "attempt", "repeat", "task", "task_digest", "bundle_sha256", "validity", "auto_label",
              "manual_label", "manual_reason", "reward", "reconciled_cost"] + TELEMETRY_FIELDS + obs_fields + [
        "wall_sec", "error", "trial_dir"]
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    counted = [r for r in rows if r["validity"] != "void-infrastructure"]  # void attempts leave the denominator
    solved = [(r["reward"] or 0) >= 1 for r in counted]
    times = sorted((r.get("agent_sec") or r["wall_sec"]) for r in rows)
    outcomes: Dict[str, int] = {}
    for r in rows:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    per_task: Dict[str, List[bool]] = {}
    for r in rows:
        if r["validity"] != "void-infrastructure":
            per_task.setdefault(r["task"], []).append((r["reward"] or 0) >= 1)
    always = sorted(t for t, runs in per_task.items() if all(runs))
    mean = sum(solved) / len(counted) if counted else 0.0
    voids = len(rows) - len(counted)
    print(f"\nsolve rate (mean per counted run) {sum(solved)}/{len(counted)} = {mean:.2f}"
          f" ({voids} void infrastructure attempt(s) excluded)")
    print(f"solved in every repeat: {len(always)}/{len(per_task)} {always}")
    print(cost_report(rows))
    print(f"session ledger: {ledger.spent()} of ${args.ceiling:.2f}")
    print(f"time p50 {times[len(times) // 2]}s  max {times[-1]}s")
    print("taxonomy: " + ", ".join(f"{k}={v}" for k, v in sorted(outcomes.items())))
    print(f"results: {out_dir}/results.csv")

    failures = []
    if outcomes.get("mechanical"):
        failures.append(f"{outcomes['mechanical']} mechanical failure(s)")
    if args.min_solve is not None and mean < args.min_solve:
        failures.append(f"mean solve {mean:.2f} < {args.min_solve}")
    if args.baseline:
        with open(args.baseline, newline="") as handle:
            before: Dict[str, List[bool]] = {}
            for r in csv.DictReader(handle):
                before.setdefault(r["task"], []).append(float(r["reward"] or 0) >= 1)
        lost = sorted(t for t, runs in before.items() if all(runs) and t in per_task and not all(per_task[t]))
        if lost:
            failures.append(f"regressed vs baseline: {lost}")
    if stopped:
        failures.append(stopped)
    summary = {"mean_solve": mean, "always_solved": always, "outcomes": outcomes, "failures": failures,
               "cost": cost_report(rows), "ledger": ledger.spent()}
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    for failure in failures:
        print(f"GATE FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
