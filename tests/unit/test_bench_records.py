"""B-RUN-04 (provenance at execution time) and B-RUN-02 (observations, validity, automatic labels)."""

import json
import os

from tests.conftest import write
from tools.bench_records import auto_label, expected_tasks, observe, task_digest, validity


def tree(tmp_path, name="t"):
    root = str(tmp_path / name)
    write(root, "task.toml", "x = 1\n")
    write(root, "instruction.md", "# T\n")
    write(root, "tests/verify.py", "print(1)\n")
    write(root, "environment/app/m.py", "A = 1\n")
    return root


def test_B_RUN_04_digest_covers_every_input_and_is_order_invariant(tmp_path):
    root = tree(tmp_path)
    base = task_digest(root)
    assert base.startswith("task-tree-v1:")
    assert task_digest(tree(tmp_path, "copy")) == base  # same content elsewhere, different walk order irrelevant
    for rel, text in (("tests/verify.py", "print(2)\n"), ("environment/app/m.py", "A = 2\n")):
        path = os.path.join(root, rel)
        old = open(path).read()
        write(root, rel, text)
        assert task_digest(root) != base, rel  # checker and app source are part of the identity
        write(root, rel, old)
    assert task_digest(root) == base
    os.chmod(os.path.join(root, "tests/verify.py"), 0o755)
    assert task_digest(root) != base  # mode-only change
    os.chmod(os.path.join(root, "tests/verify.py"), 0o644)
    os.makedirs(os.path.join(root, "tests/empty"))
    assert task_digest(root) != base  # directory entries count
    os.rmdir(os.path.join(root, "tests/empty"))
    os.symlink("verify.py", os.path.join(root, "tests/link"))
    with_link = task_digest(root)
    os.remove(os.path.join(root, "tests/link"))
    os.symlink("m.py", os.path.join(root, "tests/link"))
    assert task_digest(root) != with_link  # symlink target, not followed
    os.remove(os.path.join(root, "tests/link"))
    write(root, "tests/__pycache__/x.pyc", "junk")
    write(root, ".pytest_cache/v", "junk")
    assert task_digest(root) == base  # documented cache exclusions


def test_B_RUN_04_expected_task_list(tmp_path):
    for name in ("b-task", "a-task"):
        write(str(tmp_path), f"bench/tasks/dev/{name}/task.toml", "")
    assert expected_tasks(str(tmp_path), "dev") == ["a-task", "b-task"]


def trial(tmp_path, exception=None, reward=None, patch="diff --git a/m b/m\n", apply_rc=0):
    root = str(tmp_path / "trial")
    write(root, "result.json", json.dumps({"exception_info": {"exception_type": exception, "exception_message": "m"}}
                                          if exception else {}))
    if reward is not None:
        write(root, "verifier/reward.txt", f"{int(reward)}\n")
    if patch:
        write(root, "agent/patch.diff", patch)
    write(root, "agent/git-apply-check.log", f"$ git apply --check\n[return_code] {apply_rc}\n")
    cli = f"SUCCEEDED\nreward: {reward}\n" if reward is not None else "FAILED: X\n"
    return root, cli


def telemetry(final=None, loop="finished"):
    return {"version": 1, "final": final or {}, "rounds": [{"loop": loop}], "cost": {"accounting_complete": True}}


def label(tmp_path, **kw):
    tele = kw.pop("tele", telemetry({"source": "candidate", "eligible": True, "problems": []}))
    root, cli = trial(tmp_path, **kw)
    obs = observe(root, cli, tele)
    return obs, validity(obs), auto_label(obs)


def test_B_RUN_02_observations_are_recorded_separately(tmp_path):
    obs, state, lab = label(tmp_path, reward=1)
    assert obs["checker_completed"] and obs["apply_check_ok"] and obs["patch_sha256"] and obs["reward"] == 1.0
    assert obs["final_eligible"] is True and obs["termination"] == "finished" and obs["accounting_complete"] is True
    assert (state, lab) == ("valid", "solved")


def test_B_RUN_02_labels_follow_precedence(tmp_path):
    assert label(tmp_path / "a", reward=0)[2] == "unsolved"
    assert label(tmp_path / "b", exception="EnvironmentStartTimeoutError")[1:] == ("void-infrastructure", "infrastructure-void")
    assert label(tmp_path / "c", exception="VerifierTimeoutError")[1:] == ("unresolved", "unknown")
    assert label(tmp_path / "d", exception="MinerInvalidPatchError")[1:] == ("valid", "mechanical")
    assert label(tmp_path / "e", exception="MinerRuntimeError", reward=1)[2] == "unknown"  # contradictory
    guard = telemetry({"source": "candidate", "eligible": False, "problems": ["scope: changes outside scope"]})
    assert label(tmp_path / "f", reward=0, tele=guard)[2] == "guard-failed"
    checks = telemetry({"source": "candidate", "eligible": False, "problems": ["`pytest -q` exited 1:"]})
    assert label(tmp_path / "g", reward=0, tele=checks)[2] == "checks-failed"
    assert label(tmp_path / "h", tele=None)[2] == "unknown"  # no reward, no exception: insufficient evidence


def test_B_RUN_02_voluntary_no_patch_is_not_a_transport_failure(tmp_path):
    no_candidate = telemetry({}, loop="budget")
    obs, state, lab = label(tmp_path / "a", exception="MinerRuntimeError", patch="", tele=no_candidate)
    assert (state, lab) == ("valid", "budget")
    obs, state, lab = label(tmp_path / "b", exception="MinerRuntimeError", tele=telemetry({"source": "candidate"}))
    assert lab == "mechanical"  # a patch existed: this is a real mechanical failure


def test_B_RUN_02_broken_task_image_is_a_task_defect_not_agent_or_transient(tmp_path):
    root, cli = trial(tmp_path, exception="RuntimeError")
    obs = observe(root, cli, None)
    obs["exception_message"] = "Unsupported task environment: python3 is required to run the Ridges miner runtime"
    assert (validity(obs), auto_label(obs)) == ("task-environment", "task-environment-defect")
