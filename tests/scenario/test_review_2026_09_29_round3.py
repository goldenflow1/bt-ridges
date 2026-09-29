"""Third-pass review findings (docs/reviews/2026-09-29-third-pass.md). Each test states the correct behaviour."""

import os
import subprocess

from quarry.git import GitRepo
from quarry.profile import build_profile
from quarry.shell import Settings, Workflow, run_agent
from tests.conftest import write
from tests.scenario.test_review_2026_09_29 import M, Scripted, env


def test_R3_F2_H_SHELL_08_any_check_created_runtime_file_counts(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    statement = ("# Fix f\n\nOnly edit `m.py`.\n\n```bash\n"
                 "printf 'SELECT 2' > query.jinja && python -c 'import m; assert m.f() == \"SELECT 2\"'\n```\n")
    new_f = "def f():\n    import pathlib\n    return pathlib.Path(__file__).with_name('query.jinja').read_text()"
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": new_f})]
    settings = Settings()
    settings.fix_rounds = 0
    wf = Workflow(statement, repo.root, env(tmp_path), Scripted([edit]), settings)
    wf.run()
    assert not wf.store.best().checks_passed, "validation relied on query.jinja, which the patch does not contain"


def test_R3_F2_H_SHELL_08_disposable_artifacts_do_not_count(make_repo):
    repo = make_repo({"m.py": M})
    before = repo.fingerprint()
    write(repo.root, ".pytest_cache/v/cache/lastfailed", "{}")
    write(repo.root, "coverage.xml", "<coverage/>")
    write(repo.root, "debug.log", "x")
    assert repo.fingerprint() == before
    write(repo.root, "query.jinja", "SELECT 2")
    assert repo.fingerprint() != before


def test_R3_F4_H_SHELL_07_handoff_exception_never_returns_unchecked_patch(make_repo, tmp_path, monkeypatch):
    repo = make_repo({"m.py": M})
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]

    def broken(self):
        raise OSError("injected cleanup failure")

    monkeypatch.setattr(GitRepo, "undo_run_changes", broken)
    patch = run_agent("# Fix f\n\nOnly edit `m.py`.\n", repo.root, env(tmp_path), Scripted([edit]), Settings())
    if patch:
        check = subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo.root, text=True, capture_output=True)
        assert check.returncode == 0, "a returned patch must apply to the tree as the agent leaves it"


def test_R3_F4_H_SHELL_07_handoff_retries_cleanup_after_error(make_repo, tmp_path, monkeypatch):
    repo = make_repo({"m.py": M})
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
    real = GitRepo.undo_run_changes
    calls = {"n": 0}

    def flaky(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("transient")
        return real(self)

    monkeypatch.setattr(GitRepo, "undo_run_changes", flaky)
    patch = run_agent("# Fix f\n\nOnly edit `m.py`.\n", repo.root, env(tmp_path), Scripted([edit]), Settings())
    assert "+    return 2" in patch
    assert subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo.root, text=True).returncode == 0


def test_R3_F6_H_PROF_05_complete_env_credentials_are_not_discarded(tmp_path):
    root = str(tmp_path)
    write(root, "settings.py", (
        "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'shop', 'USER': 'app',"
        " 'HOST': 'db', 'PASSWORD': get_secret()}}\n"
    ))
    profile = build_profile(root, environ={"PGHOST": "db", "PGDATABASE": "shop", "PGUSER": "app", "PGPASSWORD": "fixture-pw"})
    first = profile.databases[0]
    assert first.password == "fixture-pw"
    assert "unresolved" not in first.source or "PASSWORD" not in first.source


def test_R3_X_H_GIT_05_paths_dirty_at_start_keep_content_and_staging(make_repo):
    repo = make_repo({"m.py": M, "notes.txt": "a\n"})
    write(repo.root, "notes.txt", "b\n")
    repo.git("add", "notes.txt")
    repo.ensure_baseline()  # snapshot after the pre-existing staged edit
    write(repo.root, "m.py", M.replace("return 1", "return 2", 1))
    repo.undo_run_changes()
    with open(os.path.join(repo.root, "notes.txt")) as handle:
        assert handle.read() == "b\n"
    assert repo.git("diff", "--cached", "--name-only").output.strip() == "notes.txt"
    assert repo.git("status", "--porcelain", "m.py").output.strip() == ""
