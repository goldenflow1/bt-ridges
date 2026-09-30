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
ALLOWED = Path("observatory/report.py")
ORIGINAL = Path("/opt/task/original-balances.py")
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/report_hidden_test.py")
HIDDEN_TARGET = APP / "tests/test_ridges_report.py"
PIN = "ch-py-uniq-exact"
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
            name="ch-py-uniq-exact",
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
        if isinstance(node, ast.FunctionDef) and node.name == "visitor_count"
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

    for node in ast.walk(candidate):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise AssertionError("new imports and global mutation are forbidden")
        if isinstance(node, ast.Attribute) and node.attr in {"command", "insert", "_post"}:
            raise AssertionError("report must only use the query API")
    return {"function_sha256": hashlib.sha256(body_text.encode()).hexdigest()}



def permitted_constructs():
    original = ast.parse(ORIGINAL.read_text())
    candidate = ast.parse((APP / ALLOWED).read_text())
    for old in original.body:
        if isinstance(old, ast.FunctionDef) and not old.name.startswith("_"):
            matches = [node for node in candidate.body if isinstance(node, ast.FunctionDef) and node.name == old.name]
            if len(matches) != 1:
                raise AssertionError("public function missing or duplicated")
            new = matches[0]
            if ast.dump(old.args) != ast.dump(new.args):
                raise AssertionError("public signature changed")
            if (ast.dump(old.returns) if old.returns else None) != (ast.dump(new.returns) if new.returns else None):
                raise AssertionError("public return annotation changed")
    for node in ast.walk(candidate):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise AssertionError("new imports and global mutation are forbidden")
        if isinstance(node, ast.Attribute) and node.attr in {"command", "insert", "_post"}:
            raise AssertionError("reports must only use the query API")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"open", "eval", "exec", "compile", "__import__"}:
            raise AssertionError("external side-effect construct")


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
    result = run(["pytest", "-p", "no:cacheprovider", "-v", "tests/test_report.py"], check=False)
    return parse_pytest_run(result, 2, ['test_small_sample', 'test_empty_window'])


def hidden_tests():
    if HIDDEN_TARGET.exists() or HIDDEN_TARGET.is_symlink():
        raise AssertionError("hidden test target already exists")
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    os.chmod(HIDDEN_TARGET, 0o400)
    try:
        result = run(["pytest", "-p", "no:cacheprovider", "-v", str(HIDDEN_TARGET.relative_to(APP))], check=False)
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)
    return parse_pytest_run(result, 4, ['test_large_exact_cardinality', 'test_null_is_not_a_visitor', 'test_zero_duplicates_tenants_and_half_open_bounds', 'test_all_null_and_quoted_tenant'])


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
    report.check("bounded_visitor_count_function", bounded_function)
    report.check("bounded_public_contract", permitted_constructs)
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
    report.check("regression_report_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_report_semantics", hidden_tests)
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
