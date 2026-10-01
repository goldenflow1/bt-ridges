#!/usr/bin/env python3
"""Live bench (gates G6/G7): run dist/agent.py on a task set N times through `ridges miner run-local`.

Needs the ridges CLI (`uv sync --extra miner` in a ridges checkout, then `ridges miner setup` with an OpenRouter key)
and Docker. Writes bench/runs/<timestamp>/results.csv and prints a summary with a failure taxonomy.

Usage: python tools/run_bench.py --set public --repeats 3 [--tasks id1,id2] [--ridges "uv run --project ~/ridges ridges"]
"""

from __future__ import annotations

import argparse
import csv
import fcntl
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
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
from quarry.telemetry import parse_log  # noqa: E402  (shared parser: the agent's telemetry contract)
from tools.bench_cost import proxy_summary, reconcile, reconcile_proxy  # noqa: E402
from tools.bench_records import (  # noqa: E402
    MAX_SETUP_REPLACEMENTS,
    ImageWatcher,
    auto_label,
    cli_version,
    expected_tasks,
    finalization_events,
    host_identity,
    inputs_unchanged,
    observe,
    outcome_category,
    task_digest,
    trial_images,
    validity,
)
from tools.fault_proxy import FaultProxy, load_scenario  # noqa: E402

LEGACY_TELEMETRY = re.compile(r"\[quarry\] calls=(\d+) prompt_tokens=(\d+) cached_tokens=(\d+) cost=\$([\d.]+)")
KEY_ENDPOINT = "https://openrouter.ai/api/v1/key"
TELEMETRY_FIELDS = [
    "telemetry", "attempts", "cost_provider", "cost_estimate", "estimated_calls", "unknown_attempts",
    "unknown_reserved", "cost_accounted", "accounting_complete", "cache_read_reported", "cache_read_tokens",
    "cache_write_reported", "cache_write_tokens", "successful_calls", "read_share", "read_share_calls", "agent_sec",
]


