#!/usr/bin/env python3
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path("/app")
LOGS = Path("/logs/verifier")
ALLOWED = Path("src/reports.ts")
ORIGINAL = Path("/opt/task/original-reports.ts")
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/report_hidden.test.ts")
HIDDEN_TARGET = APP / "test/ridges_report_hidden.test.ts"
PIN = "ts-ch-client-limit-by"
AGENT_UID = 1000
TSSPAN = "/opt/task/tsspan.cjs"


class Report:
    def __init__(self):
        self.cases = []

    def check(self, name, function):
        try:
            detail = function()
            self.cases.append((name, True, detail))
            return detail
        except Exception as error:
            self.cases.append((name, False, f"{type(error).__name__}: {error}"))
            return None

    def write(self):
        suite = ET.Element(
            "testsuite",
            name="ts-ch-client-limit-by",
            tests=str(len(self.cases)),
            failures=str(sum(not passed for _, passed, _ in self.cases)),
            errors="0",
            skipped="0",
        )
        for name, passed, detail in self.cases:
            case = ET.SubElement(suite, "testcase", name=name)
            if not passed:
                failure = ET.SubElement(case, "failure", message=str(detail)[:1000])
                failure.text = str(detail)[:5000]
            output = ET.SubElement(case, "system-out")
            output.text = (
                json.dumps(detail, sort_keys=True)
                if isinstance(detail, (dict, list))
                else str(detail)
            )
        ET.ElementTree(suite).write(
            LOGS / "junit.xml", encoding="utf-8", xml_declaration=True
        )
        passed = all(result for _, result, _ in self.cases)
        (LOGS / "reward.txt").write_text("1\n" if passed else "0\n")
        return 0 if passed else 1


def run(command, timeout=420, check=True):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=APP,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    digest = hashlib.sha256("\0".join(command).encode()).hexdigest()[:12]
    (LOGS / f"command-{digest}.log").write_text(result.stdout)
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}; "
            f"tail={result.stdout[-3500:]}"
        )
    return result


def file_record(path):
    mode = stat.S_IMODE(path.lstat().st_mode)
    if path.is_symlink():
        return {"kind": "symlink", "mode": mode, "target": path.readlink().as_posix()}
    if path.is_file():
        return {
            "kind": "file",
            "mode": mode,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    if path.is_dir():
        return {"kind": "directory", "mode": mode}
    return {"kind": "other", "mode": mode}


def source_identity():
    revision = Path("/opt/task/SOURCE_REVISION").read_text().strip()
    if revision != PIN:
        raise AssertionError("protected source revision changed")
    expected = json.loads(MANIFEST.read_text())
    actual = {}
    for path in sorted(APP.rglob("*")):
        relative = path.relative_to(APP)
        if relative == ALLOWED:
            continue
        actual[str(relative)] = file_record(path)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))[:10]
        added = sorted(set(actual) - set(expected))[:10]
        changed = sorted(
            key for key in set(actual) & set(expected) if actual[key] != expected[key]
        )[:10]
        raise AssertionError(
            f"source drift: missing={missing}, added={added}, changed={changed}"
        )
    target = APP / ALLOWED
    if target.is_symlink() or not target.is_file():
        raise AssertionError("editable source is not a regular file")
    if target.stat().st_uid != AGENT_UID:
        raise AssertionError("editable source owner changed")
    metadata = json.loads(ALLOWED_METADATA.read_text())
    if stat.S_IMODE(target.lstat().st_mode) != metadata["mode"]:
        raise AssertionError("editable source mode changed")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def bounded_function():
    info = json.loads(run(["node", TSSPAN, str(ORIGINAL), str(APP / ALLOWED), 'topItems']).stdout)
    assert info["found"] == info["originalFound"] == 1
    assert info["prefixEqual"] and info["suffixEqual"] and info["headerEqual"], "edits outside function"
    assert not info["loops"], "keep row ordering and aggregation in SQL"
    prohibited = {"map", "flatMap", "filter", "sort", "reduce", "reverse", "splice", "slice", "exec", "spawn", "fetch", "writeFile", "readFile", "command", "insert", "update", "delete"}
    assert not (set(info["properties"]) & prohibited), "forbidden row transformation or side effect"
    assert not (set(info["names"]) & {"eval", "Function", "require", "process", "fetch"}), "forbidden side-effect API"
    assert info["properties"].get("query", 0) == 1, "exactly one query required"
    return "ok"

COMMAND = ['node', '--import', 'tsx', '--test', '--test-reporter=tap', 'test/reports.test.ts']
REQUIRED = ['hidden: each category gets its own quota', 'hidden: cutoff ties choose smaller IDs', 'hidden: filter eligibility before ranking']

def check_run(command, required):
    result = run(command, check=False, timeout=600)
    assert result.returncode == 0, result.stdout[-5000:]
    for name in required:
        assert name in result.stdout, "missing test: " + name
    assert "--- SKIP:" not in result.stdout and "# SKIP" not in result.stdout
    return "ok"

def hidden_tests():
    assert not HIDDEN_TARGET.exists()
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    try:
        command = COMMAND.copy()
        if 'ts' == "go":
            command[1:1] = []
            command.insert(2, "-run=^TestHidden")
        else:
            command[-1] = str(HIDDEN_TARGET.relative_to(APP))
        return check_run(command, REQUIRED)
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)

def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.check("bounded_function", bounded_function)
    report.check("source_tree_conservation_before_tests", source_identity)
    report.check("compilation", lambda: run(['npx', '--offline', 'tsc', '--noEmit']).returncode)
    report.check("regression_tests", lambda: check_run(COMMAND, []))
    report.check("hidden_behavior", hidden_tests)
    report.check("source_tree_conservation_after_tests", source_identity)
    return report.write()

if __name__ == "__main__":
    sys.exit(main())
