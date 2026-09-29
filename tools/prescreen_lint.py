#!/usr/bin/env python3
"""Block what pre-screening rejects before spending an upload (H-LINT-01).

Usage: tools/prescreen_lint.py [dist/agent.py]   Exit 1 on any FAIL.
"""

from __future__ import annotations

import re
import sys
from typing import List, Tuple

EXEMPT = re.compile(r"SANDBOX_PROXY_URL")
RULES: List[Tuple[str, str, str]] = [
    ("FAIL", "grading vocabulary", r"hidden[ _-]?tests?|verifier|grader|graded|being (tested|evaluated|scored)|benchmark"),
    ("FAIL", "evaluation environment", r"\bharbor\b|sandbox|test harness|evaluation (set|environment|run)"),
    ("FAIL", "sample or practice task/repo names",
     r"netbox|mptt|ridges-bench|swe-?bench|polyglot|contact[_-]group|vlangroup|cached[_-]value[_-]index|prefix[_-]hierarchy"
     r"|orders[_-]fanout|replacing[_-]final|sqlx[_-]pagination|prisma[_-]groupby"),
    ("FAIL", "long encoded blob", r"[A-Za-z0-9+/=]{200,}"),
    ("FAIL", "base64/zlib decode", r"b64decode|zlib\.decompress|codecs\.decode|marshal\.loads|pickle\.loads"),
    ("WARN", "hard-coded URL", r"https?://"),
    ("WARN", "dynamic code execution", r"\bexec\(|\beval\(|__import__\("),
    ("WARN", "scoring words", r"\bscor(e|es|ed|ing)\b"),
    ("WARN", "task identifiers", r"task[_ -]?id|instance[_ -]?id|problem[_ -]?name"),
]


def lint(text: str) -> Tuple[int, int, List[str]]:
    fails = warns = 0
    report: List[str] = []
    lines = text.splitlines()
    for level, label, pattern in RULES:
        regex = re.compile(pattern, re.IGNORECASE)
        hits = [(n, line) for n, line in enumerate(lines, 1) if regex.search(line) and not EXEMPT.search(line)]
        if hits:
            report.append(f"[{level}] {label}")
            report.extend(f"    {n}: {line.strip()[:150]}" for n, line in hits[:8])
            if level == "FAIL":
                fails += 1
            else:
                warns += 1
    return fails, warns, report


def main(argv: List[str]) -> int:
    path = argv[1] if len(argv) > 1 else "dist/agent.py"
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    fails, warns, report = lint(text)
    print("\n".join(report))
    print(f"\nprescreen_lint: {fails} fail(s), {warns} warning(s) in {path}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
