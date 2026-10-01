"""B-FAULT-01..03: the fault-injecting inference proxy (v004 C1) and its bench accounting, against a fake upstream
(no paid inference). Negative cases follow docs/reviews/2026-10-01-e016-readiness.md."""

import csv
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from quarry.llm import ModelRoute, ProxyClient, http_transport
from quarry.wallet import Wallet
from tools.bench_cost import proxy_summary, reconcile_proxy, trusted_cost
from tools.fault_proxy import FaultProxy, Rules, ScenarioError, load_scenario

OK = {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.002}}


class Upstream:
    """Fake provider: records requests (model, Authorization); answers with `self.reply` after `self.delay`."""

    def __init__(self):
        self.requests = []
        self.reply = (200, OK)
        self.delay = 0.0
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((body.get("model"), self.headers.get("Authorization")))
                time.sleep(outer.delay)
                status, payload = outer.reply
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/chat"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def upstream():
    u = Upstream()
    yield u
    u.close()


def post(port, model="primary", timeout=5.0):
    body = json.dumps({"model": model, "messages": []}).encode()
    return http_transport(f"http://127.0.0.1:{port}/api/v1/chat/completions", body, {"Content-Type": "application/json"}, timeout)


def records(path):
    return [json.loads(line) for line in open(path)]


def ends(path):
    return [r for r in records(path) if r.get("event") == "request_end"]


def proxy(scenario, upstream, log=None, **kw):
    return FaultProxy(scenario, host="127.0.0.1", upstream=upstream.url, key=kw.pop("key", "k"), log_path=log, **kw)


# ---------------------------------------------------------------- B-FAULT-01 forwarding, lifecycle, key


def test_B_FAULT_01_forwards_with_the_bench_key_and_logs_a_complete_lifecycle_without_it(upstream, tmp_path):
    log = str(tmp_path / "proxy.jsonl")
    with proxy({"name": "clean", "rules": []}, upstream, log, key="sk-secret") as p:
        status, text, _ = post(p.port)
        missing = http_transport(f"http://127.0.0.1:{p.port}/other", b"{}", {}, 5.0)
    assert status == 200 and json.loads(text) == OK and missing[0] == 404
    assert upstream.requests == [("primary", "Bearer sk-secret")]
    assert [r["event"] for r in records(log)] == ["proxy_start", "request_start", "request_end", "proxy_stop"]
    end = ends(log)[0]
    assert end["charge"] == "known" and end["real_cost"] == end["reported_cost"] == 0.002
    assert "sk-secret" not in open(log).read()
    summary = proxy_summary(log)
    assert summary["proxy_complete"] and summary["proxy_real_cost"] == 0.002


def test_B_FAULT_01_a_request_still_in_flight_at_shutdown_leaves_the_accounting_incomplete(upstream, tmp_path):
    log = str(tmp_path / "proxy.jsonl")
    upstream.delay = 1.0
    p = proxy({"name": "clean", "rules": []}, upstream, log, drain_sec=0.1)
    p.__enter__()
    worker = threading.Thread(target=lambda: post(p.port, timeout=5.0))
    worker.start()
    time.sleep(0.3)
    p.__exit__(None, None, None)
    worker.join()
    stop = [r for r in records(log) if r["event"] == "proxy_stop"][0]
    assert stop["outstanding"] == 1
    assert not proxy_summary(log)["proxy_complete"]


def test_B_FAULT_01_forward_errors_are_logged_as_uncertain_charges(tmp_path):
    log = str(tmp_path / "proxy.jsonl")
    with FaultProxy({"name": "clean", "rules": []}, host="127.0.0.1", upstream="http://127.0.0.1:9/none", key="k",
                    log_path=log) as p:
        status, _, _ = post(p.port)
    assert status == 502
    end = ends(log)[0]
    assert end["stage"] == "forward_error" and end["charge"] == "uncertain"
    assert not proxy_summary(log)["proxy_complete"]


