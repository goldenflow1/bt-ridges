"""B-RUN-01 (runtime identity, input mutation), B-RUN-02 (replacement cap) and B-RUN-03 (aggregation, promotion,
comparison under the W6 confirmation protocol)."""

import csv
import json
import os
import time

import pytest

from tools.bench_records import ImageWatcher, host_identity, inputs_unchanged, trial_images
from tools.bench_summary import SummaryError, compare, load_run, promote, promotion_problems, summarize
from tools.run_bench import run_slot

TASKS = {"a": "task-tree-v1:aaa", "b": "task-tree-v1:bbb"}
HOST = {"ridges_cli_commit": "d74410d8484f", "harbor": "0.20.0", "cpu": "x", "cpus": 8, "docker": "29"}


def make_run(root, name, results, purpose="evaluation", agent="agent1", tasks=None, host=None):
    """results: {task: [reward, ...]} (None = void attempt replaced by the next value)."""
    path = os.path.join(str(root), name)
    os.makedirs(path)
    manifest = {"set": "dev", "agent_sha256": agent, "model_override": {}, "tasks": tasks or TASKS,
                "expected_tasks": sorted(tasks or TASKS), "purpose": purpose, "host": host or HOST}
    with open(os.path.join(path, "manifest.json"), "w") as handle:
        json.dump(manifest, handle)
    rows = []
    for task, rewards in results.items():
        repeat = 0
        attempt = 1
        for reward in rewards:
            if attempt == 1:
                repeat += 1
            void = reward is None
            rows.append({"trial_id": f"{name}/{task}/r{repeat}/a{attempt}", "purpose": purpose, "slot": f"{name}/{task}/r{repeat}",
                         "task": task, "reward": "" if void else str(reward), "reconciled_cost": "0.01",
                         "validity": "void-infrastructure" if void else "valid",
                         "auto_label": "infrastructure-void" if void else ("solved" if reward else "unsolved"),
                         "inputs_changed": "", "images": '{"env-main:latest": "sha256:1"}'})
            attempt = attempt + 1 if void else 1
    with open(os.path.join(path, "results.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------- B-RUN-01


def test_B_RUN_01_runtime_identity_and_input_mutation(tmp_path):
    fake = {
        ("docker", "version"): "29.8.1",
        ("docker", "images"): "task-x__abc12__env-main:latest sha256:111\ntask-x__abc12__env-postgres:latest sha256:222\n"
                              "other__zz__env-main:latest sha256:333",
    }

    def run(cmd):
        return next((v for k, v in fake.items() if tuple(cmd[:2]) == k), "")

    ident = host_identity(str(tmp_path), run)
    assert ident["docker"] == "29.8.1" and ident["harbor"] is None and ident["cpus"]
    images = trial_images("/runs/task-x__ABC12/", run)
    assert images == {"env-main:latest": "sha256:111", "env-postgres:latest": "sha256:222"}
    assert inputs_unchanged({"t": "d1", "bundle": "b1"}, {"t": "d1", "bundle": "b1"}) == []
    assert inputs_unchanged({"t": "d1", "bundle": "b1"}, {"t": "d2", "bundle": "b1"}) == ["t"]


def test_B_RUN_01_images_are_captured_while_the_trial_runs_before_harbor_removes_them():
    # Harbor names images <task id[:32]>__<trial>__<service> and deletes them at the end of the trial
    # (compose down --rmi local); a stale image of an earlier trial must not be attributed to this one.
    stale = "a-very-long-task-name-for-images__old1234__env-main:latest sha256:000"
    state = {"listing": stale}

    def run(cmd):
        return state["listing"]

    with ImageWatcher("a-very-long-task-name-for-images-001", run, interval=0.01) as watcher:
        state["listing"] = stale + "\na-very-long-task-name-for-images__new5678__env-main:latest sha256:111"
        time.sleep(0.1)
        state["listing"] = stale  # removed before the trial returns
    images = trial_images("/runs/x/a-very-long-task-name-for-images__NEW5678/", seen=watcher.seen)
    assert images == {"env-main:latest": "sha256:111"}


def test_B_RUN_01_watcher_prefix_matches_harbor_trial_names_cut_on_a_dash():
    # Harbor: task_name[:32].rstrip("_-"); a 32nd character "-" is dropped (pg-netbox-vlangroup-utilization-001)
    watcher = ImageWatcher("pg-netbox-vlangroup-utilization-001", lambda cmd: "")
    assert watcher.prefix == "pg-netbox-vlangroup-utilization__"


# ---------------------------------------------------------------- B-RUN-02 (replacement cap)


def test_B_RUN_02_slot_replaces_only_void_attempts_up_to_the_cap():
    outcomes = iter(["void-infrastructure", "valid"])
    rows, blocked, stop = run_slot(lambda a: {"attempt": a, "validity": next(outcomes)}, lambda: True)
    assert [r["attempt"] for r in rows] == [1, 2] and not blocked and not stop
    rows, blocked, _ = run_slot(lambda a: {"attempt": a, "validity": "void-infrastructure"}, lambda: True)
    assert len(rows) == 3 and blocked  # first attempt + 2 replacements, then infrastructure-blocked
    rows, blocked, _ = run_slot(lambda a: {"attempt": a, "validity": "valid"}, lambda: True)
    assert len(rows) == 1  # a valid failure is never replaced
    rows, blocked, stop = run_slot(lambda a: {"attempt": a, "validity": "void-infrastructure"}, lambda: False)
    assert len(rows) == 1 and "ceiling" in stop


# ---------------------------------------------------------------- B-RUN-03


def test_B_RUN_03_equal_task_weight_and_void_attempts_leave_the_denominator(tmp_path):
    run = load_run(make_run(tmp_path, "r1", {"a": [1, 1, 1, 1, 1], "b": [None, 0, 1, 0]}))
    summary = summarize([run])
    assert summary["per_task"]["a"]["solve_fraction"] == 1.0
    assert summary["per_task"]["b"]["valid_trials"] == 3 and summary["per_task"]["b"]["void_attempts"] == 1
    assert summary["mean_solve"] == pytest.approx((1.0 + 1 / 3) / 2)  # not 6/8 weighted by attempts
    assert summary["complete"]


def test_B_RUN_03_incompatible_cohorts_and_duplicate_conflicts_are_errors(tmp_path):
    one = load_run(make_run(tmp_path, "r1", {"a": [1, 1, 1], "b": [1, 1, 1]}))
    other_tasks = load_run(make_run(tmp_path, "r2", {"a": [1], "b": [1]}, tasks={"a": "task-tree-v1:CHANGED", "b": TASKS["b"]}))
    with pytest.raises(SummaryError, match="cohorts"):
        summarize([one, other_tasks])
    twin = load_run(make_run(tmp_path, "twin", {"a": [0, 1, 1], "b": [1, 1, 1]}))
    twin["rows"][0]["trial_id"] = one["rows"][0]["trial_id"]
    with pytest.raises(SummaryError, match="conflicting"):
        summarize([one, twin])


def test_B_RUN_03_promotion_conditions_and_immutability(tmp_path):
    recon = load_run(make_run(tmp_path, "recon", {"a": [1, 1, 1], "b": [1, 1, 1]}, purpose="reconnaissance"))
    assert any("evaluation" in p for p in promotion_problems([recon]))
    short = load_run(make_run(tmp_path, "short", {"a": [1, 1], "b": [1, 1, 1]}))
    assert any("a: 2 valid trials" in p for p in promotion_problems([short]))
    good = load_run(make_run(tmp_path, "good", {"a": [1, 1, 1], "b": [None, 1, 0, 1]}))
    out = str(tmp_path / "baseline.json")
    promote([good], out)
    assert not os.access(out, os.W_OK) or oct(os.stat(out).st_mode)[-3:] == "444"
    with pytest.raises(SummaryError, match="never overwritten"):
        promote([good], out)
    failed_out = str(tmp_path / "never.json")
    with pytest.raises(SummaryError):
        promote([short], failed_out)
    assert not os.path.exists(failed_out)  # a failed promotion writes nothing


def baseline_for(tmp_path, results):
    out = str(tmp_path / "base.json")
    promote([load_run(make_run(tmp_path, "base", results))], out)
    return json.load(open(out))


def test_B_RUN_03_compare_applies_the_w6_protocol(tmp_path):
    base = baseline_for(tmp_path, {"a": [1, 1, 1], "b": [0, 0, 0]})
    gain = load_run(make_run(tmp_path, "gain", {"a": [1, 1, 1], "b": [1, 1, 1]}, agent="agent2"))
    assert compare(base, [gain])["decision"] == "keep"
    material = load_run(make_run(tmp_path, "mat", {"a": [1, 0, 0], "b": [1, 1, 1]}, agent="agent2"))
    assert compare(base, [material])["decision"] == "revert"  # 3/3 → 1/3 blocks even with a gain elsewhere
    small = load_run(make_run(tmp_path, "small", {"a": [1, 1, 0], "b": [1, 1, 1]}, agent="agent2"))
    pending = compare(base, [small])
    assert pending["decision"] == "pending" and pending["needs_confirmation"] == ["a"]
    cb = load_run(make_run(tmp_path, "cb", {"a": [1, 1, 1]}, purpose="confirmation",
                           tasks={"a": TASKS["a"]}))
    cc_ok = load_run(make_run(tmp_path, "cc_ok", {"a": [1, 1, 1]}, purpose="confirmation", agent="agent2",
                              tasks={"a": TASKS["a"]}))
    assert compare(base, [small], [cb], [cc_ok])["decision"] == "keep"  # drop not reproduced, gain on b
    cc_bad = load_run(make_run(tmp_path, "cc_bad", {"a": [1, 0, 1]}, purpose="confirmation", agent="agent2",
                               tasks={"a": TASKS["a"]}))
    assert compare(base, [small], [cb], [cc_bad])["decision"] == "revert"  # drop persists


def test_B_RUN_03_compare_rejects_changed_task_versions_or_runtime(tmp_path):
    base = baseline_for(tmp_path, {"a": [1, 1, 1], "b": [1, 1, 1]})
    changed = load_run(make_run(tmp_path, "c", {"a": [1, 1, 1], "b": [1, 1, 1]}, agent="agent2",
                                tasks={"a": "task-tree-v1:NEW", "b": TASKS["b"]}))
    assert compare(base, [changed])["decision"] == "incompatible"
    runtime = load_run(make_run(tmp_path, "rt", {"a": [1, 1, 1], "b": [1, 1, 1]}, agent="agent2",
                                host=dict(HOST, harbor="0.21.0")))
    assert compare(base, [runtime])["decision"] == "incompatible"
