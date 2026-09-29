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
ALLOWED = Path("tidewater/reports.py")
ORIGINAL = Path("/opt/task/original-reports.py")
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/revenue_fanout_hidden_test.py")
HIDDEN_TARGET = APP / "tests/test_ridges_revenue_fanout.py"
PIN = "tidewater-0.9.2-revenue-fanout"
AGENT_UID = 1000
DEV_URL = "postgresql://tidewater:tidewater-app-5c1e93d7@postgres:5432/tidewater_dev"
TEST_URL = "postgresql://tidewater:tidewater-app-5c1e93d7@postgres:5432/tidewater_test"


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
            name="py-sqla-orders-fanout",
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
        if isinstance(node, ast.FunctionDef) and node.name == "customer_revenue"
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
        "add",
        "commit",
        "connection",
        "cursor",
        "delete",
        "exec_driver_sql",
        "flush",
        "raw_connection",
        "text",
        "literal_column",
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
            if node.attr in {"execute", "scalars", "scalar"}:
                executes += 1
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(
                marker in node.value
                for marker in (
                    "Otto",
                    "Pia",
                    "Quin",
                    "Rosa",
                    "Sven",
                    "Tess",
                    "Ugo",
                    "Vera",
                    "Wes",
                    "Xan",
                    "Yara",
                    "east",
                    "west",
                )
            )
        ):
            raise AssertionError("fixture-specific literal in production function")
    if comprehensions > 1:
        raise AssertionError("only the result-building comprehension is allowed")
    if executes != 1:
        raise AssertionError("the function must execute exactly one statement")
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
        ["pytest", "-p", "no:cacheprovider", "-v", "tests/test_reports.py"],
        timeout=600,
        check=False,
    )
    required = [
        "test_revenue_sums_order_lines",
        "test_cancelled_orders_are_excluded",
        "test_customer_without_orders_is_listed_with_zero",
        "test_unshipped_orders_still_count_as_revenue",
        "test_region_filter",
        "test_placed_window_is_half_open",
        "test_revenue_ordering_breaks_ties_by_customer_id",
        "test_sku_volume_counts_shipped_orders_only",
        "test_pending_orders_lists_paid_unshipped",
    ]
    return parse_pytest_run(result, 9, required)


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
        "test_equal_line_amounts_are_each_counted",
        "test_split_shipments_do_not_multiply_lines",
        "test_parcels_shipped_together_count_once",
        "test_mixed_customers_rank_by_true_revenue",
        "test_customers_without_qualifying_orders_report_integer_zero",
        "test_report_is_one_statement",
    ]
    return parse_pytest_run(result, 6, required)


def role_identity():
    result = run(
        [
            "psql",
            DEV_URL,
            "-At",
            "-c",
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname='tidewater'",
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
    report.check("bounded_customer_revenue_function", bounded_function)
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
    report.check("postgres_application_role_is_bounded", role_identity)
    report.check("regression_report_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_revenue_fanout_worlds", hidden_tests)
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
