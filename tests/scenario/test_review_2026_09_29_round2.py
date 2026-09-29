"""Second-round review findings (2026-09-29). Each test states the correct behaviour."""


from quarry.guard import Guard, GuardContext
from quarry.shell import Settings, Workflow, run_agent
from quarry.spec import compile_statement
from quarry.tools import transaction_control
from tests.conftest import read, write
from tests.scenario.test_review_2026_09_29 import M, Scripted, env

DISCOVER = "# Fix the query\n\nFind the query method and change only that method.\n"


def test_R2_1_H_GUARD_15_discover_mode_freezes_rest_of_file():
    assert compile_statement(DISCOVER).scope.rest_frozen


def test_R2_1_H_GUARD_15_discover_mode_rejects_two_methods(make_repo):
    repo = make_repo({"m.py": M})
    write(repo.root, "m.py", M.replace("return 1", "return 2"))
    report = Guard().run(GuardContext(repo, compile_statement(DISCOVER)))
    assert not report.eligible, report.render()


def test_R2_1_H_GUARD_15_discovered_target_keeps_only_that_method(make_repo):
    repo = make_repo({"m.py": M})
    write(repo.root, "m.py", M.replace("return 1", "return 2"))
    report = Guard().run(GuardContext(repo, compile_statement(DISCOVER), ("m.py", "f")))
    assert read(repo.root, "m.py") == "def f():\n    return 2\n\n\ndef g():\n    return 1\n"
    assert report.eligible, report.render()


def test_R2_2_H_SHELL_08_untracked_helper_created_by_checks_is_not_evidence(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    statement = ("# Fix f\n\nOnly edit `m.py`.\n\n```bash\n"
                 "printf 'X = 2\\n' > helper.py && python -c 'import m; assert m.f() == 2'\n```\n")
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    from helper import X\n    return X"})]
    settings = Settings()
    settings.fix_rounds = 0
    wf = Workflow(statement, repo.root, env(tmp_path), Scripted([edit]), settings)
    patch = wf.run()
    wf.handoff(patch)
    best = wf.store.best()
    assert best is not None and not best.checks_passed, "validation relied on a file the patch does not contain"


def test_R2_3_H_SHELL_10_failed_checks_make_candidate_last_resort(make_repo, tmp_path, capsys):
    repo = make_repo({"m.py": M})
    # the check passes on unmodified code and fails after the edit, so the failure is evidence against the patch
    statement = "# Fix f\n\nOnly edit `m.py`.\n\n```bash\npython -c 'import m; assert m.f() == 1'\n```\n"
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
    settings = Settings()
    settings.fix_rounds = 0
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([edit]), settings)
    assert "+    return 2" in patch
    err = capsys.readouterr().err
    assert "last-resort" in err and "python -c 'import m; assert m.f() == 1'" in err


def test_R2_4_H_SHELL_07_handoff_never_returns_a_patch_that_does_not_apply(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = Workflow("# T\n\nOnly edit `m.py`.\n", repo.root, env(tmp_path), Scripted([]), Settings())
    wf.prepare()
    bad = "diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n def nope():\n-    return 9\n+    return 8\n"
    assert wf.handoff(bad) == ""


def test_R2_4_H_SHELL_07_handoff_falls_back_to_next_candidate_that_applies(make_repo, tmp_path):
    from quarry.shell import Candidate

    repo = make_repo({"m.py": M})
    wf = Workflow("# T\n\nOnly edit `m.py`.\n", repo.root, env(tmp_path), Scripted([]), Settings())
    wf.prepare()
    write(repo.root, "m.py", M.replace("def f():\n    return 1", "def f():\n    return 3"))
    good = repo.diff()
    repo.restore("m.py")
    bad = good.replace("-    return 1", "-    return 9")
    wf.store.add(Candidate(bad, 5.0, True))
    wf.store.add(Candidate(good, 1.0, True))
    assert wf.handoff(bad) == good


def test_R2_5_H_TOOL_09_comments_do_not_hide_transaction_control():
    for query in ["/* end */ COMMIT", "SELECT 1; -- done\nCOMMIT", "/* a /* nested */ b */ ROLLBACK", "SELECT 1;/**/END"]:
        assert transaction_control(query), query
    for query in ["SELECT 'COMMIT; x'", "SELECT $$ ; COMMIT $$", 'SELECT "end" FROM t', "SELECT 1 -- ; COMMIT"]:
        assert not transaction_control(query), query


def test_R2_5_H_TOOL_09_meta_command_after_comment_detected():
    assert transaction_control("SELECT 1;\n  \\c other")
    assert not transaction_control("SELECT E'\\\\c'")
