"""B-FAULT-01..02: the fault-injecting inference proxy (v004 C1), against a fake upstream (no paid inference)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from quarry.llm import ModelRoute, ProxyClient, http_transport
from quarry.wallet import Wallet
from tools.fault_proxy import FaultProxy, Rules, ScenarioError, load_scenario

OK = {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.002}}


class Upstream:
    """Fake provider: records requests (model, Authorization) and answers OK."""

    def __init__(self):
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((body.get("model"), self.headers.get("Authorization")))
                payload = json.dumps(OK).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

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


def lines(path):
    return [json.loads(line) for line in open(path)]


def test_B_FAULT_01_forwards_with_the_bench_key_and_logs_without_it(upstream, tmp_path):
    log = str(tmp_path / "proxy.jsonl")
    with FaultProxy({"name": "clean", "rules": []}, host="127.0.0.1", upstream=upstream.url, key="sk-secret", log_path=log) as proxy:
        status, text, _ = post(proxy.port)
        missing = http_transport(f"http://127.0.0.1:{proxy.port}/other", b"{}", {}, 5.0)
    assert status == 200 and json.loads(text) == OK
    assert upstream.requests == [("primary", "Bearer sk-secret")]
    assert missing[0] == 404
    entries = lines(log)
    assert entries[0]["upstream_status"] == 200 and entries[0]["real_cost"] == entries[0]["reported_cost"] == 0.002
    assert "sk-secret" not in open(log).read()


def test_B_FAULT_02_before_forward_faults_are_never_sent_upstream(upstream, tmp_path):
    scenario = {"name": "s", "rules": [
        {"action": "status", "status": 429, "until_request": 1, "headers": {"Retry-After": "3"}},
        {"action": "status", "status": 402, "from_request": 2, "until_request": 2, "message": "in_flight_budget_exhausted"},
        {"action": "malformed", "from_request": 3, "until_request": 3},
    ]}
    log = str(tmp_path / "proxy.jsonl")
    with FaultProxy(scenario, host="127.0.0.1", upstream=upstream.url, key="k", log_path=log) as proxy:
        first, second, third, fourth = (post(proxy.port) for _ in range(4))
    assert first[0] == 429 and first[2]["retry-after"] == "3"
    assert second[0] == 402 and "in_flight" in second[1]
    assert third[0] == 200 and json.loads(third[1])["choices"] == "not a list"
    assert fourth[0] == 200 and len(upstream.requests) == 1          # only the clean request was forwarded
    assert [e["stage"] for e in lines(log)] == ["before", "before", "before", None]


def test_B_FAULT_02_after_forward_faults_are_forwarded_and_logged_as_possibly_billed(upstream, tmp_path):
    scenario = {"name": "s", "rules": [{"action": "drop", "until_request": 1}, {"action": "cost_multiplier", "factor": 10}]}
    log = str(tmp_path / "proxy.jsonl")
    with FaultProxy(scenario, host="127.0.0.1", upstream=upstream.url, key="k", log_path=log) as proxy:
        with pytest.raises((OSError, Exception)):
            post(proxy.port)                                        # forwarded, then no response
        status, text, _ = post(proxy.port)
    assert len(upstream.requests) == 2
    assert status == 200 and json.loads(text)["usage"]["cost"] == pytest.approx(0.02)
    dropped, multiplied = lines(log)
    assert dropped["stage"] == "after" and dropped["rule"] == "drop" and dropped["real_cost"] == 0.002
    assert multiplied["real_cost"] == 0.002 and multiplied["reported_cost"] == pytest.approx(0.02)


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


def test_B_FAULT_02_invalid_scenarios_are_rejected():
    for bad in ({"rules": []}, {"name": "x", "rules": [{"action": "explode"}]},
                {"name": "x", "rules": [{"action": "status"}]}, {"name": "x", "rules": [{"action": "cost_multiplier"}]}):
        with pytest.raises(ScenarioError):
            load_scenario(bad)


def test_B_FAULT_02_slow_body_is_cut_off_by_the_agent_transport(upstream):
    with FaultProxy({"name": "slow", "rules": [{"action": "slow_body", "seconds": 5}]}, host="127.0.0.1",
                    upstream=upstream.url, key="k") as proxy:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            post(proxy.port, timeout=0.4)
        assert time.monotonic() - started < 1.5


def test_B_FAULT_02_quarry_client_recovers_through_the_proxy(upstream, tmp_path):
    # End to end over HTTP: two 503s on the primary -> this call uses the fallback; later calls return to the primary.
    scenario = {"name": "burst", "rules": [{"action": "status", "status": 503, "model": "primary", "until_request": 2}]}
    with FaultProxy(scenario, host="127.0.0.1", upstream=upstream.url, key="k") as proxy:
        now = [1000.0]
        client = ProxyClient(Wallet(1.0, {"primary": (0.2, 1.2), "fallback": (0.48, 4.2)}),
                             {"SANDBOX_PROXY_URL": f"http://127.0.0.1:{proxy.port}"},
                             sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        route = ModelRoute("primary", "fallback")
        client.complete([{"role": "user", "content": "hi"}], route)
        now[0] += 61
        client.complete([{"role": "user", "content": "hi"}], route)
    assert [m for m, _ in upstream.requests] == ["fallback", "primary"]


# ---------------------------------------------------------------- B-FAULT-03 (run_bench wiring)


def test_B_FAULT_03_proxy_summary_and_reconciliation_use_the_real_cost(tmp_path):
    from tools.bench_cost import proxy_summary, reconcile_proxy

    log = tmp_path / "p.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in [
        {"model": "primary", "stage": "before", "rule": "status", "upstream_status": None},
        {"model": "fallback", "stage": "after", "rule": "cost_multiplier", "upstream_status": 200,
         "real_cost": 0.002, "reported_cost": 0.02},
        {"model": "primary", "stage": None, "rule": None, "upstream_status": 200, "real_cost": 0.003, "reported_cost": 0.003},
    ]) + "\n")
    summary = proxy_summary(str(log))
    assert summary["proxy_requests"] == 3 and summary["proxy_injected_before"] == 1 and summary["proxy_injected_after"] == 0
    assert summary["proxy_real_cost"] == 0.005 and summary["proxy_reported_cost"] == 0.023
    assert json.loads(summary["proxy_models"]) == {"fallback": 1, "primary": 2}
    assert reconcile_proxy(0.00502, summary)["cost_reconciliation"] == "matched-proxy"
    assert reconcile_proxy(0.02, summary)["reconciled_cost"] is None      # another client spent on the key


def test_B_FAULT_03_run_one_routes_the_trial_through_the_custom_provider(tmp_path, monkeypatch):
    import tools.run_bench as rb

    seen = {}

    def fake_run(cmd, **kwargs):
        if "run-local" in cmd:  # the image watcher's `docker images` calls use the same module
            seen["cmd"], seen["env"] = cmd, kwargs.get("env") or {}

        class P:
            stdout, stderr = "FAILED: stub\n", ""
        return P()

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    rb.run_one(["ridges"], str(tmp_path / "task-a"), "agent.py", 10, str(tmp_path / "raw.log"),
               ["--provider", "custom"], {"RIDGES_CUSTOM_SANDBOX_PROXY_URL": "http://172.17.0.1:18801"})
    assert seen["cmd"][-2:] == ["--provider", "custom"]
    assert seen["env"]["RIDGES_CUSTOM_SANDBOX_PROXY_URL"] == "http://172.17.0.1:18801"


def test_B_FAULT_03_fault_runs_never_share_a_cohort_with_normal_runs():
    from tools.bench_summary import cohort_key

    normal = {"set": "dev", "agent_sha256": "a", "tasks": {"t": "d"}, "host": {}}
    faulted = dict(normal, fault_scenario={"name": "cost-x10", "sha256": "s"})
    assert cohort_key(normal) != cohort_key(faulted)


def test_B_FAULT_03_results_csv_keeps_the_fault_columns(tmp_path):
    import csv

    from tools.run_bench import save_results

    save_results(str(tmp_path), [{"trial_id": "t1", "fault_scenario": "cost-x10", "proxy_requests": 9,
                                  "proxy_real_cost": 0.004, "proxy_reported_cost": 0.04}])
    row = next(csv.DictReader(open(tmp_path / "results.csv")))
    assert row["fault_scenario"] == "cost-x10" and row["proxy_requests"] == "9" and row["proxy_reported_cost"] == "0.04"

