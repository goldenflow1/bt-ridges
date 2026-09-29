#!/usr/bin/env python3
"""Run the automatic gates G0–G5 (docs/process/engineering-loop.md §5); stop at the first failure.

Usage: uv run python tools/gate.py [--skip-py39]
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERIFY_TAG = re.compile(r"\|\s*(H-[A-Z]+-\d+)\s*\|.*\|\s*([a-z0-9, ]+)\s*\|\s*$")
REQUIREMENT_ROW = re.compile(r"^\|\s*H-[A-Z]+-\d+\s*\|")
KNOWN_METHODS = {"unit", "scenario", "e2e", "bench", "manual"}


def run(label: str, cmd: list) -> bool:
    started = time.time()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    ok = result.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}  {label}  ({time.time() - started:.1f}s)")
    if not ok:
        print((result.stdout + result.stderr)[-4000:])
    return ok


def traceability(root: str = ROOT) -> bool:
    """G5: every requirement verified by unit/scenario/e2e has at least one test naming it."""
    started = time.time()
    required = {}
    malformed = []
    for spec in glob.glob(os.path.join(root, "docs", "specs", "*.md")):
        with open(spec, encoding="utf-8") as handle:
            for line in handle:
                if not REQUIREMENT_ROW.match(line):
                    continue
                match = VERIFY_TAG.search(line.rstrip("\n"))
                methods = {m.strip() for m in match.group(2).split(",")} if match else set()
                if not match or not methods or methods - KNOWN_METHODS:
                    malformed.append(line.split("|")[1].strip())
                    continue
                if methods & {"unit", "scenario", "e2e"}:
                    required[match.group(1)] = os.path.basename(spec)
    if malformed:
        print(f"FAIL  G5 traceability: unparseable requirement rows or unknown verification methods: {malformed}")
        return False
    tests_text = ""
    for path in glob.glob(os.path.join(root, "tests", "**", "*.py"), recursive=True):
        with open(path, encoding="utf-8") as handle:
            tests_text += handle.read()
    missing = []
    for req in sorted(required):
        token = req.replace("-", "_")
        number = int(req.rsplit("-", 1)[1])
        prefix = token.rsplit("_", 1)[0]
        ranges = re.findall(prefix + r"_(\d+)_to_(\d+)", tests_text)
        covered = token in tests_text or any(int(a) <= number <= int(b) for a, b in ranges)
        if not covered:
            missing.append(req)
    ok = not missing
    print(f"{'PASS' if ok else 'FAIL'}  G5 traceability: {len(required) - len(missing)}/{len(required)} requirements have tests  ({time.time() - started:.1f}s)")
    if missing:
        print("    missing: " + ", ".join(missing))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-py39", action="store_true", help="skip importing the bundle under Python 3.9")
    args = parser.parse_args()
    py = sys.executable
    gates = [
        ("G0 ruff", [py, "-m", "ruff", "check", "src", "tools", "tests"]),
        ("G1 unit + scenario tests", [py, "-m", "pytest", "-q", "tests/unit", "tests/scenario"]),
        ("G2 bundle builds", [py, "tools/build.py"]),
        ("G3 offline e2e on the bundle", [py, "-m", "pytest", "-q", "tests/e2e"]),
        ("G4 pre-screen lint", [py, "tools/prescreen_lint.py", "dist/agent.py"]),
    ]
    for label, cmd in gates:
        if not run(label, cmd):
            return 1
        if label.startswith("G2") and not args.skip_py39:
            if not run("G2b bundle imports on Python 3.9", ["uv", "run", "--no-project", "--python", "3.9", "python", "-c",
                                                         "import importlib.util as u; s=u.spec_from_file_location('a','dist/agent.py'); "
                                                         "m=u.module_from_spec(s); s.loader.exec_module(m); assert callable(m.agent_main)"]):
                return 1
    refs = os.path.join(ROOT, "references", "miners")
    if glob.glob(os.path.join(refs, "**", "agent.py"), recursive=True):
        if not run("G4b originality vs public agents", [py, "tools/originality_check.py", "dist/agent.py"]):
            return 1
    else:
        print("SKIP  G4b originality: no references fetched (required before upload: tools/fetch_references.py)")
    if not traceability():
        return 1
    print("\nall automatic gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
