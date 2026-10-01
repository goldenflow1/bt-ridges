"""B-RUN-05: the submission gate G7 checks the declared held-out target on the exact file to be uploaded."""

import csv
import hashlib
import json

from tools.submission_gate import evaluate

AGENT = "def agent_main(inputs):\n    return {'patch': ''}\n"
REFERENCE = "import os\n\n\ndef run_everything_differently(task):\n    return os.listdir(task)\n"


def setup(tmp_path, rewards=(1, 1, 0), cost="0.01", label=None, trials=3, agent=AGENT, purpose="evaluation"):
    sub = tmp_path / "submissions" / "v001"
    sub.mkdir(parents=True)
    (sub / "agent.py").write_text(agent)
    digest = hashlib.sha256(AGENT.encode()).hexdigest()
    refs = tmp_path / "refs" / "other"
    refs.mkdir(parents=True)
    (refs / "agent.py").write_text(REFERENCE)
    run = tmp_path / "run"
    run.mkdir()
    tasks = ["a", "b", "c"]
    (run / "manifest.json").write_text(json.dumps({
        "set": "heldout", "agent_sha256": digest, "model_override": {}, "tasks": {t: "d" for t in tasks},
        "expected_tasks": tasks, "purpose": purpose, "host": {}}))
    rows = []
    for t_index, task in enumerate(tasks):
        for repeat in range(1, trials + 1):
            reward = rewards[(t_index + repeat) % len(rewards)]
            rows.append({"trial_id": f"{task}/r{repeat}/a1", "slot": f"{task}/r{repeat}", "purpose": purpose,
                         "task": task, "reward": str(reward), "reconciled_cost": cost, "validity": "valid",
                         "auto_label": label or ("solved" if reward else "unsolved"), "bundle_sha256": digest[:16],
                         "wall_sec": "100", "images": '{"env-main:latest": "sha256:1"}'})
    with open(run / "results.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return str(sub / "agent.py"), str(run), str(tmp_path / "refs")


def failed(results):
    return [name for name, passed, _ in results if not passed]


def test_B_RUN_05_gate_passes_when_every_declared_condition_holds(tmp_path):
    results, numbers = evaluate(*setup(tmp_path))
    assert failed(results) == []
    assert numbers["heldout_solved"] == 6 and numbers["heldout_trials"] == 9 and numbers["cost_usd"] == 0.01


def test_B_RUN_05_gate_rejects_a_file_other_than_the_measured_bundle(tmp_path):
    results, _ = evaluate(*setup(tmp_path, agent=AGENT + "# edited after the run\n"))
    assert failed(results) == ["bundle is the one measured"]


def test_B_RUN_05_gate_rejects_low_solve_rate_mechanical_failures_and_cost(tmp_path):
    assert "solve rate" in failed(evaluate(*setup(tmp_path / "solve", rewards=(0, 0, 1)))[0])
    assert "mechanical failures" in failed(evaluate(*setup(tmp_path / "mech", label="mechanical"))[0])
    assert "cost per trial" in failed(evaluate(*setup(tmp_path / "cost", cost="0.031"))[0])


def test_B_RUN_05_gate_requires_a_complete_three_trial_evaluation(tmp_path):
    assert "complete held-out evaluation" in failed(evaluate(*setup(tmp_path / "short", trials=2))[0])
    assert "complete held-out evaluation" in failed(evaluate(*setup(tmp_path / "diag", purpose="diagnostic"))[0])
