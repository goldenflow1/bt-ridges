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
ALLOWED = Path("internal/store/events.go")
ORIGINAL = Path("/opt/task/original-events.go")
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/pagination_hidden_test.go")
HIDDEN_TARGET = APP / "internal/store/ridges_pagination_hidden_test.go"
PIN = "auditfeed-0.7.1-keyset-pagination"
AGENT_UID = 1000
DEV_URL = "postgresql://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_dev"
TEST_URL = "postgresql://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_test"
FUNCSPAN = "/opt/task/funcspan"


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
            name="go-sqlx-pagination",
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


def span(path):
    result = run([FUNCSPAN, str(path), "*Store", "ListEvents"], timeout=60)
    info = json.loads(result.stdout)
    if info["found"] != 1:
        raise AssertionError(f"expected one ListEvents method, found {info['found']}")
    return info


def bounded_method():
    original_bytes = ORIGINAL.read_bytes()
    candidate_bytes = (APP / ALLOWED).read_bytes()
    original = span(ORIGINAL)
    candidate = span(APP / ALLOWED)
    if original_bytes[: original["start"]] != candidate_bytes[: candidate["start"]]:
        raise AssertionError("source before target method changed")
    if original_bytes[original["end"] :] != candidate_bytes[candidate["end"] :]:
        raise AssertionError("source after target method changed")
    if original["header"] != candidate["header"]:
        raise AssertionError("method signature changed")
    if original["doc"] != candidate["doc"]:
        raise AssertionError("method doc comment changed")
    if candidate["imports"] != original["imports"]:
        raise AssertionError("imports changed")
    method_bytes = candidate_bytes[candidate["start"] : candidate["end"]]
    if len(method_bytes) > 6000:
        raise AssertionError("target method exceeds 6000 bytes")
    if candidate["nodes"] > 600:
        raise AssertionError("target method exceeds 600 AST nodes")
    if candidate["loops"] or candidate["go_stmts"] or candidate["func_lits"]:
        raise AssertionError("loops, goroutines and function literals are forbidden in the method")
    calls = candidate["calls"]
    queries = sum(
        calls.get(name, 0)
        for name in (
            "SelectContext",
            "QueryxContext",
            "QueryContext",
            "QueryRowxContext",
            "QueryRowContext",
            "Select",
            "Queryx",
            "Query",
            "Get",
            "GetContext",
        )
    )
    if queries != 1:
        raise AssertionError(f"the method must run exactly one query, found {queries}")
    forbidden_calls = {
        "Exec",
        "ExecContext",
        "MustExec",
        "Begin",
        "BeginTx",
        "Beginx",
        "BeginTxx",
        "NamedExec",
        "Rebind",
        "In",
    }
    used = sorted(set(calls) & forbidden_calls)
    if used:
        raise AssertionError(f"forbidden calls in method: {used}")
    for literal in candidate["string_lits"]:
        for marker in ("gannet", "petrel", "skua", "importer", "backfill"):
            if marker in literal:
                raise AssertionError("fixture-specific literal in production method")
    return {
        "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "method_sha256": hashlib.sha256(method_bytes).hexdigest(),
    }


def parse_go_test_run(result, expected_names):
    plain = result.stdout
    if result.returncode:
        raise AssertionError(
            f"test command failed ({result.returncode}); tail={plain[-4500:]}"
        )
    passed = re.findall(r"^\s*--- PASS: (\S+)", plain, re.MULTILINE)
    if re.search(r"^\s*--- (FAIL|SKIP): ", plain, re.MULTILINE):
        raise AssertionError("test run reported failures or skips")
    top_level = sorted(name for name in passed if "/" not in name)
    if top_level != sorted(expected_names):
        raise AssertionError(f"unexpected test set: {top_level}")
    return {
        "tests": len(top_level),
        "stdout_sha256": hashlib.sha256(plain.encode()).hexdigest(),
    }


def focused_tests():
    result = run(
        ["go", "test", "-count=1", "-v", "./..."],
        timeout=600,
        check=False,
    )
    required = [
        "TestCursorRoundTrip",
        "TestDecodeCursorRejectsGarbage",
        "TestListEventsFirstPage",
        "TestListEventsWalksAllPages",
        "TestListEventsOrdersByTimeNotID",
        "TestListEventsTenantIsolation",
        "TestListEventsClampsLimit",
        "TestListEventsRejectsBadCursor",
        "TestCountEvents",
    ]
    return parse_go_test_run(result, required)


def hidden_tests():
    if HIDDEN_TARGET.exists() or HIDDEN_TARGET.is_symlink():
        raise AssertionError("hidden test target already exists")
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    os.chmod(HIDDEN_TARGET, 0o400)
    try:
        result = run(
            [
                "go",
                "test",
                "-count=1",
                "-v",
                "-run",
                "^TestHidden",
                "./internal/store/",
            ],
            timeout=600,
            check=False,
        )
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)
    required = [
        "TestHiddenTiesAcrossPageBoundaries",
        "TestHiddenBackfilledEventsHaveIDsOutOfTimeOrder",
        "TestHiddenWholeFeedAtOneInstant",
        "TestHiddenMicrosecondNeighboursAndTies",
        "TestHiddenEventsWrittenAtCursorInstantAppearLater",
        "TestHiddenTenantsShareTimestamps",
    ]
    return parse_go_test_run(result, required)


def gofmt_clean():
    result = run(["gofmt", "-l", str(ALLOWED)], timeout=60)
    if result.stdout.strip():
        raise AssertionError("gofmt reports the file is not formatted")
    return "ok"


def role_identity():
    result = run(
        [
            "psql",
            DEV_URL,
            "-At",
            "-c",
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname='auditfeed'",
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
    report.check("bounded_list_events_method", bounded_method)
    report.check("source_tree_conservation_before_tests", source_identity)
    report.check("gofmt", gofmt_clean)
    report.check(
        "go_vet",
        lambda: run(["go", "vet", "./..."], timeout=300).returncode,
    )
    report.check("postgres_application_role_is_bounded", role_identity)
    report.check("regression_store_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_keyset_pagination_worlds", hidden_tests)
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
