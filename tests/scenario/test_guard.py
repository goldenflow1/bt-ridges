"""Scenario tests for the guard (docs/specs/harness.md §7): realistic repos broken in realistic ways."""

import os

from quarry.guard import Guard, GuardContext
from quarry.spec import compile_statement
from tests.conftest import read, write

MODELS = '''"""Order reporting."""

from django.db import models
from django.db.models import Count, OuterRef, Subquery, Sum
from django.db.models.expressions import RawSQL


class OrderQuerySet(models.QuerySet):
    def with_totals(self):
        return self.annotate(total=Sum("items__amount"))

    def with_item_counts(self):
        return self.annotate(item_count=Count("items"))

    def legacy(self):
        return self.annotate(x=RawSQL("SELECT 1", ()))


def helper():
    return 1
'''

BOUNDED = """# Repair order totals

Work in `/app`. Limit production changes to `shop/models.py`, specifically
`OrderQuerySet.with_totals()`. Keep its signature and the rest of the file
unchanged, including imports; use only names the file already imports.

- totals do not double count;

Write the method as plain ORM expressions: no Python loops, comprehensions,
lambdas, exception handling, or context managers inside it. Do not add raw SQL
or database writes. Do not change tests.

```bash
python manage.py test shop
```
"""

DISCOVER = """# Restore bounded item counts

Find the queryset method that counts items and change only that method. Keep its
signature and the rest of its file unchanged, including imports.
"""

MIGRATION = """# Speed up order lookups

Add a new migration that creates an index for the customer lookup. Do not change
models or tests.
"""

FIXED = MODELS.replace(
    'return self.annotate(total=Sum("items__amount"))',
    'return self.annotate(total=Subquery(OuterRef("pk")))',
)


def repo_with_models(make_repo, extra=None, modes=None):
    files = {"shop/models.py": MODELS, "shop/views.py": "VIEW = 1\n", "shop/tests/test_models.py": "def test():\n    pass\n"}
    files.update(extra or {})
    return make_repo(files, modes)


def run_guard(repo, statement, target=None):
    ctx = GuardContext(repo, compile_statement(statement), target)
    return Guard().run(ctx)


def result(report, name):
    return next(r for r in report.results if r.name == name)


