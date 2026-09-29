#!/usr/bin/env python3
"""Measure how much of our bundle overlaps with other miners' public agents (upload gate; H-LINT-02).

Two measures per reference, both as a share of the *candidate's* content:
- lines:    distinctive normalised lines (stripped, no blanks/comments, >= 30 chars) also present in the reference;
- shingles: 12-token sequences (comments and whitespace ignored) also present in the reference; this catches
            copies that were reformatted, re-wrapped or had comments changed.
Fail if any reference is byte-identical or either share >= --fail (default 30%); warn at >= --warn (15%).

Usage: python tools/originality_check.py [dist/agent.py] [--refs references/miners]
Exit: 0 pass, 1 fail, 2 nothing to compare against.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import os
import sys
import tokenize
from typing import Dict, List, Set, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MIN_LINE = 30
SHINGLE = 12


def distinctive_lines(text: str) -> Set[str]:
    out = set()
    for line in text.replace("\r", "").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and len(line) >= MIN_LINE:
            out.add(line)
    return out


def code_tokens(text: str) -> List[str]:
    """Python tokens without comments, whitespace or docstring-only differences in layout."""
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING,
            tokenize.ENDMARKER}
    try:
        return [tok.string for tok in tokenize.generate_tokens(io.StringIO(text).readline) if tok.type not in skip]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text.split()


def shingles(tokens: List[str], size: int = SHINGLE) -> Set[int]:
    return {hash(tuple(tokens[i:i + size])) for i in range(max(0, len(tokens) - size + 1))}


def compare(candidate: str, reference: str) -> Dict[str, float]:
    cand_lines, ref_lines = distinctive_lines(candidate), distinctive_lines(reference)
    cand_sh, ref_sh = shingles(code_tokens(candidate)), shingles(code_tokens(reference))
    return {
        "identical": hashlib.sha256(candidate.encode()).digest() == hashlib.sha256(reference.encode()).digest(),
        "lines": 100.0 * len(cand_lines & ref_lines) / len(cand_lines) if cand_lines else 0.0,
        "shingles": 100.0 * len(cand_sh & ref_sh) / len(cand_sh) if cand_sh else 0.0,
    }


def check(candidate_path: str, refs_root: str, warn: float, fail: float) -> Tuple[int, List[str]]:
    with open(candidate_path, encoding="utf-8") as handle:
        candidate = handle.read()
    refs = sorted(glob.glob(os.path.join(refs_root, "**", "agent.py"), recursive=True))
    if not refs:
        return 2, [f"no reference agents under {refs_root}; run tools/fetch_references.py first"]
    rows: List[Tuple[float, str]] = []
    status = 0
    for ref in refs:
        with open(ref, encoding="utf-8", errors="replace") as handle:
            result = compare(candidate, handle.read())
        worst = max(result["lines"], result["shingles"])
        flag = ""
        if result["identical"] or worst >= fail:
            flag, status = "FAIL", 1
        elif worst >= warn:
            flag = "warn"
        label = "identical" if result["identical"] else f"{result['lines']:6.1f}% {result['shingles']:8.1f}%"
        rows.append((100.0 if result["identical"] else worst, f"{os.path.relpath(ref, refs_root):<60} {label}  {flag}"))
    rows.sort(reverse=True)
    report = [f"{'reference':<60} {'lines':>7} {'shingles':>9}"] + [line for _, line in rows]
    report.append(f"\n{len(refs)} reference(s); warn at {warn:.0f}%, fail at {fail:.0f}% (lines or shingles)")
    return status, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("candidate", nargs="?", default=os.path.join(ROOT, "dist", "agent.py"))
    parser.add_argument("--refs", default=os.path.join(ROOT, "references", "miners"))
    parser.add_argument("--warn", type=float, default=15.0)
    parser.add_argument("--fail", type=float, default=30.0)
    args = parser.parse_args(argv)
    status, report = check(args.candidate, args.refs, args.warn, args.fail)
    print("\n".join(report))
    print({0: "originality_check: PASS", 1: "originality_check: FAIL", 2: "originality_check: NOT RUN"}[status])
    return status


if __name__ == "__main__":
    sys.exit(main())
