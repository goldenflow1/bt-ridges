#!/usr/bin/env python3
import hashlib
import json
import os
import re
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
HIDDEN_SOURCE = Path("/tests/completion_rate_hidden.test.ts")
HIDDEN_TARGET = APP / "test/ridges_completion_rate_hidden.test.ts"
PIN = "courseboard-2.3.0-completion-rate"
AGENT_UID = 1000
DEV_URL = "postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_dev"
TEST_URL = "postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_test"
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
            name="ts-prisma-groupby",
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
    result = run(
        ["node", TSSPAN, str(ORIGINAL), str(APP / ALLOWED), "courseCompletionRates"],
        timeout=60,
    )
    info = json.loads(result.stdout)
    if info["found"] != 1 or info["originalFound"] != 1:
        raise AssertionError(f"expected one courseCompletionRates function, found {info['found']}")
    if not info["prefixEqual"]:
        raise AssertionError("source before target function changed")
    if not info["suffixEqual"]:
        raise AssertionError("source after target function changed")
    if not info["headerEqual"]:
        raise AssertionError("function doc comment or signature changed")
    if info["bodyLength"] > 6000:
        raise AssertionError("target function exceeds 6000 characters")
    if info["nodes"] > 400:
        raise AssertionError("target function exceeds 400 AST nodes")
    if info["loops"]:
        raise AssertionError("loops are forbidden in the target function")
    properties = info["properties"]
    if properties.get("$queryRaw", 0) != 1 or info["taggedTemplates"] != 1:
        raise AssertionError("the function must run exactly one $queryRaw tagged query")
    forbidden_properties = {
        "$queryRawUnsafe",
        "$executeRaw",
        "$executeRawUnsafe",
        "$transaction",
        "raw",
        "round",
        "floor",
        "ceil",
        "trunc",
        "toFixed",
        "toPrecision",
        "sort",
        "filter",
        "reduce",
    }
    used = sorted(set(properties) & forbidden_properties)
    if used:
        raise AssertionError(f"forbidden property access in function: {used}")
    names = sorted(set(info["names"]) & {"Math", "eval", "Function", "require", "process"})
    if names:
        raise AssertionError(f"forbidden names in function: {names}")
    for text in info["templateText"]:
        for marker in ("LAT10", "OCE20", "SOC31", "ECO12", "CS100"):
            if marker in text:
                raise AssertionError("fixture-specific literal in production function")
    candidate_bytes = (APP / ALLOWED).read_bytes()
    return {"candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest()}


def parse_node_test_run(result, expected_names):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    if result.returncode:
        raise AssertionError(
            f"test command failed ({result.returncode}); tail={plain[-4500:]}"
        )
    passed = re.findall(r"^ok \d+ - (.+?)\s*$", plain, re.MULTILINE)
    if re.search(r"^not ok \d+ - ", plain, re.MULTILINE):
        raise AssertionError("test run reported failures")
    if re.search(r"# (SKIP|TODO)", plain):
        raise AssertionError("test run reported skipped tests")
    if sorted(passed) != sorted(expected_names):
        raise AssertionError(f"unexpected test set: {passed}")
    return {
        "tests": len(passed),
        "stdout_sha256": hashlib.sha256(plain.encode()).hexdigest(),
    }


def node_test(path):
    return run(
        ["node", "--import", "tsx", "--test", "--test-reporter=tap", path],
        timeout=600,
        check=False,
    )


def focused_tests():
    required = [
        "completion rate per course",
        "course without enrollments has rate zero",
        "withdrawn enrollments are ignored",
        "archived courses are left out",
        "equal rates are ordered by course id",
        "instructor load counts active learners",
        "markCompleted completes an active enrollment once",
    ]
    return parse_node_test_run(node_test("test/reports.test.ts"), required)


def hidden_tests():
    if HIDDEN_TARGET.exists() or HIDDEN_TARGET.is_symlink():
        raise AssertionError("hidden test target already exists")
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    os.chmod(HIDDEN_TARGET, 0o400)
    try:
        result = node_test(str(HIDDEN_TARGET.relative_to(APP)))
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)
    required = [
        "hidden: fractional rates keep one decimal",
        "hidden: halves round away from zero",
        "hidden: ordering uses the precise rate",
        "hidden: withdrawn learners do not dilute fractional rates",
        "hidden: large cohorts and tiny fractions",
    ]
    return parse_node_test_run(result, required)


def role_identity():
    result = run(
        [
            "psql",
            DEV_URL,
            "-At",
            "-c",
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname='courseboard'",
        ],
        timeout=30,
    )
    if result.stdout.strip() != "f|f|f|f|f":
        raise AssertionError(f"unexpected application role: {result.stdout.strip()}")
    return result.stdout.strip()


def schema_identity():
    result = run(
        [
            "psql",
            TEST_URL,
            "-At",
            "-c",
            "SELECT n.nspname,c.relname,c.relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
            "AND n.nspname NOT LIKE 'pg_toast%' "
            "ORDER BY 1,2,3",
        ],
        timeout=60,
    )
    return hashlib.sha256(result.stdout.encode()).hexdigest()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.check(
        "transported_patch_recorded",
        lambda: hashlib.sha256(
            Path("/logs/verifier/graded.patch").read_bytes()
        ).hexdigest(),
    )
    report.check("bounded_course_completion_rates_function", bounded_function)
    report.check("source_tree_conservation_before_tests", source_identity)
    report.check(
        "typescript_typecheck",
        lambda: run(["npx", "--offline", "tsc", "--noEmit"], timeout=300).returncode,
    )
    report.check("postgres_application_role_is_bounded", role_identity)
    report.check("regression_report_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_completion_rate_worlds", hidden_tests)
    report.check("source_tree_conservation_after_tests", source_identity)
    report.check(
        "database_schema_conservation",
        lambda: (
            before
            if schema_identity() == before
            else (_ for _ in ()).throw(AssertionError("database schema changed"))
        ),
    )
    return report.write()


if __name__ == "__main__":
    sys.exit(main())