def test_H_GUARD_01_out_of_scope_tracked_change_is_reverted(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    write(repo.root, "shop/views.py", "VIEW = 2\n")
    report = run_guard(repo, BOUNDED)
    assert read(repo.root, "shop/views.py") == "VIEW = 1\n"
    assert "shop/views.py" not in report.diff
    assert result(report, "scope").ok
    assert report.eligible, report.render()


def test_H_GUARD_01_discover_mode_allows_one_file_only(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", MODELS.replace('Count("items")', 'Count("items", distinct=True)'))
    write(repo.root, "shop/views.py", "VIEW = 2\n")
    report = run_guard(repo, DISCOVER)
    assert not result(report, "scope").ok


def test_H_GUARD_02_junk_files_removed_and_allowed_migration_kept(make_repo):
    repo = repo_with_models(make_repo, {"shop/migrations/0001_initial.py": "# initial\n"})
    write(repo.root, "scratch_debug.py", "print(1)\n")
    write(repo.root, "shop/migrations/0002_order_customer_idx.py", "# index\n")
    report = run_guard(repo, MIGRATION)
    assert not os.path.exists(os.path.join(repo.root, "scratch_debug.py"))
    assert "0002_order_customer_idx.py" in report.diff
    assert report.eligible, report.render()


def test_H_GUARD_02_new_files_removed_when_not_asked(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    write(repo.root, "shop/extra.py", "X = 1\n")
    report = run_guard(repo, BOUNDED)
    assert not os.path.exists(os.path.join(repo.root, "shop/extra.py"))
    assert report.eligible, report.render()


def test_H_GUARD_03_mode_change_is_restored(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    os.chmod(os.path.join(repo.root, "shop/models.py"), 0o755)
    report = run_guard(repo, BOUNDED)
    assert "old mode" not in report.diff and "new mode" not in report.diff
    assert result(report, "file-modes").ok


def test_H_GUARD_04_text_outside_method_is_spliced_back(make_repo):
    repo = repo_with_models(make_repo)
    drifted = FIXED.replace('"""Order reporting."""', '"""Order reporting (edited)."""')
    drifted = drifted.replace('Count("items")', 'Count("items", distinct=True)')
    drifted = drifted.replace("def helper():\n    return 1\n", "def helper():\n    return 1\n\n\n")
    write(repo.root, "shop/models.py", drifted)
    report = run_guard(repo, BOUNDED)
    assert read(repo.root, "shop/models.py") == FIXED
    assert result(report, "bounded-symbol").ok
    assert report.eligible, report.render()


def test_H_GUARD_04_crlf_file_keeps_line_endings(make_repo):
    crlf = MODELS.replace("\n", "\r\n")
    repo = make_repo({"shop/models.py": "placeholder\n"})
    write(repo.root, "shop/models.py", crlf, newline="")
    repo.git("commit", "-qam", "crlf", "--no-gpg-sign")
    repo.ensure_baseline()
    candidate = FIXED.replace("\n", "\r\n").replace("def helper", "def  helper")
    write(repo.root, "shop/models.py", candidate, newline="")
    run_guard(repo, BOUNDED)
    assert read(repo.root, "shop/models.py") == FIXED.replace("\n", "\r\n")


def test_H_GUARD_04_missing_symbol_fails(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", MODELS.replace("def with_totals(self):", "def totals(self):"))
    report = run_guard(repo, BOUNDED)
    assert not report.eligible


def test_H_GUARD_04_discover_mode_two_methods_changed_fails(make_repo):
    repo = repo_with_models(make_repo)
    two = FIXED.replace('Count("items")', 'Count("items", distinct=True)')
    write(repo.root, "shop/models.py", two)
    report = run_guard(repo, DISCOVER)
    assert not result(report, "bounded-symbol").ok


def test_H_GUARD_04_discover_mode_one_method_changed_passes(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", MODELS.replace('Count("items")', 'Count("items", distinct=True)'))
    report = run_guard(repo, DISCOVER)
    assert report.eligible, report.render()


def test_H_GUARD_05_signature_change_fails(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED.replace("def with_totals(self):", "def with_totals(self, distinct=True):"))
    report = run_guard(repo, BOUNDED)
    assert not result(report, "signature").ok


def test_H_GUARD_06_new_import_reverted_then_unbound_name_detected(make_repo):
    repo = repo_with_models(make_repo)
    candidate = FIXED.replace("from django.db import models\n", "from django.db import models\nfrom django.db.models import F\n")
    candidate = candidate.replace('Subquery(OuterRef("pk"))', 'F("pk")')
    write(repo.root, "shop/models.py", candidate)
    report = run_guard(repo, BOUNDED)
    assert "from django.db.models import F" not in read(repo.root, "shop/models.py")
    imports = result(report, "imports")
    assert not imports.ok and "F" in imports.detail


def test_H_GUARD_07_loop_in_method_fails(make_repo):
    repo = repo_with_models(make_repo)
    loop = MODELS.replace(
        '        return self.annotate(total=Sum("items__amount"))',
        '        for _ in range(1):\n            pass\n        return self.annotate(total=Sum("items__amount"))',
    )
    write(repo.root, "shop/models.py", loop)
    report = run_guard(repo, BOUNDED)
    assert not result(report, "statement-rules").ok
    assert "no_loops" in result(report, "statement-rules").detail


def test_H_GUARD_07_added_raw_sql_fails_but_existing_is_fine(make_repo):
    repo = repo_with_models(make_repo)
    raw = MODELS.replace('Sum("items__amount")', 'RawSQL("SELECT 1", ())')
    write(repo.root, "shop/models.py", raw)
    report = run_guard(repo, BOUNDED)
    assert "no_raw_sql" in result(report, "statement-rules").detail
    legacy_only = MODELS.replace('RawSQL("SELECT 1", ())', 'RawSQL("SELECT 2", ())')
    write(repo.root, "shop/models.py", legacy_only)
    statement = BOUNDED.replace("`OrderQuerySet.with_totals()`", "`OrderQuerySet.legacy()`")
    assert result(run_guard(repo, statement), "statement-rules").ok


def test_H_GUARD_08_empty_and_whitespace_only_fail(make_repo):
    repo = repo_with_models(make_repo)
    assert not result(run_guard(repo, BOUNDED), "non-empty").ok
    write(repo.root, "shop/models.py", MODELS.replace('        return self.annotate(total=Sum("items__amount"))',
                                                      '        return self.annotate(total=Sum("items__amount"))   '))
    assert not result(run_guard(repo, BOUNDED), "non-empty").ok


def test_H_GUARD_09_patch_applies_to_clean_tree(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    report = run_guard(repo, BOUNDED)
    assert result(report, "apply-check").ok
    assert repo.apply_check(report.diff).ok


def test_H_GUARD_10_test_changes_reverted_unless_allowed(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    write(repo.root, "shop/tests/test_models.py", "def test():\n    assert True\n")
    write(repo.root, "shop/tests/test_new.py", "def test_new():\n    pass\n")
    report = run_guard(repo, BOUNDED)
    assert "shop/tests" not in report.diff
    allowed = "# Fix totals\n\nFix `shop/models.py` and add a regression test in `shop/tests/test_new.py`.\n"
    write(repo.root, "shop/tests/test_new.py", "def test_new():\n    pass\n")
    report = run_guard(repo, allowed)
    assert "shop/tests/test_new.py" in report.diff


def test_H_GUARD_11_report_is_structured(make_repo):
    repo = repo_with_models(make_repo)
    write(repo.root, "shop/models.py", FIXED)
    os.chmod(os.path.join(repo.root, "shop/models.py"), 0o755)
    report = run_guard(repo, BOUNDED)
    names = [r.name for r in report.results]
    assert names[:3] == ["scope", "file-modes", "python-compiles"]
    assert any("restored mode" in note for note in report.repairs)
    assert "PASS scope" in report.render()
