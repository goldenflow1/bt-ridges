"""Per-test outcomes from a task checker's log, for the four runners the current tasks use (B-VALID-08).

Each result is "pass", "fail" (a behavioural assertion ran and failed) or "error" (collection, import, setup,
compile, panic or any non-assertion exception). A decoy only counts when its declared test is a "fail".
Deliberately small: one adapter per runner in use, not a general test-report framework.
"""

from __future__ import annotations

import html
import re
from typing import Dict

PYTEST_SECTION = re.compile(r"^_{3,} (\S+?) _{3,}$", re.M)
PYTEST_SUMMARY = re.compile(r"^(FAILED|ERROR|PASSED) (\S+?)(?: - .*)?$", re.M)
DJANGO_LINE = re.compile(r"^(test_\w+) \([\w.]+\) \.\.\. (ok|FAIL|ERROR)\s*$", re.M)
GO_RESULT = re.compile(r"^\s*--- (PASS|FAIL): (\S+)", re.M)
TAP_RESULT = re.compile(r"^(not ok|ok) \d+ - (.+?)\s*$", re.M)


def _set(results: Dict[str, str], name: str, status: str) -> None:
    # "error" beats "fail" beats "pass": the least trustworthy outcome wins if a name repeats
    rank = {"pass": 0, "fail": 1, "error": 2}
    if rank[status] >= rank.get(results.get(name, "pass"), 0) or name not in results:
        results[name] = status


def pytest_results(text: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    sections = {}
    matches = list(PYTEST_SECTION.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Stop before the summary (or another runner header). A sibling's
        # summary can mention AssertionError after this test's runtime error.
        body = re.split(r"^={3,}.*$", text[match.end():end], maxsplit=1, flags=re.M)[0]
        sections[match.group(1).split("::")[-1]] = body
    for kind, node in PYTEST_SUMMARY.findall(text):
        name = node.split("::")[-1]
        if kind == "PASSED":
            _set(results, name, "pass")
        elif kind == "ERROR" or "::" not in node:
            _set(results, name, "error")
        else:
            body = sections.get(name, "")
            exceptions = re.findall(r"^E\s+([\w.]*(?:Error|Exception))\b", body, re.M)
            asserted = (exceptions[-1].rsplit(".", 1)[-1] == "AssertionError" if exceptions
                        else bool(re.search(r"^E\s+assert ", body, re.M)))
            _set(results, name, "fail" if asserted else "error")
    if re.search(r"collected \d+ items? / \d+ errors?|ERROR collecting", text):
        results["<collection>"] = "error"
    return results


def django_results(text: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for name, outcome in DJANGO_LINE.findall(text):
        _set(results, name, {"ok": "pass", "FAIL": "fail", "ERROR": "error"}[outcome])
    return results


def go_results(text: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for outcome, name in GO_RESULT.findall(text):
        _set(results, name, "pass" if outcome == "PASS" else "fail")
    if re.search(r"^panic: ", text, re.M):
        # a panic aborts the package: the test running at the time is an error, not an assertion
        running = re.findall(r"^=== RUN\s+(\S+)", text[: re.search(r"^panic: ", text, re.M).start()], re.M)
        if running:
            _set(results, running[-1], "error")
    if "[build failed]" in text or re.search(r"^# \S+\n.*\.go:\d+:\d+: ", text, re.M):
        results["<build>"] = "error"
    return results


def tap_results(text: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    matches = list(TAP_RESULT.finditer(text))
    for i, match in enumerate(matches):
        name = match.group(2)
        if match.group(1) == "ok":
            _set(results, name, "pass")
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.end():end]
        asserted = "failureType: 'testCodeFailure'" in block and "code: 'ERR_ASSERTION'" in block
        _set(results, name, "fail" if asserted else "error")
    return results


ADAPTERS = {"pytest": pytest_results, "django": django_results, "go": go_results, "tap": tap_results}


def runner_text(text: str) -> str:
    """The raw runner output. Checker logs also embed a JUnit XML summary whose copies of the output are
    truncated; parsing those would mistake a cut-off assertion for an error, so XML lines are dropped first."""
    kept = [line for line in (text or "").splitlines() if not line.lstrip().startswith(("<?xml", "<testsuite"))]
    return html.unescape("\n".join(kept))


def parse(text: str, runner: str) -> Dict[str, str]:
    return ADAPTERS[runner](runner_text(text))


def detect_runner(text: str) -> str:
    text = runner_text(text)
    if "TAP version" in text:
        return "tap"
    if GO_RESULT.search(text) or "=== RUN" in text:
        return "go"
    if DJANGO_LINE.search(text):
        return "django"
    return "pytest"
