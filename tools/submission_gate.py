"""Submission gate G7 (B-RUN-05): may `submissions/vNNN/agent.py` be uploaded?

Checks the target declared in docs/plans/wave3-heldout-tasks.md §6 against a held-out evaluation run, on the exact
file that will be uploaded:

  python tools/submission_gate.py submissions/v001 bench/runs/<timestamp>-heldout

1. The file is the bundle the held-out run measured (SHA-256 equals the run's agent hash and every trial's bundle).
2. The run is a complete held-out evaluation: every expected task has >= 3 valid trials, nothing unresolved.
3. Held-out solve rate >= 50% of the valid trials.
4. 0 agent mechanical failures.
5. Mean reconciled cost <= $0.03 per trial, with every trial's cost reconciled.
6. Pre-screen lint and originality (against the fetched public agents) pass on this file.
G0-G5 run separately (`tools/gate.py`); `--with-gates` runs them first.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import math
import os
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.bench_cost import trusted_cost  # noqa: E402
from tools.bench_summary import load_run, solved, summarize  # noqa: E402
from tools.originality_check import check as originality  # noqa: E402
from tools.prescreen_lint import lint  # noqa: E402

# Declared 2026-09-29 before any held-out result existed (wave3 plan §6). Change only by declaring a new target there.
MIN_SOLVE_RATE = 0.50
MAX_MECHANICAL = 0
MAX_COST_PER_TRIAL = 0.03
MIN_TRIALS = 3


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def evaluate(agent_path: str, run_dir: str, refs_root: str) -> Tuple[List[Tuple[str, bool, str]], Dict]:
    """Every gate condition as (name, passed, detail), plus the numbers for the manifest."""
    results: List[Tuple[str, bool, str]] = []
    run = load_run(run_dir)
    manifest = run["manifest"]
    digest = sha256_file(agent_path)

    bundles = {row.get("bundle_sha256") for row in run["rows"]}
    same = manifest.get("agent_sha256") == digest and bundles == {digest[:16]}
    results.append(("bundle is the one measured", same,
                    f"file {digest[:16]}, run {str(manifest.get('agent_sha256'))[:16]}, trials {sorted(map(str, bundles))}"))
    results.append(("production model routing", not manifest.get("model_override"),
                    "default routing" if not manifest.get("model_override") else "local model overrides were used"))

    purposes = {row.get("purpose") for row in run["rows"]}
    summary = summarize([run], {"evaluation"})
    unresolved = sum(info["unresolved"] for info in summary["per_task"].values())
    complete = (manifest.get("set") == "heldout" and manifest.get("purpose") == "evaluation"
                and purposes == {"evaluation"} and summary["complete"]
                and summary["min_valid_trials"] >= MIN_TRIALS and unresolved == 0)
    results.append(("complete held-out evaluation", complete,
                    f"set {manifest.get('set')}, purposes {sorted(map(str, purposes))}, "
                    f"min valid trials {summary['min_valid_trials']}, unresolved {unresolved}"))

    counted = [row for row in run["rows"] if row.get("validity") == "valid" and row.get("purpose") == "evaluation"]
    wins = sum(1 for row in counted if solved(row))
    needed = math.ceil(MIN_SOLVE_RATE * len(counted)) if counted else 1
    results.append(("solve rate", bool(counted) and wins >= needed, f"{wins}/{len(counted)} solved, need >= {needed}"))

    mechanical = sum(info["mechanical"] for info in summary["per_task"].values())
    results.append(("mechanical failures", mechanical <= MAX_MECHANICAL, f"{mechanical}"))

    costs = [trusted_cost(row) for row in counted if trusted_cost(row) is not None]
    mean_cost: Optional[float] = sum(costs) / len(costs) if costs else None
    cost_ok = mean_cost is not None and len(costs) == len(counted) and mean_cost <= MAX_COST_PER_TRIAL
    results.append(("cost per trial", cost_ok,
                    f"mean ${mean_cost:.4f} over {len(costs)}/{len(counted)} reconciled" if mean_cost is not None
                    else "no reconciled cost"))

    with open(agent_path, encoding="utf-8") as handle:
        errors, _, findings = lint(handle.read())
    results.append(("pre-screen lint", errors == 0, "clean" if errors == 0 else "; ".join(findings[:3])))

    has_refs = bool(glob.glob(os.path.join(refs_root, "**", "agent.py"), recursive=True))
    code, notes = originality(agent_path, refs_root, 15.0, 30.0) if has_refs else (1, ["no references fetched"])
    worst = " ".join(notes[1].split()) if code == 0 and len(notes) > 1 else "; ".join(notes[:3])
    results.append(("originality", code == 0, f"highest overlap: {worst}" if code == 0 else worst))

    walls = sorted(float(row["wall_sec"]) for row in counted if row.get("wall_sec"))
    numbers = {"heldout_solve": round(wins / len(counted), 4) if counted else None, "heldout_trials": len(counted),
               "heldout_solved": wins, "cost_usd": round(mean_cost, 6) if mean_cost is not None else None,
               "p50_sec": walls[len(walls) // 2] if walls else None, "mechanical": mechanical,
               "heldout_run": os.path.basename(os.path.normpath(run_dir)), "sha256": digest}
    return results, numbers


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("submission", help="submissions/vNNN (holds agent.py)")
    parser.add_argument("heldout_run", help="bench/runs/<timestamp>-heldout")
    parser.add_argument("--refs", default=os.path.join(ROOT, "references", "miners"))
    parser.add_argument("--with-gates", action="store_true", help="run tools/gate.py (G0-G5) first")
    args = parser.parse_args(argv)
    if args.with_gates:
        with tempfile.TemporaryDirectory(prefix="quarry-gates-") as temp:
            tested = os.path.join(temp, "agent.py")
            if subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gate.py"), "--bundle", tested], cwd=ROOT).returncode:
                print("FAIL  G0-G5")
                return 1
            if sha256_file(tested) != sha256_file(os.path.join(args.submission, "agent.py")):
                print("FAIL  G0-G5 tested a different bundle from the submission")
                return 1
    results, numbers = evaluate(os.path.join(args.submission, "agent.py"), args.heldout_run, args.refs)
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    ok = all(passed for _, passed, _ in results)
    print(f"\nG7 submission gate {'PASSED' if ok else 'FAILED'} for {args.submission} ({numbers['sha256'][:16]})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