def test_B_FAULT_01_charges_reported_on_error_responses_are_counted_and_unpriced_5xx_are_uncertain(upstream, tmp_path):
    billed = str(tmp_path / "billed.jsonl")
    upstream.reply = (503, {"error": {"code": 503}, "usage": {"cost": 0.003}})
    with proxy({"name": "clean", "rules": []}, upstream, billed) as p:
        post(p.port)
    assert proxy_summary(billed)["proxy_real_cost"] == 0.003 and proxy_summary(billed)["proxy_complete"]
    unpriced = str(tmp_path / "unpriced.jsonl")
    upstream.reply = (503, {"error": {"code": 503}})
    with proxy({"name": "clean", "rules": []}, upstream, unpriced) as p:
        post(p.port)
    assert proxy_summary(unpriced)["proxy_uncertain"] == 1 and not proxy_summary(unpriced)["proxy_complete"]


def test_B_FAULT_01_a_missing_log_is_missing_evidence_not_zero_cost(tmp_path):
    summary = proxy_summary(str(tmp_path / "never-written.jsonl"))
    assert summary["proxy_log_present"] is False and summary["proxy_complete"] is False
    assert summary["proxy_real_cost"] is None
    assert reconcile_proxy(0.0, summary)["reconciled_cost"] is None


# ---------------------------------------------------------------- B-FAULT-02 scenarios


def test_B_FAULT_02_before_forward_faults_are_never_sent_upstream(upstream, tmp_path):
    scenario = {"name": "s", "rules": [
        {"action": "status", "status": 429, "until_request": 1, "headers": {"Retry-After": "3"}},
        {"action": "status", "status": 402, "from_request": 2, "until_request": 2, "message": "in_flight_budget_exhausted"},
        {"action": "malformed", "from_request": 3, "until_request": 3},
    ]}
    log = str(tmp_path / "proxy.jsonl")
    with proxy(scenario, upstream, log) as p:
        first, second, third, fourth = (post(p.port) for _ in range(4))
    assert first[0] == 429 and first[2]["retry-after"] == "3"
    assert second[0] == 402 and "in_flight" in second[1]
    assert third[0] == 200 and json.loads(third[1])["choices"] == "not a list"
    assert fourth[0] == 200 and len(upstream.requests) == 1
    assert [(e["stage"], e["charge"]) for e in ends(log)] == [("before", "none")] * 3 + [(None, "known")]


def test_B_FAULT_02_after_forward_faults_are_forwarded_and_logged_as_possibly_billed(upstream, tmp_path):
    scenario = {"name": "s", "rules": [{"action": "drop", "until_request": 1}, {"action": "cost_multiplier", "factor": 10}]}
    log = str(tmp_path / "proxy.jsonl")
    with proxy(scenario, upstream, log) as p:
        with pytest.raises(OSError):
            post(p.port)
        status, text, _ = post(p.port)
    assert len(upstream.requests) == 2
    assert status == 200 and json.loads(text)["usage"]["cost"] == pytest.approx(0.02)
    dropped, multiplied = ends(log)
    assert dropped["stage"] == "after" and dropped["charge"] == "known" and dropped["real_cost"] == 0.002
    assert multiplied["scaled"] is True and multiplied["reported_cost"] == pytest.approx(0.02)
    summary = proxy_summary(log)
    assert summary["proxy_real_cost"] == 0.004 and summary["proxy_reported_cost"] == pytest.approx(0.02)


def test_B_FAULT_02_responses_the_multiplier_cannot_scale_are_counted(upstream, tmp_path):
    upstream.reply = (200, {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3}})
    log = str(tmp_path / "proxy.jsonl")
    with proxy({"name": "x", "rules": [{"action": "cost_multiplier", "factor": 15}]}, upstream, log) as p:
        post(p.port)
    end = ends(log)[0]
    assert end["scaled"] is False and end["charge"] == "uncertain"
    summary = proxy_summary(log)
    assert summary["proxy_unscaled"] == 1 and not summary["proxy_complete"]


