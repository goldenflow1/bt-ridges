#!/usr/bin/env python3
"""Aggregate, promote and compare live bench runs (B-RUN-03; plan M0.5 W5/W6).

  summarize RUN_DIR...                       per set/cohort, equal task weight, completeness, attempts
  promote --out BASELINE.json RUN_DIR...     immutable baseline manifest, only if every promotion condition holds
  compare BASELINE.json RUN_DIR... [--confirm-baseline DIR... --confirm-candidate DIR...]
                                             W6 keep/revert decision with the paired confirmation protocol

A run directory is what tools/run_bench.py writes: manifest.json + results.csv.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

PROMOTABLE_PURPOSES = {"evaluation", "confirmation"}
MIN_REPEATS = 3


class SummaryError(Exception):
    pass


# ---------------------------------------------------------------------------------- loading


def load_run(run_dir: str) -> Dict:
    manifest_path, results_path = os.path.join(run_dir, "manifest.json"), os.path.join(run_dir, "results.csv")
    if not (os.path.exists(manifest_path) and os.path.exists(results_path)):
        raise SummaryError(f"{run_dir}: missing manifest.json or results.csv")
    with open(manifest_path) as handle:
        manifest = json.load(handle)
    with open(results_path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    with open(results_path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return {"dir": os.path.abspath(run_dir), "manifest": manifest, "rows": rows, "results_sha256": digest}


def cohort_key(manifest: Dict) -> Tuple:
    """What must match inside one cohort: set, agent build, model routing, task versions, runtime."""
    host = manifest.get("host") or {}
    return (
        manifest.get("set"), manifest.get("agent_sha256"),
        json.dumps(manifest.get("model_override") or {}, sort_keys=True),
        json.dumps(manifest.get("tasks") or {}, sort_keys=True),
        host.get("ridges_cli_commit") or manifest.get("ridges_cli_commit"), host.get("harbor"),
    )


def runtime_key(manifest: Dict) -> Tuple:
    host = manifest.get("host") or {}
    return (host.get("ridges_cli_commit") or manifest.get("ridges_cli_commit"), host.get("harbor"))


def solved(row: Dict) -> bool:
    try:
        return float(row.get("reward") or 0) >= 1
    except ValueError:
        return False


def trials(runs: List[Dict]) -> List[Dict]:
    """All physical attempts, deduplicated by trial ID; conflicting duplicates are an error."""
    seen: Dict[str, Dict] = {}
    for run in runs:
        for row in run["rows"]:
            tid = row.get("trial_id") or ""
            if tid in seen:
                if seen[tid] != row:
                    raise SummaryError(f"conflicting records for trial {tid}")
                continue
            seen[tid] = dict(row, _purpose=row.get("purpose") or run["manifest"].get("purpose") or "reconnaissance")
    return list(seen.values())


# ---------------------------------------------------------------------------------- summarize


def summarize(runs: List[Dict], purposes: Optional[set] = None) -> Dict:
    if not runs:
        raise SummaryError("no runs")
    keys = {cohort_key(r["manifest"]) for r in runs}
    if len(keys) != 1:
        raise SummaryError(f"runs belong to {len(keys)} different cohorts (set/agent/model/task versions/runtime)")
    manifest = runs[0]["manifest"]
    expected = list(manifest.get("expected_tasks") or manifest.get("selected_tasks") or [])
    rows = [r for r in trials(runs) if purposes is None or r["_purpose"] in purposes]
    per_task: Dict[str, Dict] = {}
    for task in expected:
        task_rows = [r for r in rows if r.get("task") == task]
        counted = [r for r in task_rows if r.get("validity") == "valid"]
        slots = sorted({r.get("slot") for r in counted})
        per_task[task] = {
            "attempts": len(task_rows),
            "void_attempts": sum(1 for r in task_rows if r.get("validity") == "void-infrastructure"),
            "unresolved": sum(1 for r in task_rows if r.get("validity") not in ("valid", "void-infrastructure")),
            "valid_trials": len(slots),
            "solved": sum(1 for r in counted if solved(r)),
            "mechanical": sum(1 for r in counted if r.get("auto_label") == "mechanical"),
            "solve_fraction": (sum(1 for r in counted if solved(r)) / len(counted)) if counted else None,
            "solved_every_repeat": bool(counted) and all(solved(r) for r in counted),
            "mean_cost": _mean([float(r["reconciled_cost"]) for r in counted if r.get("reconciled_cost")]),
        }
    missing = [t for t, info in per_task.items() if info["valid_trials"] == 0]
    fractions = [info["solve_fraction"] for info in per_task.values() if info["solve_fraction"] is not None]
    costs = [info["mean_cost"] for info in per_task.values() if info["mean_cost"] is not None]
    return {
        "set": manifest.get("set"), "agent_sha256": manifest.get("agent_sha256"), "expected_tasks": expected,
        "complete": not missing, "missing_tasks": missing,
        "mean_solve": (sum(fractions) / len(fractions)) if fractions and not missing else None,
        "solved_every_repeat": sorted(t for t, info in per_task.items() if info["solved_every_repeat"]),
        "cost_per_task_mean": _mean(costs), "cost_coverage": f"{len(costs)}/{len(expected)}",
        "min_valid_trials": min((info["valid_trials"] for info in per_task.values()), default=0),
        "per_task": per_task,
    }


def _mean(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 6) if values else None


# ---------------------------------------------------------------------------------- promote


def promotion_problems(runs: List[Dict]) -> List[str]:
    problems = []
    purposes = {r["manifest"].get("purpose") for r in runs}
    if not purposes <= PROMOTABLE_PURPOSES:
        problems.append(f"only evaluation/confirmation runs can be promoted; got {sorted(p or 'none' for p in purposes)}")
    try:
        summary = summarize(runs, PROMOTABLE_PURPOSES)
    except SummaryError as exc:
        return problems + [str(exc)]
    for task, info in summary["per_task"].items():
        if info["valid_trials"] < MIN_REPEATS:
            problems.append(f"{task}: {info['valid_trials']} valid trials < {MIN_REPEATS} (reconnaissance, not a baseline)")
        if info["unresolved"]:
            problems.append(f"{task}: {info['unresolved']} unresolved trial(s)")
        if info["mechanical"]:
            problems.append(f"{task}: {info['mechanical']} agent mechanical failure(s)")
    for run in runs:
        for row in run["rows"]:
            if row.get("inputs_changed"):
                problems.append(f"{row.get('trial_id')}: inputs changed during the trial")
            if not row.get("images") or row.get("images") == "{}":
                problems.append(f"{row.get('trial_id')}: runtime images not recorded")
    return problems


def promote(runs: List[Dict], out: str) -> Dict:
    if os.path.exists(out):
        raise SummaryError(f"{out} exists; a kept baseline is never overwritten")
    problems = promotion_problems(runs)
    if problems:
        raise SummaryError("not promotable:\n  " + "\n  ".join(problems))
    summary = summarize(runs, PROMOTABLE_PURPOSES)
    record = {
        "baseline_version": 1, "summary": summary,
        "cohort": {"set": summary["set"], "agent_sha256": summary["agent_sha256"],
                   "tasks": runs[0]["manifest"].get("tasks"), "runtime": list(runtime_key(runs[0]["manifest"])),
                   "model_override": runs[0]["manifest"].get("model_override") or {}},
        "runs": [{"dir": r["dir"], "results_sha256": r["results_sha256"],
                  "trial_ids": sorted(row["trial_id"] for row in r["rows"])} for r in runs],
    }
    with open(out, "x") as handle:  # "x": never overwrite
        json.dump(record, handle, indent=1)
    os.chmod(out, 0o444)
    return record


# ---------------------------------------------------------------------------------- compare (W6)


def compatibility_problems(baseline: Dict, candidate_runs: List[Dict]) -> List[str]:
    problems = []
    cohort = baseline["cohort"]
    for run in candidate_runs:
        manifest = run["manifest"]
        if manifest.get("set") != cohort["set"]:
            problems.append(f"{run['dir']}: set {manifest.get('set')} != {cohort['set']}")
        if (manifest.get("tasks") or {}) != cohort["tasks"]:
            problems.append(f"{run['dir']}: task membership or versions differ from the baseline (re-run the baseline)")
        if list(runtime_key(manifest)) != list(cohort["runtime"]):
            problems.append(f"{run['dir']}: runtime differs from the baseline")
    return problems


def _fraction(info: Dict) -> Tuple[int, int]:
    return info["solved"], info["valid_trials"]


def compare(baseline: Dict, candidate_runs: List[Dict], confirm_base: Optional[List[Dict]] = None,
            confirm_cand: Optional[List[Dict]] = None, cost_branch: bool = False) -> Dict:
    """W6 decision: keep | revert | pending. Material regression: a baseline 3/3 task at 0/3 or 1/3. Any other
    drop needs one paired confirmation block (both versions, affected tasks); a drop persists when the candidate
    solves fewer confirmation trials than the baseline. Confirmation never replaces initial results."""
    problems = compatibility_problems(baseline, candidate_runs)
    if problems:
        return {"decision": "incompatible", "problems": problems}
    base = baseline["summary"]["per_task"]
    cand = summarize(candidate_runs, PROMOTABLE_PURPOSES)["per_task"]
    confirm_b = summarize(confirm_base, {"confirmation"})["per_task"] if confirm_base else {}
    confirm_c = summarize(confirm_cand, {"confirmation"})["per_task"] if confirm_cand else {}
    material, needs_confirmation, confirmed, not_reproduced, gains = [], [], [], [], []
    for task, b in base.items():
        c = cand.get(task)
        if c is None or c["valid_trials"] < MIN_REPEATS:
            return {"decision": "pending", "reason": f"{task}: candidate has fewer than {MIN_REPEATS} valid trials"}
        if c["mechanical"]:
            material.append(f"{task}: new agent mechanical failure")
        (bs, bn), (cs, cn) = _fraction(b), _fraction(c)
        if bs == bn and cs <= 1:
            material.append(f"{task}: {bs}/{bn} → {cs}/{cn}")
        elif cs * bn < bs * cn:  # lower observed fraction
            if task in confirm_b and task in confirm_c:
                (xb, _), (xc, _) = _fraction(confirm_b[task]), _fraction(confirm_c[task])
                (confirmed if xc < xb else not_reproduced).append(
                    f"{task}: initial {bs}/{bn} → {cs}/{cn}; confirmation baseline {xb}/3 vs candidate {xc}/3")
            else:
                needs_confirmation.append(task)
        if cs == cn and bs < bn:
            gains.append(task)
    base_cost = baseline["summary"].get("cost_per_task_mean")
    cand_cost = summarize(candidate_runs, PROMOTABLE_PURPOSES).get("cost_per_task_mean")
    result = {"material_regressions": material, "confirmed_regressions": confirmed, "not_reproduced": not_reproduced,
              "needs_confirmation": needs_confirmation, "gains": gains, "baseline_cost": base_cost,
              "candidate_cost": cand_cost}
    if material or confirmed:
        result["decision"] = "revert"
    elif needs_confirmation:
        result["decision"] = "pending"
        result["reason"] = f"run one paired confirmation block (3 trials, both versions) for {needs_confirmation}"
    elif gains:
        result["decision"] = "keep"
    elif cost_branch and base_cost and cand_cost is not None and cand_cost <= 0.85 * base_cost and any(
            info["solved"] for info in cand.values()):
        result["decision"] = "keep"
        result["reason"] = f"cost {cand_cost} ≤ 85% of {base_cost} with no confirmed regression"
    else:
        result["decision"] = "revert"
        result["reason"] = "no task newly solved 3/3 and no qualifying cost reduction"
    return result


# ---------------------------------------------------------------------------------- CLI


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("runs", nargs="+")
    p_pro = sub.add_parser("promote")
    p_pro.add_argument("--out", required=True)
    p_pro.add_argument("runs", nargs="+")
    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("baseline")
    p_cmp.add_argument("runs", nargs="+")
    p_cmp.add_argument("--confirm-baseline", nargs="*", default=[])
    p_cmp.add_argument("--confirm-candidate", nargs="*", default=[])
    p_cmp.add_argument("--cost-branch", action="store_true", help="evaluate the cost-saving branch of W6")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "summarize":
            print(json.dumps(summarize([load_run(d) for d in args.runs]), indent=1))
        elif args.cmd == "promote":
            record = promote([load_run(d) for d in args.runs], args.out)
            print(f"promoted baseline written to {args.out} (read-only); mean solve {record['summary']['mean_solve']}")
        else:
            with open(args.baseline) as handle:
                baseline = json.load(handle)
            result = compare(baseline, [load_run(d) for d in args.runs],
                             [load_run(d) for d in args.confirm_baseline] or None,
                             [load_run(d) for d in args.confirm_candidate] or None, args.cost_branch)
            print(json.dumps(result, indent=1))
            return 0 if result["decision"] in ("keep", "revert", "pending") else 1
    except SummaryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
