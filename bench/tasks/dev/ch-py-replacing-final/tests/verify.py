#!/usr/bin/env python3
import ast
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
ALLOWED = Path("meterline/balances.py")
ORIGINAL = Path("/opt/task/original-balances.py")
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/replacing_final_hidden_test.py")
HIDDEN_TARGET = APP / "tests/test_ridges_replacing_final.py"
PIN = "meterline-1.4.0-replacing-final"
AGENT_UID = 1000
CH_URL = "http://clickhouse:8123/"
CH_USER = "meterline"
CH_PASSWORD = "meterline-app-4e2a9c17"


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
            name="ch-py-replacing-final",
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


def find_function(tree):
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "tenant_balance_summary"
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one target function, found {len(matches)}")
    return matches[0]


def bounded_function():
    original_text = ORIGINAL.read_text()
    candidate_text = (APP / ALLOWED).read_text()
    original = find_function(ast.parse(original_text))
    candidate = find_function(ast.parse(candidate_text))
    original_lines = original_text.splitlines(keepends=True)
    candidate_lines = candidate_text.splitlines(keepends=True)
    if original_lines[: original.lineno - 1] != candidate_lines[: candidate.lineno - 1]:
        raise AssertionError("source before target function changed")
    if original_lines[original.end_lineno :] != candidate_lines[candidate.end_lineno :]:
        raise AssertionError("source after target function changed")

    def normalized_field(value):
        if isinstance(value, ast.AST):
            return ast.dump(value, include_attributes=False)
        if isinstance(value, list):
            return [normalized_field(item) for item in value]
        return value

    for field in original._fields:
        if field == "body":
            continue
        if normalized_field(getattr(original, field)) != normalized_field(
            getattr(candidate, field)
        ):
            raise AssertionError(f"function header field changed: {field}")
    if ast.get_docstring(original) != ast.get_docstring(candidate):
        raise AssertionError("function docstring changed")
    body_text = "".join(candidate_lines[candidate.lineno - 1 : candidate.end_lineno])
    if len(body_text.encode()) > 6000:
        raise AssertionError("target function exceeds 6000 bytes")
    if len(list(ast.walk(candidate))) > 500:
        raise AssertionError("target function exceeds 500 AST nodes")

    forbidden_nodes = (
        ast.AsyncFunctionDef,
        ast.Await,
        ast.ClassDef,
        ast.Delete,
        ast.For,
        ast.Global,
        ast.Import,
        ast.ImportFrom,
        ast.Lambda,
        ast.DictComp,
        ast.SetComp,
        ast.GeneratorExp,
        ast.Match,
        ast.Nonlocal,
        ast.Raise,
        ast.Try,
        ast.While,
        ast.With,
        ast.Yield,
        ast.YieldFrom,
    )
    dangerous_names = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "setattr",
        "sorted",
        "sum",
        "vars",
    }
    dangerous_attributes = {
        "command",
        "insert",
        "urlopen",
        "Request",
        "database",
        "url",
    }
    submitted_body = ast.Module(body=candidate.body, type_ignores=[])
    comprehensions = 0
    executes = 0
    for node in ast.walk(submitted_body):
        if isinstance(node, ast.FunctionDef):
            raise AssertionError("nested function definitions are forbidden")
        if isinstance(node, forbidden_nodes):
            raise AssertionError(f"forbidden construct: {type(node).__name__}")
        if isinstance(node, ast.ListComp):
            comprehensions += 1
        if isinstance(node, ast.Name) and (
            node.id in dangerous_names or "__" in node.id
        ):
            raise AssertionError(f"forbidden name: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr in dangerous_attributes or "__" in node.attr:
                raise AssertionError(f"forbidden attribute: {node.attr}")
            if node.attr in {"query", "_post"}:
                executes += 1
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(
                marker in node.value
                for marker in (
                    "orbit",
                    "tundra",
                    "delta",
                    "summit",
                    "ember",
                    "CHF",
                )
            )
        ):
            raise AssertionError("fixture-specific literal in production function")
    if comprehensions > 1:
        raise AssertionError("only the result-building comprehension is allowed")
    if executes != 1:
        raise AssertionError("the function must run exactly one query")
    return {
        "candidate_sha256": hashlib.sha256(candidate_text.encode()).hexdigest(),
        "function_sha256": hashlib.sha256(body_text.encode()).hexdigest(),
    }