def test_B_FAULT_02_schedules_are_deterministic_for_a_seed():
    scenario = load_scenario({"name": "p", "seed": 11, "rules": [{"action": "status", "status": 503, "probability": 0.3}]})
    runs = []
    for _ in range(2):
        rules = Rules(scenario)
        runs.append([rules.next("m")[1] is not None for _ in range(50)])
    assert runs[0] == runs[1] and 5 < sum(runs[0]) < 25


def test_B_FAULT_02_rules_match_by_model_window_and_period():
    rules = Rules(load_scenario({"name": "w", "rules": [
        {"action": "status", "status": 503, "model": "primary", "from_request": 2, "until_request": 6, "every": 2}]}))
    hits = [rules.next(model)[1] is not None for model in ["primary"] * 7 + ["fallback"]]
    assert hits == [False, True, False, True, False, True, False, False]


@pytest.mark.parametrize("bad", [
    {"rules": []},
    {"name": "x", "rules": [{"action": "explode"}]},
    {"name": "x", "rules": [{"action": "status"}]},
    {"name": "x", "rules": [{"action": "cost_multiplier"}]},
    {"name": "x", "rules": [{"action": "cost_multiplier", "factor": float("inf")}]},
    {"name": "x", "rules": [{"action": "cost_multiplier", "factor": True}]},
    {"name": "x", "rules": [{"action": "cost_multiplier", "factor": "10"}]},
    {"name": "x", "rules": [{"action": "cost_multiplier", "factor": -2}]},
])
def test_B_FAULT_02_invalid_scenarios_are_rejected(bad):
    with pytest.raises(ScenarioError):
        load_scenario(bad)


def test_B_FAULT_02_slow_body_is_cut_off_by_the_agent_transport(upstream):
    with proxy({"name": "slow", "rules": [{"action": "slow_body", "seconds": 5}]}, upstream) as p:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            post(p.port, timeout=0.4)
        assert time.monotonic() - started < 1.5


