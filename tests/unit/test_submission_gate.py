"""B-RUN-05: the submission gate G7 checks the declared held-out target on the exact file to be uploaded."""

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tools.submission_gate import evaluate
from tools.submission_preflight import preflight

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


@pytest.mark.parametrize('cost', ['nan', 'inf', '-1', ''])
def test_B_RUN_05_nonfinite_negative_or_missing_cost_blocks_upload(tmp_path, cost):
    assert 'cost per trial' in failed(evaluate(*setup(tmp_path, cost=cost))[0])


def test_B_RUN_05_mismatched_provider_and_key_usage_blocks_upload(tmp_path):
    agent, run, refs = setup(tmp_path)
    path = Path(run) / 'results.csv'
    rows = list(csv.DictReader(path.open()))
    for row in rows:
        row.update(cost_provider='0.001', accounting_complete='True', estimated_calls='0', unknown_attempts='0')
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert 'cost per trial' in failed(evaluate(agent, run, refs)[0])


def test_B_RUN_05_upload_preflight_checks_release_bytes_and_evidence(tmp_path):
    agent, run, refs = setup(tmp_path)
    folder = Path(agent).parent
    evidence = folder / 'evidence' / 'heldout'
    evidence.mkdir(parents=True)
    hashes = {}
    for name in ('manifest.json', 'results.csv'):
        data = (Path(run) / name).read_bytes()
        (evidence / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = {'status': 'ready', 'competition_set_id': 28, 'sha256': hashlib.sha256(Path(agent).read_bytes()).hexdigest(),
                'evidence_sha256': hashes}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    assert preflight(folder, refs) == agent
    Path(agent).write_text(AGENT + '# changed\n')
    with pytest.raises(ValueError, match='checksum'):
        preflight(folder, refs)
    Path(agent).write_text(AGENT)
    (evidence / 'results.csv').write_text('changed')
    with pytest.raises(ValueError, match='evidence checksum'):
        preflight(folder, refs)


def test_B_RUN_05_shell_preflight_rejects_legacy_file_override_without_uploader(tmp_path):
    import os

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['bash', str(root / 'tools/ridges_submit.sh'), 'preflight'],
                            env=dict(os.environ, RIDGES_AGENT_FILE=str(tmp_path / 'agent.py')),
                            capture_output=True, text=True)
    assert result.returncode != 0 and 'RIDGES_SUBMISSION_DIR' in result.stderr


@pytest.mark.parametrize('action', ['upload', 'resume', 'fund', 'register'])
def test_B_RUN_05_paid_steps_require_explicit_wallet_after_possible_migration(action):
    import os

    root = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if k != 'RIDGES_WALLET_NAME'}
    result = subprocess.run(['bash', str(root / 'tools/ridges_submit.sh'), action],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'RIDGES_WALLET_NAME' in result.stderr


def test_B_RUN_05_local_model_override_does_not_qualify_default_upload(tmp_path):
    agent, run, refs = setup(tmp_path)
    path = Path(run) / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['model_override'] = {'QUARRY_DRIVER_MODEL': 'other'}
    path.write_text(json.dumps(manifest))
    assert 'production model routing' in failed(evaluate(agent, run, refs)[0])
