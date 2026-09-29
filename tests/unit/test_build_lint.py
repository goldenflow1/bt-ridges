"""Unit tests: bundler and pre-screen lint (docs/specs/harness.md §10)."""

import ast
import os

import pytest

from tests.conftest import write
from tools.build import BuildError, build, dependency_order, internal_imports
from tools.prescreen_lint import lint


def test_H_BUILD_01_bundle_is_single_stdlib_file_with_entry_point():
    bundle = build()
    tree = ast.parse(bundle, feature_version=(3, 9))
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "agent_main" in names
    assert "from quarry" not in bundle and "import quarry" not in bundle
    assert bundle.count("from __future__ import annotations") == 1


def test_H_BUILD_02_duplicate_names_and_bad_imports_fail(tmp_path):
    pkg = str(tmp_path / "quarry")
    write(pkg, "agent.py", "from quarry.a import X\nfrom quarry.b import Y\n\ndef agent_main(input):\n    return X + Y\n")
    write(pkg, "a.py", "X = 1\nHELPER = 1\n")
    write(pkg, "b.py", "Y = 1\nHELPER = 2\n")
    with pytest.raises(BuildError, match="duplicate top-level name 'HELPER'"):
        build(pkg)
    write(pkg, "b.py", "import quarry.a\nY = 1\n")
    with pytest.raises(BuildError, match="not allowed"):
        build(pkg)
    with pytest.raises(BuildError, match="cycle"):
        dependency_order({"agent": {"a"}, "a": {"agent"}})
    assert internal_imports(ast.parse("from quarry.a import (\n    X,\n    Y,\n)\n")) == [("a", 1, 4)]


def test_H_BUILD_03_assets_embedded():
    bundle = build()
    assert '"prompts/driver.md": """' in bundle and '"packs/clickhouse.md": """' in bundle
    namespace = {"__name__": "bundle_under_test"}
    exec(compile(bundle, "agent.py", "exec"), namespace)
    assert "ReplacingMergeTree" in namespace["asset"]("packs/clickhouse.md")
    assert namespace["EMBEDDED_ASSETS"]["prompts/driver.md"].startswith("You are")


def test_H_LINT_01_flags_banned_content():
    fails, warns, _ = lint('print("the hidden tests run in a sandbox")\nx = "http://example.com"\n')
    assert fails == 2 and warns == 1
    fails, _, _ = lint('proxy = os.environ["SANDBOX_PROXY_URL"]\n')
    assert fails == 0
    fails, _, _ = lint("blob = '" + "A" * 250 + "'\n")
    assert fails == 1


def test_H_LINT_01_repository_sources_are_clean():
    root = os.path.join(os.path.dirname(__file__), "..", "..", "src", "quarry")
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith((".py", ".md")):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    fails, _, report = lint(handle.read())
                assert fails == 0, (name, report)


def _spec_tree(tmp_path, rows, tests):
    from tests.conftest import write as w

    w(str(tmp_path), "docs/specs/s.md", "| ID | Req | Verify |\n|---|---|---|\n" + "".join(rows))
    w(str(tmp_path), "tests/test_x.py", tests)
    return str(tmp_path)


def test_H_LINT_01_traceability_counts_e2e_and_rejects_malformed_rows(tmp_path):
    from tools.gate import traceability

    covered = _spec_tree(tmp_path / "a", ["| H-X-01 | thing | unit, e2e |\n"], "def test_H_X_01(): pass\n")
    assert traceability(covered)
    missing = _spec_tree(tmp_path / "b", ["| H-X-02 | thing | e2e |\n"], "")
    assert not traceability(missing)  # an e2e-only requirement without a test must fail, not be skipped
    unknown = _spec_tree(tmp_path / "c", ["| H-X-03 | thing | vibes |\n"], "def test_H_X_03(): pass\n")
    assert not traceability(unknown)