def test_B_FAULT_02_quarry_client_recovers_through_the_proxy(upstream):
    scenario = {"name": "burst", "rules": [{"action": "status", "status": 503, "model": "primary", "until_request": 2}]}
    with proxy(scenario, upstream) as p:
        now = [1000.0]
        client = ProxyClient(Wallet(1.0, {"primary": (0.2, 1.2), "fallback": (0.48, 4.2)}),
                             {"SANDBOX_PROXY_URL": f"http://127.0.0.1:{p.port}"},
                             sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        route = ModelRoute("primary", "fallback")
        client.complete([{"role": "user", "content": "hi"}], route)
        now[0] += 61
        client.complete([{"role": "user", "content": "hi"}], route)
    assert [m for m, _ in upstream.requests] == ["fallback", "primary"]


# ---------------------------------------------------------------- B-FAULT-03 bench accounting and comparison


def fault_row(cost, real, complete=True):
    return {"reconciled_cost": str(cost), "cost_reconciliation": "matched-proxy", "proxy_real_cost": str(real),
            "proxy_complete": str(complete), "cost_provider": str(real * 15)}   # agent saw the multiplied cost


def test_B_FAULT_03_trusted_cost_validates_proxy_evidence_instead_of_the_altered_agent_cost():
    assert trusted_cost(fault_row(0.002, 0.002)) == pytest.approx(0.002)
    assert trusted_cost(fault_row(0.002, 0.002, complete=False)) is None
    assert trusted_cost(fault_row(0.02, 0.002)) is None                      # key usage includes someone else
    assert trusted_cost({"reconciled_cost": "0.002", "cost_reconciliation": "matched-proxy"}) is None


def test_B_FAULT_03_fault_runs_aggregate_with_trusted_costs(tmp_path):
    from tools.bench_summary import load_run, summarize

    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(json.dumps({"set": "dev", "agent_sha256": "a", "tasks": {"t": "d"},
                                                   "expected_tasks": ["t"], "purpose": "diagnostic", "host": {},
                                                   "fault_scenario": {"name": "cost-x15", "sha256": "s"}}))
    rows = [dict(fault_row(0.002, 0.002), trial_id=f"t/r{i}", slot=f"t/r{i}", task="t", reward="1.0",
                 validity="valid", auto_label="solved") for i in (1, 2, 3)]
    with open(run / "results.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize([load_run(str(run))])
    assert summary["per_task"]["t"]["mean_cost"] == pytest.approx(0.002) and summary["per_task"]["t"]["cost_complete"]


def test_B_FAULT_03_fault_and_normal_conditions_are_never_compared_or_confirmed_together():
    from tools.bench_summary import cohort_key, compatibility_problems, confirmation_problems

    normal = {"set": "dev", "agent_sha256": "a", "tasks": {"t": "d"}, "host": {}}
    faulted = dict(normal, fault_scenario={"name": "cost-x15", "sha256": "s"})
    assert cohort_key(normal) != cohort_key(faulted)
    baseline = {"cohort": {"set": "dev", "tasks": {"t": "d"}, "runtime": [None, None],
                           "fault_scenario": faulted["fault_scenario"]}}
    assert any("fault scenario" in p for p in compatibility_problems(baseline, [{"dir": "c", "manifest": normal}]))
    assert not compatibility_problems(baseline, [{"dir": "c", "manifest": faulted}])
    identity = dict(baseline["cohort"], agent_sha256="a")
    run = {"dir": "c", "manifest": dict(normal, purpose="confirmation"), "rows": []}
    assert any("fault scenario" in p for p in confirmation_problems([run], identity, {"t": "d"}))


def test_B_FAULT_03_promoted_cohorts_keep_the_fault_scenario(tmp_path, monkeypatch):
    import tools.bench_summary as bs

    monkeypatch.setattr(bs, "promotion_problems", lambda runs: [])
    monkeypatch.setattr(bs, "summarize", lambda runs, purposes=None: {"set": "dev", "agent_sha256": "a"})
    run = {"dir": "r", "results_sha256": "x", "rows": [{"trial_id": "t1"}],
           "manifest": {"tasks": {"t": "d"}, "host": {}, "fault_scenario": {"name": "cost-x15", "sha256": "s"}}}
    record = bs.promote([run], str(tmp_path / "b.json"))
    assert record["cohort"]["fault_scenario"] == {"name": "cost-x15", "sha256": "s"}


def test_B_FAULT_03_ledger_holds_in_flight_reservations(tmp_path):
    from tools.run_bench import SessionLedger

    ledger = SessionLedger(str(tmp_path / "l.json"), 1.0, lambda: 0.0)
    ledger.reserve("t1", 0.6)
    assert not ledger.fits(0.5)                      # 0.6 still held although key usage shows nothing yet
    ledger.record("t1", 0.6, 0.01, 0.01)
    assert ledger.fits(0.5)
    reopened = SessionLedger(str(tmp_path / "l.json"), 1.0, lambda: 0.0)
    reopened.reserve("t2", 0.6)                       # a crash here leaves t2 pending: still held on restart
    assert not SessionLedger(str(tmp_path / "l.json"), 1.0, lambda: 0.0).fits(0.5)


def test_B_FAULT_03_results_csv_keeps_the_fault_and_pairing_columns(tmp_path):
    from tools.run_bench import save_results

    save_results(str(tmp_path), [{"trial_id": "t1", "fault_scenario": "cost-x15", "proxy_requests": 9,
                                  "proxy_real_cost": 0.004, "proxy_reported_cost": 0.06, "fin_notices": 1,
                                  "outcome_category": "patch", "arm": "B", "pair_id": "p/t/r1", "arm_position": 0}])
    row = next(csv.DictReader(open(tmp_path / "results.csv")))
    assert row["proxy_reported_cost"] == "0.06" and row["fin_notices"] == "1" and row["arm"] == "B"
    assert row["outcome_category"] == "patch" and row["pair_id"] == "p/t/r1"


def test_B_FAULT_03_outcomes_and_finalization_events_are_classified():
    from tools.bench_records import finalization_events, outcome_category

    log = ("[quarry] finalization notice at turn 9 (verify)\n[quarry] empty finish refused at turn 3\n"
           "[quarry] finalization round: no candidate after the driver (budget); $0.03 and 200s left\n")
    log += '[quarry] [quarry-telemetry] {"version": 1}\n'
    assert finalization_events(log) == {"fin_notices": 1, "fin_refusals": 1, "fin_empty_accepts": 0, "fin_rounds": 1,
                                        "fin_observed": True}
    assert outcome_category("", {}, "") == "not-started"
    assert outcome_category("d", {"exception_type": "AgentTimeoutError"}, log) == "harness-exception"
    assert outcome_category("d", {"patch_sha256": "abc"}, log) == "patch"
    assert outcome_category("d", {}, log) == "empty-output"
    assert outcome_category("d", {}, "") == "missing-evidence"


# ---------------------------------------------------------------- B-FAULT-03 runner wiring (stubbed trials)


def stub_bench(tmp_path, monkeypatch, argv, env_key, file_key, row_overrides=None, reconciliation=None,
               key_remaining=None):
    """Run tools.run_bench with every external effect stubbed; return (captured FaultProxy keys, run order, dirs).
    `row_overrides(n)` adjusts the n-th trial's row; `reconciliation(n)` replaces the proxy reconciliation."""
    import tools.run_bench as rb

    root = tmp_path / "repo"
    for name in ("t1", "t2"):
        (root / "bench" / "tasks" / "dev" / name).mkdir(parents=True)
        (root / "bench" / "tasks" / "dev" / name / "task.toml").write_text("x")
    for arm in ("a.py", "b.py"):
        (tmp_path / arm).write_text(f"# {arm}\n")
    home = tmp_path / "home"
    (home / ".ridges").mkdir(parents=True)
    (home / ".ridges" / ".env.miner").write_text(f"RIDGES_OPENROUTER_API_KEY={file_key}\n")
    monkeypatch.setenv("HOME", str(home))
    if env_key:
        monkeypatch.setenv("RIDGES_OPENROUTER_API_KEY", env_key)
    else:
        monkeypatch.delenv("RIDGES_OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(rb, "ROOT", str(root))
    monkeypatch.setattr(rb, "host_identity", lambda path: {})
    monkeypatch.setattr(rb, "cli_version", lambda path: "x")
    monkeypatch.setattr(rb, "fetch_key_usage", lambda key: None)
    seen = {"keys": [], "order": []}

    class StubProxy:
        def __init__(self, scenario, **kw):
            seen["keys"].append(kw.get("key"))
            self.port = 1

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def stub_run_one(ridges, task, agent, timeout, raw, extra_args=None, extra_env=None):
        seen["order"].append((os.path.basename(task), open(agent).read().strip()))
        row = {"task": os.path.basename(task), "reward": 1.0, "wall_sec": 1, "error": "", "validity": "valid",
               "outcome": "solved", "auto_label": "solved", "images": "{}"}
        row.update((row_overrides or (lambda n: {}))(len(seen["order"])))
        return row

    if reconciliation is not None:
        monkeypatch.setattr(rb, "reconcile_proxy", lambda delta, row: reconciliation(len(seen["order"])))
    monkeypatch.setattr(rb, "fetch_key_remaining", lambda key: key_remaining)

    monkeypatch.setattr(rb, "FaultProxy", StubProxy)
    monkeypatch.setattr(rb, "run_one", stub_run_one)
    scenario = tmp_path / "s.json"
    scenario.write_text(json.dumps({"name": "s", "rules": []}))
    monkeypatch.setattr("sys.argv", ["run_bench"] + argv + ["--fault-scenario", str(scenario),
                                                            "--ledger", str(tmp_path / "ledger.json")])
    rb.run_bench()
    dirs = sorted(os.listdir(root / "bench" / "runs"))
    return seen, dirs


def test_B_FAULT_03_the_proxy_uses_the_same_resolved_key_as_the_ledger(tmp_path, monkeypatch):
    seen, _ = stub_bench(tmp_path, monkeypatch, ["--set", "dev", "--agent", str(tmp_path / "a.py")],
                         env_key="dummy-env-key", file_key="dummy-file-key")
    assert seen["keys"] and set(seen["keys"]) == {"dummy-env-key"}


def test_B_FAULT_03_paired_runs_counterbalance_the_order_and_keep_one_cohort_per_arm(tmp_path, monkeypatch):
    seen, dirs = stub_bench(tmp_path, monkeypatch, ["--set", "dev", "--repeats", "2", "--agent", str(tmp_path / "a.py"),
                                                    "--agent-b", str(tmp_path / "b.py")],
                            env_key="", file_key="dummy-file-key")
    arms = [agent for _, agent in seen["order"]]
    pairs = [tuple(arms[i:i + 2]) for i in range(0, len(arms), 2)]
    assert pairs == [("# a.py", "# b.py"), ("# b.py", "# a.py")] * 2   # 2 tasks x 2 repeats, alternating
    assert [task for task, _ in seen["order"][::2]] == ["t1", "t2", "t1", "t2"]
    assert len(dirs) == 2 and dirs[0].endswith("-dev-A") and dirs[1].endswith("-dev-B")


# ---------------------------------------------------------------- B-RUN-06 enforced experiment controls (follow-up P1)

MISMATCH = {"key_usage_delta": 0.02, "reconciled_cost": None, "cost_reconciliation": "key usage differs from proxy real cost"}
INCOMPLETE = {"key_usage_delta": 0.0, "reconciled_cost": None, "cost_reconciliation": "proxy accounting incomplete"}
MATCHED = {"key_usage_delta": 0.01, "reconciled_cost": 0.01, "cost_reconciliation": "matched-proxy"}
BASE = ["--set", "dev", "--repeats", "2"]


def agent_args(tmp_path):
    return ["--agent", str(tmp_path / "a.py"), "--agent-b", str(tmp_path / "b.py")]


def test_B_RUN_06_a_billing_mismatch_stops_before_the_next_dispatch(tmp_path, monkeypatch):
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--stop-on-billing-mismatch"],
                         "", "k", reconciliation=lambda n: MISMATCH)
    assert len(seen["order"]) == 1


def test_B_RUN_06_a_changed_input_stops_before_the_next_dispatch(tmp_path, monkeypatch):
    import tools.run_bench as rb

    calls = {"n": 0}
    real = rb.inputs_unchanged

    def moved(before, after):
        calls["n"] += 1
        return ["bundle"] if calls["n"] == 1 else real(before, after)

    monkeypatch.setattr(rb, "inputs_unchanged", moved)
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--stop-on-input-change"],
                         "", "k", reconciliation=lambda n: MATCHED)
    assert len(seen["order"]) == 1


def test_B_RUN_06_blocked_slots_stop_at_the_threshold_including_replacements(tmp_path, monkeypatch):
    void = lambda n: {"validity": "void-infrastructure", "outcome": "infrastructure-void", "reward": None}  # noqa: E731
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--max-blocked-slots", "2"],
                         "", "k", row_overrides=void, reconciliation=lambda n: MATCHED)
    assert len(seen["order"]) == 6        # two slots x (first attempt + 2 replacements), then stop