def parse_pytest_run(result, expected_count, required_names):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    if result.returncode:
        raise AssertionError(
            f"test command failed ({result.returncode}); tail={plain[-4500:]}"
        )
    if not re.search(rf"\b{expected_count} passed\b", plain):
        raise AssertionError(f"expected exactly {expected_count} passing tests")
    if re.search(r"\b\d+ (failed|skipped|error|errors|xfailed|xpassed)\b", plain):
        raise AssertionError("test run reported failures, errors or skips")
    for name in required_names:
        if not re.search(rf"::{re.escape(name)} PASSED", plain):
            raise AssertionError(f"required test not reported as passed: {name}")
    return {
        "tests": expected_count,
        "stdout_sha256": hashlib.sha256(plain.encode()).hexdigest(),
    }


def focused_tests():
    result = run(
        ["pytest", "-p", "no:cacheprovider", "-v", "tests/test_balances.py"],
        timeout=600,
        check=False,
    )
    required = [
        "test_summary_totals_per_currency",
        "test_summary_is_scoped_to_tenant",
        "test_summary_skips_frozen_and_closed_accounts",
        "test_summary_after_merge_uses_latest_revision",
        "test_summary_for_unknown_tenant_is_empty",
        "test_negative_balances_are_summed",
        "test_history_lists_revisions_in_order",
        "test_current_balance_picks_highest_revision",
    ]
    return parse_pytest_run(result, 8, required)


def hidden_tests():
    if HIDDEN_TARGET.exists() or HIDDEN_TARGET.is_symlink():
        raise AssertionError("hidden test target already exists")
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    os.chmod(HIDDEN_TARGET, 0o400)
    try:
        result = run(
            [
                "pytest",
                "-p",
                "no:cacheprovider",
                "-v",
                str(HIDDEN_TARGET.relative_to(APP)),
            ],
            timeout=600,
            check=False,
        )
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)
    required = [
        "test_unmerged_revisions_count_once",
        "test_out_of_order_arrival_uses_highest_revision",
        "test_current_status_and_currency_decide_membership",
        "test_revision_not_timestamp_decides_the_current_row",
        "test_repeated_balances_are_not_collapsed",
        "test_same_answer_before_and_after_merge",
        "test_tenant_with_only_inactive_current_rows_is_empty",
    ]
    return parse_pytest_run(result, 7, required)


def clickhouse(sql, database="meterline_test"):
    import urllib.parse
    import urllib.request

    request = urllib.request.Request(
        CH_URL + "?" + urllib.parse.urlencode({"database": database}),
        data=sql.encode(),
        method="POST",
        headers={"X-ClickHouse-User": CH_USER, "X-ClickHouse-Key": CH_PASSWORD},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode()


EXPECTED_GRANTS = sorted(
    [
        "GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE, OPTIMIZE, "
        "SYSTEM MERGES ON meterline_dev.* TO meterline",
        "GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE, OPTIMIZE, "
        "SYSTEM MERGES ON meterline_test.* TO meterline",
        "GRANT SELECT(active, database, name, rows, `table`) ON system.parts TO meterline",
    ]
)


def role_identity():
    grants = sorted(line for line in clickhouse("SHOW GRANTS").splitlines() if line.strip())
    if grants != EXPECTED_GRANTS:
        raise AssertionError(f"unexpected application grants: {grants}")
    return grants


def schema_identity():
    listing = clickhouse(
        "SELECT database, name, engine, sorting_key, create_table_query FROM system.tables "
        "WHERE database IN ('meterline_dev', 'meterline_test') ORDER BY database, name "
        "FORMAT TSV"
    )
    return hashlib.sha256(listing.encode()).hexdigest()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.check(
        "transported_patch_recorded",
        lambda: hashlib.sha256(
            Path("/logs/verifier/graded.patch").read_bytes()
        ).hexdigest(),
    )
    report.check("bounded_tenant_balance_summary_function", bounded_function)
    report.check("source_tree_conservation_before_tests", source_identity)
    report.check(
        "python_compilation",
        lambda: compile((APP / ALLOWED).read_text(), str(ALLOWED), "exec") and "ok",
    )
    report.check(
        "ruff_lint",
        lambda: (
            run(["ruff", "check", "--no-cache", str(ALLOWED)], timeout=120).returncode
        ),
    )
    report.check("clickhouse_application_user_is_bounded", role_identity)
    report.check("regression_balance_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_replacing_merge_worlds", hidden_tests)
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