@contextmanager
def bench_lock(identity):
    """Exclude concurrent local consumers of the same key/ledger; never expose the key."""
    digest = hashlib.sha256(identity.encode()).hexdigest()
    path = os.path.join('/tmp', 'quarry-bench-' + digest + '.lock')
    with open(path, 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another benchmark holds this key or ledger; wait for it to finish.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def save_results(out_dir, rows):
    if not rows:
        return
    obs_fields = sorted({k for row in rows for k in row if k.startswith('obs_')})
    fault_fields = sorted({k for row in rows for k in row if k.startswith('proxy_') or k == 'fault_scenario'})
    fault_fields += sorted({k for row in rows for k in row if k.startswith('fin_')})
    fault_fields += [k for k in ('outcome_category', 'arm', 'pair_id', 'arm_position') if any(k in row for row in rows)]
    fields = ['trial_id', 'purpose', 'slot', 'attempt', 'repeat', 'task', 'task_digest', 'bundle_sha256', 'inputs_changed',
              'images', 'validity', 'auto_label', 'manual_label', 'manual_reason', 'reward', 'reconciled_cost',
              'key_usage_delta', 'cost_reconciliation'] + TELEMETRY_FIELDS + obs_fields + fault_fields + ['wall_sec', 'error', 'trial_dir']
    temp = os.path.join(out_dir, 'results.csv.tmp')
    with open(temp, 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, os.path.join(out_dir, 'results.csv'))


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
        """Atomic replacement: a crash while saving leaves the previous ledger, never a truncated one."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        temp = self.path + ".tmp"
        with open(temp, "w") as handle:
            json.dump(self.data, handle, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)

    def spent(self) -> Dict:
        now, start = self.fetch(), self.data.get("start_usage")
        if now is not None and start is not None:
            return {"usd": round(now - start, 6), "source": "key-usage"}
        total = 0.0
        for run in self.data["runs"].values():
            if run.get("pending"):
                total += run.get("allowance") or 0.0
                continue
            for field in ("reconciled", "consumed", "allowance"):
                if isinstance(run.get(field), (int, float)):
                    total += run[field]
                    break
        return {"usd": round(total, 6), "source": "per-run records"}

    def pending(self) -> float:
        """Allowances reserved for trials that have not been recorded (in flight, or interrupted by a crash)."""
        return sum(r.get("allowance") or 0.0 for r in self.data["runs"].values() if r.get("pending"))

    def fits(self, allowance: float) -> bool:
        spent = self.spent()
        held = self.pending() if spent["source"] == "key-usage" else 0.0  # per-run records already count them
        return spent["usd"] + held + allowance <= self.ceiling

    def reserve(self, trial_id: str, allowance: float) -> None:
        """Persist the allowance before dispatch, so a crash or late key usage cannot leave a reservation gap."""
        self.data["runs"][trial_id] = {"allowance": allowance, "reconciled": None, "consumed": None, "pending": True}
        self.save()

    def record(self, trial_id: str, allowance: float, reconciled: Optional[float], consumed: Optional[float]) -> None:
        """Settle a trial. Only a reconciled real cost releases its reservation; otherwise the allowance stays held
        (E016 follow-up P1): an unchanged usage reading does not prove no delayed charge is coming."""
        self.data["runs"][trial_id] = {"allowance": allowance, "reconciled": reconciled, "consumed": consumed,
                                       "pending": reconciled is None}
        self.save()

    def settle(self, trial_id: str, real_cost: float) -> None:
        """Release a held reservation after its real cost was established by other evidence (manual reconciliation)."""
        run = self.data["runs"][trial_id]
        run.update(reconciled=real_cost, pending=False, settled_manually=True)
        self.save()


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class StopConditions:
    """Declared stop conditions, enforced by the scheduler (E016 follow-up P1). Each returns a reason once met."""

    def __init__(self, billing_mismatch: bool, input_change: bool, max_blocked: Optional[int],
                 max_incomplete: Optional[int]):
        self.billing_mismatch, self.input_change = billing_mismatch, input_change
        self.max_blocked, self.max_incomplete = max_blocked, max_incomplete
        self.blocked = 0
        self.incomplete_run = 0

    def after_trial(self, row: Dict) -> str:
        reconciliation = str(row.get("cost_reconciliation") or "")
        if self.billing_mismatch and "differs" in reconciliation:
            return f"billing mismatch on {row.get('trial_id')}: {reconciliation}"
        if self.input_change and row.get("inputs_changed"):
            return f"inputs changed during {row.get('trial_id')}: {row['inputs_changed']}"
        complete = reconciliation in ("matched", "matched-proxy")
        self.incomplete_run = 0 if complete else self.incomplete_run + 1
        if self.max_incomplete and self.incomplete_run >= self.max_incomplete:
            return f"{self.incomplete_run} consecutive trials without complete cost accounting"
        return ""

    def after_blocked_slot(self) -> str:
        self.blocked += 1
        if self.max_blocked and self.blocked >= self.max_blocked:
            return f"{self.blocked} infrastructure-blocked slots"
        return ""


class ExperimentEnvelope:
    """Experiment-level spending control, checked before every dispatch: real settled cost plus held (unreconciled)
    allowances plus the next allowance must fit the limit, and the key must keep `keep_headroom` of unspent limit.
    Unknown key headroom refuses dispatch (fail closed). With a `state_path` (one per experiment identity, e.g.
    e016-pilot) the settled cost and held reservations persist, so a relaunch continues the same envelope instead of
    starting from zero (E016 second follow-up)."""

    def __init__(self, limit: Optional[float], keep_headroom: Optional[float],
                 key_remaining: Callable[[], Optional[float]], state_path: Optional[str] = None):
        self.limit, self.keep_headroom, self.key_remaining = limit, keep_headroom, key_remaining
        self.state_path = state_path
        self.settled = 0.0
        self.held: Dict[str, float] = {}
        if state_path and os.path.exists(state_path):
            with open(state_path) as handle:
                state = json.load(handle)
            if limit is not None and state.get("limit") is not None and float(state["limit"]) != float(limit):
                raise RuntimeError(f"experiment envelope {state_path} was declared with limit ${state['limit']}, "
                                   f"not ${limit}; refusing to relaunch under a different limit")
            self.settled = float(state.get("settled") or 0.0)
            self.held = {k: float(v) for k, v in (state.get("held") or {}).items()}

    def save(self) -> None:
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        temp = self.state_path + ".tmp"
        with open(temp, "w") as handle:
            json.dump({"limit": self.limit, "settled": round(self.settled, 6), "held": self.held}, handle, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.state_path)

    def reserve(self, trial_id: str, allowance: float) -> None:
        self.held[trial_id] = allowance
        self.save()

    def settle(self, trial_id: str, real_cost: Optional[float]) -> None:
        if real_cost is None:
            return  # unresolved: the allowance stays held, across relaunches too
        self.held.pop(trial_id, None)
        self.settled += float(real_cost)
        self.save()

    def refusal(self, allowance: float) -> str:
        held = sum(self.held.values())
        if self.limit is not None and self.settled + held + allowance > self.limit:
            return (f"experiment spend limit ${self.limit:.2f}: settled ${self.settled:.4f} + held ${held:.2f} "
                    f"+ next ${allowance:.2f} would exceed it")
        if self.keep_headroom is not None:
            remaining = self.key_remaining()
            if remaining is None:
                return "key headroom unknown; not dispatching (fail closed)"
            if remaining - held - allowance < self.keep_headroom:
                return (f"key headroom: ${remaining:.2f} left - held ${held:.2f} - next ${allowance:.2f} "
                        f"< retained ${self.keep_headroom:.2f}")
        return ""


def fetch_key_remaining(key: str) -> Optional[float]:
    """The key's unspent limit (`limit_remaining`) from the free key endpoint; None when unavailable."""
    if not key:
        return None
    request = urllib.request.Request(KEY_ENDPOINT, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            value = json.load(response).get("data", {}).get("limit_remaining")
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def run_one(ridges: List[str], task: str, agent: str, timeout: int, raw_path: str,
            extra_args: Optional[List[str]] = None, extra_env: Optional[Dict[str, str]] = None) -> Dict:
    started = time.time()
    cmd = ridges + ["miner", "run-local", "--non-interactive", "--task-path", task, "--agent-path", agent] + (extra_args or [])
    env = dict(os.environ, **(extra_env or {}))
    with ImageWatcher(os.path.basename(os.path.normpath(task))) as watcher:
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
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
           "trial_dir": trial_dir, "images": json.dumps(trial_images(trial_dir, seen=watcher.seen), sort_keys=True)}
    failed = re.search(r"^FAILED:\s*(.+)$", output, re.M)
    row["error"] = failed.group(1).strip() if failed else ""
    row.update({f"obs_{k}": v for k, v in obs.items() if k != "trial_dir"})
    row["validity"] = validity(obs)
    row["outcome"] = row["auto_label"] = auto_label(obs)
    row["manual_label"], row["manual_reason"] = "", ""
    runtime_log = ""
    if trial_dir and os.path.exists(os.path.join(trial_dir, "agent", "runtime.log")):
        with open(os.path.join(trial_dir, "agent", "runtime.log"), encoding="utf-8", errors="replace") as handle:
            runtime_log = handle.read()
    row["outcome_category"] = outcome_category(trial_dir, obs, runtime_log)
    row.update(finalization_events(runtime_log))
    row.update(flatten_telemetry(record, joined))
    return row


def run_slot(attempt_fn: Callable[[int], Dict], fits: Callable[[], bool],
             max_replacements: int = MAX_SETUP_REPLACEMENTS):
    """One planned trial slot: the first attempt, plus up to `max_replacements` replacements for attempts voided
    by infrastructure. Returns (attempt rows, infrastructure_blocked, stop_reason). Valid failures are never
    replaced; every physical attempt is kept."""
    rows: List[Dict] = []
    for attempt in range(1, max_replacements + 2):
        if attempt > 1 and not fits():
            return rows, False, "spending ceiling reached during a setup replacement"
        row = attempt_fn(attempt)
        rows.append(row)
        if row["validity"] != "void-infrastructure":
            return rows, False, ""
    return rows, True, ""


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
    # Older runners do not hold this lock: the per-trial reconciliation also detects unrelated usage.
    key = read_key()
    lock_parser = argparse.ArgumentParser(add_help=False)
    lock_parser.add_argument('--ledger', default=os.path.join(ROOT, 'bench', 'runs', 'ledger.json'))
    lock_args, _ = lock_parser.parse_known_args()
    try:
        with bench_lock('ledger:' + os.path.realpath(lock_args.ledger)), bench_lock('key:' + key if key else 'no-key'):
            return run_bench()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def run_bench() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", default="public", choices=["public", "dev", "heldout"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all in the set)")
    parser.add_argument("--agent", default=os.path.join(ROOT, "dist", "agent.py"))
    parser.add_argument("--agent-b", default="",
                        help="paired comparison: a second bundle; each task and repeat runs both, order counterbalanced")
    parser.add_argument("--ridges", default="ridges", help="command that runs the ridges CLI")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--min-solve", type=float, default=None, help="fail (exit 1) below this mean solve rate")
    parser.add_argument("--baseline", default="", help="results.csv of the last kept run; fail if tasks regress")
    parser.add_argument("--ceiling", type=float, default=30.0, help="shared local-inference envelope in USD")
    parser.add_argument("--allowance", type=float, default=0.29, help="per-run allowance reserved before launching")
    parser.add_argument("--ledger", default=os.path.join(ROOT, "bench", "runs", "ledger.json"))
    parser.add_argument("--no-key-usage", action="store_true", help="do not read the key's usage for reconciliation")
    parser.add_argument("--fault-scenario", default="",
                        help="route every trial through tools/fault_proxy.py with this scenario JSON (B-FAULT-03)")
    parser.add_argument("--fault-host", default="172.17.0.1",
                        help="address at which task containers reach the fault proxy on this host")
    parser.add_argument("--spend-limit", type=float, default=None,
                        help="experiment real-spend envelope in USD, enforced before every dispatch (settled + held + allowance)")
    parser.add_argument("--experiment-id", default="",
                        help="stable identity (e.g. e016-pilot) whose spend envelope persists across relaunches")
    parser.add_argument("--keep-headroom", type=float, default=None,
                        help="never dispatch unless the key keeps this much unspent limit after held + new allowances")
    parser.add_argument("--stop-on-billing-mismatch", action="store_true",
                        help="stop when key usage differs from the attributable cost (another client on the key)")
    parser.add_argument("--stop-on-input-change", action="store_true", help="stop when a trial's inputs changed")
    parser.add_argument("--max-blocked-slots", type=int, default=None, help="stop at this many infrastructure-blocked slots")
    parser.add_argument("--max-consecutive-incomplete", type=int, default=None,
                        help="stop after this many consecutive trials without complete cost accounting")
    parser.add_argument("--purpose", default="reconnaissance",
                        choices=["reconnaissance", "evaluation", "confirmation", "diagnostic"],
                        help="declared before the run; only evaluation (+ confirmation) runs can be promoted")
    args = parser.parse_args()

    tasks = sorted(glob.glob(os.path.join(ROOT, "bench", "tasks", args.set, "*", "task.toml")))
    tasks = [os.path.dirname(t) for t in tasks]
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if os.path.basename(t) in wanted]
    if not tasks:
        print("no tasks found", file=sys.stderr)
        return 2
    stamp = time.strftime("%Y%m%d-%H%M%S")
    runs_dir = os.path.join(ROOT, "bench", "runs")
    base_stamp, n = stamp, 1
    while glob.glob(os.path.join(runs_dir, f"{stamp}-{args.set}*")):  # a relaunch within the same second
        n += 1
        stamp = f"{base_stamp}.{n}"
    arms = [("A", args.agent)] + ([("B", args.agent_b)] if args.agent_b else [])
    paired = len(arms) > 1
    scenario = load_scenario(args.fault_scenario) if args.fault_scenario else None
    fault_identity = None
    if scenario is not None:
        with open(args.fault_scenario, "rb") as handle:
            fault_identity = {"name": scenario["name"], "path": args.fault_scenario,
                              "sha256": hashlib.sha256(handle.read()).hexdigest(), "host": args.fault_host}
    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    git_dirty = bool(subprocess.run(["git", "status", "--porcelain", "src"], cwd=ROOT, capture_output=True, text=True).stdout)
    host = host_identity(os.path.expanduser("~/bittensor/ridges-cli"))
    state: Dict[str, Dict] = {}
    for label, source in arms:
        out_dir = os.path.join(ROOT, "bench", "runs", f"{stamp}-{args.set}" + (f"-{label}" if paired else ""))
        os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
        # The measured file never follows a later rebuild of dist/agent.py.
        source_agent = os.path.abspath(source)
        frozen_agent = os.path.join(out_dir, 'agent.py')
        with open(source_agent, 'rb') as src, open(frozen_agent, 'xb') as frozen:
            frozen.write(src.read())
        manifest = {
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "set": args.set, "repeats": args.repeats,
            "agent": frozen_agent, "agent_sha256": sha256_file(frozen_agent),
            "agent_source_path": source_agent,
            "git_commit": git_commit, "git_dirty": git_dirty,
            "model_override": {k: v for k, v in os.environ.items() if k.startswith("QUARRY_")},
            "expected_tasks": expected_tasks(ROOT, args.set),
            "selected_tasks": [os.path.basename(t) for t in tasks],
            "tasks": {os.path.basename(t): task_digest(t) for t in tasks},
            "config": {"ceiling": args.ceiling, "allowance": args.allowance, "timeout": args.timeout, "ridges": args.ridges,
                       "max_setup_replacements": MAX_SETUP_REPLACEMENTS},
            "purpose": args.purpose,
            "fault_scenario": fault_identity,
            "pairing": ({"arm": label, "arms": {lab: sha256_file(src) for lab, src in arms},
                         "order": "counterbalanced: A,B on even pairs, B,A on odd pairs", "run_stamp": stamp}
                        if paired else None),
            "host": host,
            "ridges_cli_commit": cli_version(os.path.expanduser("~/bittensor/ridges-cli")),
            "python": sys.version.split()[0],
        }
        with open(os.path.join(out_dir, "manifest.json"), "w") as handle:
            json.dump(manifest, handle, indent=1)
        state[label] = {"out_dir": out_dir, "agent": frozen_agent, "manifest": manifest, "rows": []}
    key = read_key()  # the one key used for usage reconciliation and, in fault runs, by the proxy (readiness P1)
    fetch = (lambda: fetch_key_usage(key)) if not args.no_key_usage else (lambda: None)
    ledger = SessionLedger(args.ledger, args.ceiling, fetch)
    stopped = ""
    pair_no = 0
    halt = {"reason": ""}
    stops = StopConditions(args.stop_on_billing_mismatch, args.stop_on_input_change, args.max_blocked_slots,
                           args.max_consecutive_incomplete)
    if args.spend_limit is not None and not args.experiment_id:
        print("--spend-limit needs --experiment-id so the envelope survives a relaunch", file=sys.stderr)
        return 2
    envelope = ExperimentEnvelope(
        args.spend_limit, args.keep_headroom, lambda: fetch_key_remaining(key),
        os.path.join(os.path.dirname(os.path.abspath(args.ledger)), "envelopes", f"{args.experiment_id}.json")
        if args.experiment_id else None)

    def dispatch_refusal() -> str:
        """Why the next dispatch (first attempt or replacement) must not happen; empty when it may."""
        if halt["reason"]:
            return "STOP: " + halt["reason"]
        if not ledger.fits(args.allowance):
            return f"spending ceiling ${args.ceiling:.2f} reached ({ledger.spent()}); remaining runs not scheduled"
        return envelope.refusal(args.allowance)

    def make_attempt(label, name, task, repeat, slot, pair_id, position):
        arm = state[label]

        def attempt_fn(attempt):
            trial_id = f"{slot}/a{attempt}"
            ledger.reserve(trial_id, args.allowance)
            envelope.reserve(trial_id, args.allowance)
            inputs_before = {name: task_digest(task), "bundle": sha256_file(arm["agent"])}
            before = fetch()
            raw = os.path.join(arm["out_dir"], "raw", f"{name}-r{repeat}-a{attempt}.log")
            if scenario is None:
                row = run_one(shlex.split(args.ridges), task, arm["agent"], args.timeout, raw)
            else:
                proxy_log = raw[:-4] + "-proxy.jsonl"
                with FaultProxy(scenario, port=0, host="0.0.0.0", key=key, log_path=proxy_log) as proxy:
                    row = run_one(shlex.split(args.ridges), task, arm["agent"], args.timeout, raw,
                                  ["--provider", "custom"],
                                  {"RIDGES_CUSTOM_SANDBOX_PROXY_URL": f"http://{args.fault_host}:{proxy.port}"})
                row.update(proxy_summary(proxy_log), fault_scenario=scenario["name"])
            after = settled_usage(fetch) if before is not None else None
            delta = round(after - before, 6) if (before is not None and after is not None) else None
            row.update(reconcile(row, delta) if scenario is None else reconcile_proxy(delta, row))
            changed = inputs_unchanged(inputs_before, {name: task_digest(task), "bundle": sha256_file(arm["agent"])})
            row.update({"repeat": repeat, "slot": slot, "attempt": attempt, "trial_id": trial_id,
                        "purpose": args.purpose, "bundle_sha256": arm["manifest"]["agent_sha256"][:16],
                        "task_digest": arm["manifest"]["tasks"][name], "inputs_changed": ",".join(changed)})
            if paired:
                row.update(arm=label, pair_id=pair_id, arm_position=position)
            if changed:
                row["validity"], row["outcome"] = "unresolved", "unknown"  # not comparable: inputs moved
            real = row.get("reconciled_cost")
            ledger.record(trial_id, args.allowance, real,
                          row.get("proxy_real_cost") if scenario is not None else row.get("cost_accounted"))
            envelope.settle(trial_id, real)
            halt_reason = stops.after_trial(row)
            if halt_reason and not halt["reason"]:
                halt["reason"] = halt_reason
            print(f"[{repeat}.{attempt}]{f' {label}' if paired else ''} {row['task']}: {row['outcome']} ({row['validity']}) "
                  f"reward={row['reward']} cost={format_cost(row)} wall={row['wall_sec']}s {row['error']}"
                  + (f" INPUTS CHANGED: {changed}" if changed else ""), flush=True)
            return row

        return attempt_fn

    labels = [label for label, _ in arms]
    for repeat in range(1, args.repeats + 1):
        for task in tasks:
            name = os.path.basename(task)
            order = labels if pair_no % 2 == 0 else list(reversed(labels))
            pair_id = f"{stamp}/{name}/r{repeat}"
            pair_no += 1
            for position, label in enumerate(order):
                refusal = dispatch_refusal()
                if refusal:
                    stopped = refusal
                    break
                arm = state[label]
                slot = f"{os.path.basename(arm['out_dir'])}/{name}/r{repeat}"
                attempt_fn = make_attempt(label, name, task, repeat, slot, pair_id, position)
                slot_rows, blocked, stop_reason = run_slot(attempt_fn, lambda: not dispatch_refusal())
                arm["rows"].extend(slot_rows)
                save_results(arm["out_dir"], arm["rows"])
                if blocked:
                    print(f"slot {slot}: infrastructure-blocked after {MAX_SETUP_REPLACEMENTS} setup replacements")
                    halt_reason = stops.after_blocked_slot()
                    if halt_reason and not halt["reason"]:
                        halt["reason"] = halt_reason
                if halt["reason"]:
                    stopped = "STOP: " + halt["reason"]
                elif stop_reason:
                    stopped = dispatch_refusal() or stop_reason
                if stopped:
                    break
            if stopped:
                break
        if stopped:
            break
    exit_code = 0
    for label in labels:
        if paired:
            print(f"\n==== arm {label}: {state[label]['manifest']['agent_sha256'][:16]}")
        exit_code = max(exit_code, report_arm(args, state[label]["rows"], state[label]["out_dir"], ledger, stopped))
    return exit_code


def report_arm(args, rows: List[Dict], out_dir: str, ledger: SessionLedger, stopped: str) -> int:
    if stopped:
        print(stopped)
    if not rows:
        print("no runs executed", file=sys.stderr)
        return 1
    save_results(out_dir, rows)

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