def test_B_RUN_06_consecutive_incomplete_accounting_stops_at_the_threshold(tmp_path, monkeypatch):
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--max-consecutive-incomplete", "3"],
                         "", "k", reconciliation=lambda n: INCOMPLETE if n >= 2 else MATCHED)
    assert len(seen["order"]) == 4        # trial 1 matched, trials 2-4 incomplete -> stop


def test_B_RUN_06_the_spend_limit_holds_unreconciled_allowances_before_dispatch(tmp_path, monkeypatch):
    # $0.50 limit, $0.29 allowance: an unreconciled first trial keeps its allowance held -> no second dispatch
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--spend-limit", "0.50"],
                         "", "k", reconciliation=lambda n: INCOMPLETE)
    assert len(seen["order"]) == 1
    # reconciled trials settle at their real cost and release the allowance -> all eight run
    seen, _ = stub_bench(tmp_path / "again", monkeypatch, BASE + agent_args(tmp_path / "again") + ["--spend-limit", "0.50"],
                         "", "k", reconciliation=lambda n: MATCHED)
    assert len(seen["order"]) == 8


def test_B_RUN_06_retained_key_headroom_is_enforced_and_fails_closed(tmp_path, monkeypatch):
    seen, _ = stub_bench(tmp_path, monkeypatch, BASE + agent_args(tmp_path) + ["--keep-headroom", "5"],
                         "", "k", reconciliation=lambda n: MATCHED, key_remaining=5.2)
    assert seen["order"] == []            # 5.20 - 0.29 < 5 retained
    seen, _ = stub_bench(tmp_path / "unknown", monkeypatch,
                         BASE + agent_args(tmp_path / "unknown") + ["--keep-headroom", "5"],
                         "", "k", reconciliation=lambda n: MATCHED, key_remaining=None)
    assert seen["order"] == []            # unknown headroom: no dispatch


