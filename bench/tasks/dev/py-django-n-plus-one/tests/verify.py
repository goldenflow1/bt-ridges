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
ALLOWED = (
    Path("recipes/models.py"),
    Path("recipes/serializers.py"),
    Path("recipes/views.py"),
)
MANIFEST = Path("/opt/task/source-manifest.json")
ALLOWED_METADATA = Path("/opt/task/allowed-metadata.json")
HIDDEN_SOURCE = Path("/tests/listing_hidden_test.py")
HIDDEN_TARGET = APP / "recipes/tests/test_ridges_listing_hidden.py"
PIN = "pantry-3.2.1-listing-queries"
AGENT_UID = 1000
DEV_URL = "postgresql://pantry:pantry-app-6f3b19d2@postgres:5432/pantry_dev"
TEST_URL = "postgresql://pantry:pantry-app-6f3b19d2@postgres:5432/pantry_test"


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
            name="py-django-n-plus-one",
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
        if relative in ALLOWED:
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
    metadata = json.loads(ALLOWED_METADATA.read_text())
    digests = {}
    for allowed in ALLOWED:
        target = APP / allowed
        if target.is_symlink() or not target.is_file():
            raise AssertionError(f"editable source is not a regular file: {allowed}")
        if target.stat().st_uid != AGENT_UID:
            raise AssertionError(f"editable source owner changed: {allowed}")
        if stat.S_IMODE(target.lstat().st_mode) != metadata["mode"]:
            raise AssertionError(f"editable source mode changed: {allowed}")
        digests[str(allowed)] = hashlib.sha256(target.read_bytes()).hexdigest()
    return digests


ALLOWED_IMPORT_ROOTS = ("django", "recipes")
FORBIDDEN_IMPORTS = (
    "django.core.cache",
    "django.db.connection",
    "django.db.connections",
    "django.db.backends",
    "django.views.decorators.cache",
)


def construct_limits():
    dangerous_names = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "open",
        "RawSQL",
        "connection",
        "connections",
        "cache",
        "caches",
        "lru_cache",
        "cached_property",
    }
    dangerous_attributes = {"raw", "extra", "cursor", "execute", "executemany", "cache"}
    fixture_markers = (
        "zucchini",
        "Zesty",
        "Minty",
        "Harvest",
        "Mira",
        "Batch",
        "Even Split",
        "Thirds",
        "Tie",
        "Fresh",
        "Pantry",
    )
    for allowed in ALLOWED:
        tree = ast.parse((APP / allowed).read_text(), str(allowed))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise AssertionError(f"relative import in {allowed}")
                names = [node.module or ""] + [
                    f"{node.module}.{alias.name}" for alias in node.names
                ]
            else:
                names = []
            for name in names:
                if name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    raise AssertionError(f"import outside django/recipes in {allowed}: {name}")
                if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                    raise AssertionError(f"forbidden import in {allowed}: {name}")
            if isinstance(node, ast.Name) and (node.id in dangerous_names or "__" in node.id):
                raise AssertionError(f"forbidden name in {allowed}: {node.id}")
            if isinstance(node, ast.Attribute) and (
                node.attr in dangerous_attributes or node.attr.startswith("__")
            ):
                raise AssertionError(f"forbidden attribute in {allowed}: {node.attr}")
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and any(marker in node.value for marker in fixture_markers)
            ):
                raise AssertionError(f"fixture-specific literal in {allowed}")
    return "ok"


def parse_test_run(result, expected_count, required_names):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    if result.returncode:
        raise AssertionError(
            f"test command failed ({result.returncode}); tail={plain[-4500:]}"
        )
    if not re.search(rf"Ran {expected_count} tests?", plain):
        raise AssertionError(f"expected exactly {expected_count} tests")
    if not re.search(r"^OK$", plain, re.MULTILINE):
        raise AssertionError("test run did not finish OK")
    for name in required_names:
        if not re.search(rf"^{re.escape(name)} \(.*\) \.\.\. ok$", plain, re.MULTILINE):
            raise AssertionError(f"required test not reported ok: {name}")
    return {
        "tests": expected_count,
        "stdout_sha256": hashlib.sha256(plain.encode()).hexdigest(),
    }


def manage_test(label):
    return run(
        ["python", "manage.py", "test", label, "--keepdb", "--noinput", "--verbosity", "2"],
        timeout=600,
        check=False,
    )


def focused_tests():
    required = [
        "test_list_payload",
        "test_rating_summary_in_list",
        "test_newest_first_and_unpublished_hidden",
        "test_tag_filter",
        "test_pagination",
        "test_empty_list",
        "test_detail_payload",
        "test_unpublished_detail_is_404",
    ]
    return parse_test_run(manage_test("recipes.tests.test_api"), 8, required)


def hidden_tests():
    if HIDDEN_TARGET.exists() or HIDDEN_TARGET.is_symlink():
        raise AssertionError("hidden test target already exists")
    shutil.copyfile(HIDDEN_SOURCE, HIDDEN_TARGET)
    os.chmod(HIDDEN_TARGET, 0o400)
    try:
        result = manage_test("recipes.tests.test_ridges_listing_hidden")
    finally:
        HIDDEN_TARGET.unlink(missing_ok=True)
    required = [
        "test_query_count_does_not_grow_with_rows",
        "test_payload_is_exact_with_many_relations",
        "test_rating_rounding_matches_model_and_detail",
        "test_filtered_later_pages_stay_bounded",
        "test_unpublished_recipes_do_not_leak",
        "test_same_timestamp_recipes_page_in_id_order",
        "test_listing_counts_and_average_come_from_the_database",
    ]
    return parse_test_run(result, 7, required)


def role_identity():
    result = run(
        [
            "psql",
            DEV_URL,
            "-At",
            "-c",
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname='pantry'",
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
            DEV_URL,
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


def compile_all():
    for allowed in ALLOWED:
        compile((APP / allowed).read_text(), str(allowed), "exec")
    return "ok"


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.check(
        "transported_patch_recorded",
        lambda: hashlib.sha256(
            Path("/logs/verifier/graded.patch").read_bytes()
        ).hexdigest(),
    )
    report.check("source_tree_conservation_before_tests", source_identity)
    report.check("python_compilation", compile_all)
    report.check("allowed_module_construct_limits", construct_limits)
    report.check(
        "ruff_lint",
        lambda: run(["ruff", "check", "--no-cache", "recipes/"], timeout=120).returncode,
    )
    report.check(
        "model_state_unchanged",
        lambda: run(
            ["python", "manage.py", "makemigrations", "--check", "--dry-run", "recipes"],
            timeout=120,
        ).returncode,
    )
    report.check("postgres_application_role_is_bounded", role_identity)
    report.check("regression_api_tests", focused_tests)
    before = schema_identity()
    report.check("hidden_listing_query_worlds", hidden_tests)
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
