"""Baseline check run, check timeouts and check observations (H-SHELL-11..13), found by the 2026-09-29 smoke test."""

import json

from quarry.shell import Settings, Workflow, run_agent
from quarry.telemetry import parse_log
from tests.scenario.test_review_2026_09_29 import M, Scripted, env

EDIT = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]


def statement(check):
    return f"# Fix f\n\nOnly edit `m.py`.\n\n```bash\n{check}\n```\n"


def workflow(repo, tmp_path, check, **overrides):
    settings = Settings()
    settings.fix_rounds = 0
    for key, value in overrides.items():
        setattr(settings, key, value)
    return Workflow(statement(check), repo.root, env(tmp_path), Scripted([EDIT]), settings)


def test_H_SHELL_11_baseline_runs_before_any_edit_and_records_duration(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = workflow(repo, tmp_path, "grep -q 'def f' m.py && sleep 1")
    wf.run()
    base = wf.baseline["grep -q 'def f' m.py && sleep 1"]
    assert base["ok"] and not base["timed_out"] and 0.9 <= base["seconds"] < 10
    assert wf.check_log[0]["round"] == "baseline"
    assert "passed in" in wf.messages()[1]["content"]


def test_H_SHELL_11_baseline_side_effects_are_undone_before_editing(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = workflow(repo, tmp_path, "echo junk >> m.py; true")
    wf.prepare()
    wf.baseline_checks()
    assert repo.changed().all_paths() == []


def test_H_SHELL_12_timeout_derived_from_baseline(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    # fast at baseline, slow after the edit: 3x baseline (min 1 s here) must cut it off
    check = "if grep -q 'return 2' m.py; then sleep 8; fi"
    wf = workflow(repo, tmp_path, check, check_min_sec=1.0)
    wf.run()
    later = [c for c in wf.check_log if c["round"] != "baseline"]
    assert later and later[0]["timed_out"] and later[0]["seconds"] < 6
    assert wf.store.best().checks_passed is False


def test_H_SHELL_12_baseline_timeout_makes_later_runs_unknown_not_failed(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = workflow(repo, tmp_path, "sleep 5", baseline_min_sec=1.0, baseline_share=0.0)
    wf.run()
    assert wf.baseline["sleep 5"]["timed_out"]
    assert any(c.get("skipped") for c in wf.check_log)
    assert "do not run it yourself" in wf.messages()[1]["content"]
    best = wf.store.best()
    assert best.checks_passed is None and best.eligible


def test_H_SHELL_12_check_failing_before_any_change_is_not_evidence(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = workflow(repo, tmp_path, "false")
    wf.run()
    assert not wf.baseline["false"]["ok"]
    best = wf.store.best()
    assert best.checks_passed is None and best.eligible


def test_H_SHELL_13_check_observations_reach_log_and_telemetry(make_repo, tmp_path, capsys):
    repo = make_repo({"m.py": M})
    check = "python -c 'import m; assert m.f() == 1, \"expected 1\"'"
    settings = Settings()
    settings.fix_rounds = 0
    run_agent(statement(check), repo.root, env(tmp_path), Scripted([EDIT]), settings)
    err = capsys.readouterr().err
    assert "check [baseline]" in err and "check [r0]" in err and "AssertionError: expected 1" in err
    record = parse_log(err)
    assert record["baseline_checks"][0]["ok"] is True
    runs = [c for c in record["checks"] if c["round"] == "r0"]
    assert runs[0]["exit"] == 1 and "AssertionError" in runs[0]["tail"] and "seconds" in runs[0]
    assert record["rounds"][0]["checks"] is False and record["rounds"][0]["guard_eligible"] is True
    assert record["final"]["eligible"] is False and record["final"]["returned_option"] == 0
    json.dumps(record)  # the whole record stays serialisable


class Recording(Scripted):
    def complete(self, messages, *args, **kwargs):
        self.seen = getattr(self, "seen", []) + [list(messages)]
        return super().complete(messages, *args, **kwargs)


EDIT_TO_3 = [("edit", {"path": "m.py", "old": "def f():\n    return 2", "new": "def f():\n    return 3"})]
WANTS_3 = "python -c 'import m; assert m.f() == 3, \"want 3\"'"


def test_H_SHELL_14_check_failing_before_and_after_gets_another_round(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    settings = Settings()
    settings.fix_rounds = 2
    client = Recording([EDIT, [("finish", {"summary": "done"})], EDIT_TO_3])
    wf = Workflow(statement(WANTS_3), repo.root, env(tmp_path), client, settings)
    wf.run()
    assert not wf.baseline[WANTS_3]["ok"]
    assert [r["checks"] for r in wf.rounds] == [None, True]
    feedback = [m["content"] for m in client.seen[-1] if m["role"] == "user"][-1]
    assert "failed before any change" in feedback and "want 3" in feedback
    assert wf.store.best().checks_passed is True


def test_H_SHELL_14_rounds_stop_when_none_remain(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    settings = Settings()
    settings.fix_rounds = 1
    wf = Workflow(statement("false"), repo.root, env(tmp_path), Scripted([EDIT]), settings)
    wf.run()
    assert len(wf.rounds) == 2 and all(r["checks"] is None for r in wf.rounds)
    best = wf.store.best()
    assert best.checks_passed is None and best.eligible