def test_B_RUN_06_an_unreconciled_trial_keeps_its_reservation(tmp_path):
    from tools.run_bench import SessionLedger

    path = str(tmp_path / "l.json")
    ledger = SessionLedger(path, 1.0, lambda: 0.0)
    ledger.reserve("t1", 0.6)
    assert not ledger.fits(0.5)
    ledger.record("t1", 0.6, None, 0.0)   # zero usage delta, accounting incomplete: the review's reproduction
    assert not ledger.fits(0.5)
    assert not SessionLedger(path, 1.0, lambda: 0.0).fits(0.5)        # still held after a restart
    ledger.settle("t1", 0.01)                                          # real cost established later
    assert ledger.fits(0.5)
    offline = SessionLedger(str(tmp_path / "o.json"), 1.0, lambda: None)  # key usage unavailable
    offline.record("t2", 0.6, None, 0.001)
    assert not offline.fits(0.5)          # the held allowance counts, not the small consumed figure
    assert not os.path.exists(path + ".tmp")


def test_B_RUN_06_outcome_contract_for_the_wrapped_no_change_and_missing_evidence():
    from tools.bench_records import finalization_events, outcome_category

    done = '[quarry] returning candidate\n[quarry] [quarry-telemetry] {"version": 1}\n'
    no_change = done + 'Traceback (most recent call last):\n  ...\nRuntimeError: no change was produced\n'
    wrapped = {"exception_type": "MinerRuntimeError", "exception_message": "Miner runtime failed (exit 1)"}
    assert outcome_category("d", wrapped, no_change) == "empty-output"          # the agent's own no-change exit
    assert outcome_category("d", wrapped, done + "ZeroDivisionError: x\n") == "harness-exception"
    assert outcome_category("d", wrapped, "[quarry] starting\n") == "harness-exception"
    assert outcome_category("d", {}, "[quarry] starting\n") == "missing-evidence"   # truncated: no completion record
    assert outcome_category("d", {}, "") == "missing-evidence"                       # missing log
    assert outcome_category("d", {}, done) == "empty-output"
    assert outcome_category("d", {"patch_sha256": "ab"}, done) == "patch"
    assert finalization_events("")["fin_notices"] is None and finalization_events("")["fin_observed"] is False
    assert finalization_events(done)["fin_notices"] == 0 and finalization_events(done)["fin_observed"] is True

