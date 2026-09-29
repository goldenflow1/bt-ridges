"""Regression cases from docs/reviews/2026-09-29-architecture-implementation.md (R1–R8 + extras).

Each test states the correct behaviour; a failure here reproduces the review finding.
"""

import os
import subprocess

from quarry.guard import Guard, GuardContext
from quarry.llm import ChatResult, ModelRoute, ProxyClient, ToolCall
from quarry.profile import build_profile
from quarry.shell import Settings, run_agent
from quarry.spec import compile_statement
from quarry.wallet import Wallet
from tests.conftest import read, write

M = "def f():\n    return 1\n\n\ndef g():\n    return 1\n"


class Scripted:
    """In-process model: each step is a list of (tool, args); afterwards it only calls finish."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.n = 0
        self.telemetry = []

    def complete(self, messages, route, tools=None, role="driver", timeout=0, max_tokens=None, deadline=None):
        self.n += 1
        step = self.steps.pop(0) if self.steps else [("finish", {"summary": "done"})]
        calls = [ToolCall(f"c{self.n}_{i}", name, args) for i, (name, args) in enumerate(step)]
        msg = {"role": "assistant", "content": "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}} for c in calls]}
        return ChatResult("", calls, {}, "m", msg)


def env(tmp_path):
    return {"AGENT_TIMEOUT": "300", "RIDGES_MAX_COST_USD": "0.29", "PATH": os.environ["PATH"], "HOME": str(tmp_path)}


def guard(repo, statement):
    return Guard().run(GuardContext(repo, compile_statement(statement)))


# ---------------------------------------------------------------- R1 handoff


def test_R1_H_SHELL_07_worktree_is_clean_and_patch_applies_after_return(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    statement = "# Fix f\n\nChange only `f()` in `m.py`.\n"
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([edit]), Settings())
    assert "+    return 2" in patch
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo.root, capture_output=True, text=True).stdout == ""
    check = subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo.root, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr


def test_R1_H_SHELL_07_new_file_patch_applies_after_return(make_repo, tmp_path):
    repo = make_repo({"app/models.py": "X = 1\n", "app/migrations/0001_initial.py": "# 1\n"})
    statement = "# Index\n\nAdd a new migration that creates the index.\n"
    create = [("create", {"path": "app/migrations/0002_idx.py", "content": "# 2\n"})]
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([create]), Settings())
    assert "0002_idx.py" in patch
    assert not os.path.exists(os.path.join(repo.root, "app/migrations/0002_idx.py"))
    assert subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo.root, text=True).returncode == 0


# ---------------------------------------------------------------- R2 deadlines


def test_R2_H_LLM_07_retries_respect_absolute_deadline():
    now = [0.0]
    timeouts, sleeps = [], []

    def transport(url, body, headers, timeout):
        timeouts.append(timeout)
        now[0] += timeout
        return 0, "transport error: timed out"

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = ProxyClient(Wallet(1.0), {"SANDBOX_PROXY_URL": "http://p"}, transport, sleep=sleep, clock=lambda: now[0])
    try:
        client.complete([{"role": "user", "content": "x"}], ModelRoute("m"), deadline=20.0)
    except Exception:
        pass
    assert now[0] <= 20.5, (timeouts, sleeps)


# ---------------------------------------------------------------- R3 scope


def test_R3_H_GUARD_12_only_named_symbol_may_change(make_repo):
    repo = make_repo({"m.py": M})
    write(repo.root, "m.py", M.replace("return 1", "return 2"))  # both f and g
    report = guard(repo, "# Fix f\n\nChange only `f()` in `m.py`.\n")
    # g() is outside the named scope: the guard must splice it back, so the patch changes f() only.
    assert read(repo.root, "m.py") == "def f():\n    return 2\n\n\ndef g():\n    return 1\n"
    assert report.diff.count("+    return 2") == 1 and report.eligible, report.render()


def test_R3_H_GUARD_13_deleting_the_scoped_file_fails(make_repo):
    repo = make_repo({"m.py": M})
    os.remove(os.path.join(repo.root, "m.py"))
    statement = ("# Fix f\n\nLimit production changes to `m.py`, specifically `f()`. Keep its signature and the rest "
                 "of the file unchanged, including imports.\n")
    report = guard(repo, statement)
    assert not report.eligible, report.render()


# ---------------------------------------------------------------- R4 file-scope construct rules


def test_R4_H_GUARD_14_rules_apply_with_file_only_scope(make_repo):
    repo = make_repo({"m.py": M})
    write(repo.root, "m.py", M.replace("def f():\n    return 1", "def f():\n    for _ in range(1):\n        pass\n    return 1"))
    report = guard(repo, "# Fix\n\nOnly edit `m.py`. Do not use loops.\n")
    assert not report.eligible, report.render()


# ---------------------------------------------------------------- R5 evidence identity


def test_R5_H_SHELL_08_returned_patch_is_the_validated_tree(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    statement = ("# Fix f\n\nOnly edit `m.py`.\n\n```bash\nsed -i 's/return 2/return 3/' m.py && grep -q 'return 3' m.py\n```\n")
    edit = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([edit]), Settings())
    added = [line for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
    # Either the validated content is returned, or the candidate that returns 2 is not presented as check-verified.
    assert "+    return 3" in added or "+    return 2" not in added


# ---------------------------------------------------------------- R6 requested new production file


def test_R6_H_SPEC_12_requested_new_file_is_kept(make_repo, tmp_path):
    repo = make_repo({"app.py": "X = 1\n"})
    statement = "# Service\n\nCreate a new file `service.py` to implement the production query.\n"
    create = [("create", {"path": "service.py", "content": "def q():\n    return 1\n"})]
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([create]), Settings())
    assert "service.py" in patch


# ---------------------------------------------------------------- R7 database discovery


def test_R7_H_PROF_05_unresolved_config_does_not_become_default_target(tmp_path):
    root = str(tmp_path)
    write(root, "settings.py", (
        "import os\nDATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ['PGDATABASE'],"
        " 'USER': os.environ['PGUSER'], 'HOST': os.environ['PGHOST']}}\n"
    ))
    profile = build_profile(root, environ={"PGHOST": "db", "PGDATABASE": "shop", "PGUSER": "app", "PGPASSWORD": "pw"})
    first = profile.databases[0]
    assert (first.host, first.name, first.user) == ("db", "shop", "app")


# ---------------------------------------------------------------- R8 shell semantics


def test_R8_H_SPEC_13_fenced_block_keeps_cd_and_quoting():
    spec = compile_statement('# T\n\n```bash\ncd backend\npytest -k "a  b"\n```\n')
    assert len(spec.checks) == 1
    assert "cd backend" in spec.checks[0] and 'pytest -k "a  b"' in spec.checks[0]


def test_R8_H_SPEC_14_untyped_sql_block_is_not_a_check():
    spec = compile_statement("# T\n\n```\nSELECT id FROM orders WHERE total > 0;\n```\n")
    assert spec.checks == []


# ---------------------------------------------------------------- extras


def test_X1_H_GIT_04_commit_in_shell_does_not_erase_diff(make_repo):
    repo = make_repo({"m.py": M})
    write(repo.root, "m.py", M.replace("def f():\n    return 1", "def f():\n    return 2"))
    repo.git("-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qam", "oops", "--no-gpg-sign")
    assert "+    return 2" in repo.diff()


def test_X2_H_TOOL_09_sql_commit_is_refused(tmp_path):
    from quarry.proc import ProcessRunner
    from quarry.profile import DbTarget
    from quarry.tools import ToolContext, ToolRegistry, default_tools

    ctx = ToolContext(str(tmp_path), compile_statement("# T"), ProcessRunner(str(tmp_path)), str(tmp_path / "s"),
                      [DbTarget("postgresql", "127.0.0.1", 1, "u", "p", "d")])
    out = ToolRegistry(default_tools()).dispatch(ctx, "sql", {"query": "DELETE FROM t; COMMIT; SELECT 1"})
    assert out.startswith("refused"), out


def test_X3_H_TOOL_10_process_output_memory_is_bounded(tmp_path):
    from quarry.proc import ProcessRunner

    result = ProcessRunner(str(tmp_path)).run("head -c 50000000 /dev/zero | tr '\\0' 'x'", timeout=60)
    assert len(result.output) < 2_000_000


def test_X4_H_SHELL_09_no_checks_is_not_check_evidence(make_repo, tmp_path):
    from quarry.shell import Workflow

    repo = make_repo({"m.py": M})
    wf = Workflow("# T\n\nOnly edit `m.py`.\n", repo.root, env(tmp_path), Scripted([]), Settings())
    wf.prepare()
    write(repo.root, "m.py", M.replace("return 1", "return 5", 1))
    from quarry.proc import ProcessRunner
    from quarry.tools import ToolContext

    ctx = ToolContext(repo.root, wf.spec, ProcessRunner(repo.root), str(tmp_path / "s"))
    _report, _failures, checks_ok = wf.gate(ctx)
    assert checks_ok is not True, "no checks ran, so there is no check evidence"


def test_X5_H_SHELL_10_earlier_eligible_candidate_beats_later_failure(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    statement = "# Fix f\n\nChange only `f()` in `m.py`. Do not use loops.\n\n```bash\ntest -f never-present\n```\n"
    good = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
    loop = [("edit", {"path": "m.py", "old": "def f():\n    return 2", "new": "def f():\n    for _ in []:\n        pass\n    return 2"})]
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([good, [("finish", {"summary": "v1"})], loop]), Settings())
    assert "+    return 2" in patch and "for _ in []" not in patch
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo.root, capture_output=True, text=True).stdout == ""


def test_X5_H_SHELL_10_last_resort_is_labelled(make_repo, tmp_path, capsys):
    repo = make_repo({"m.py": M})
    statement = "# Fix f\n\nChange only `f()` in `m.py`. Do not use loops.\n"
    loop = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    for _ in []:\n        pass\n    return 1"})]
    settings = Settings()
    settings.fix_rounds = 0
    patch = run_agent(statement, repo.root, env(tmp_path), Scripted([loop]), settings)
    assert "for _ in []" in patch
    assert "last-resort" in capsys.readouterr().err
    assert subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo.root, text=True).returncode == 0


def test_R2_H_LOOP_05_tool_batch_stops_at_phase_deadline(tmp_path):
    from quarry.clock import Clock
    from quarry.loop import DriverLoop
    from quarry.proc import ProcessRunner
    from quarry.tools import ToolContext, ToolRegistry, default_tools

    now = [0.0]
    clock = Clock(1000, lambda: now[0])
    timer = clock.slice(1.0)
    timer.end = 10.0

    class Tick:
        name = "tick"
        description = "advance time"
        parameters = {"type": "object", "properties": {}}

        def schema(self):
            return {"type": "function", "function": {"name": self.name, "description": "", "parameters": self.parameters}}

        def run(self, ctx, args):
            now[0] += 6
            return "ticked"

    ctx = ToolContext(str(tmp_path), compile_statement("# T"), ProcessRunner(str(tmp_path)), str(tmp_path / "s"))
    loop = DriverLoop(Scripted([[("tick", {}), ("tick", {}), ("tick", {})]]), ModelRoute("m"),
                      ToolRegistry(default_tools() + [Tick()]), ctx, timer)
    messages = []
    outcome = loop.run(messages)
    outputs = [m["content"] for m in messages if m["role"] == "tool"]
    assert outputs == ["ticked", "ticked", "skipped: the time for this phase is over"]
    assert outcome.reason == "deadline"
