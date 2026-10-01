#!/usr/bin/env python3
"""Fault-injecting inference proxy for local runs (v004 C1; B-FAULT-01..03).

The agent talks to this proxy the way it talks to the production sandbox proxy (`SANDBOX_PROXY_URL`, no key in the
container). The proxy forwards `POST /api/v1/chat/completions` to the upstream with the bench key and applies the
rules of a named scenario, deterministically (fixed seed, per-proxy request counter):

  stage "before" (never forwarded, so never billed): status (429/5xx/402/401 with body and headers), malformed
                 success, slow body (a valid error body trickled out)
  stage "after"  (forwarded, so possibly billed): drop (connection closed without a response), cost_multiplier
                 (the returned usage.cost is multiplied; the real cost is logged)

Every request is logged as one JSON line: time, index, model, rule, stage, upstream status, real and reported cost.
The key is never logged.

  python tools/fault_proxy.py bench/faults/cost-x10.json --port 18800 --log /tmp/proxy.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
ACTIONS = {"status", "malformed", "slow_body", "drop", "cost_multiplier"}
STAGE = {"status": "before", "malformed": "before", "slow_body": "before", "drop": "after", "cost_multiplier": "after"}


class ScenarioError(ValueError):
    pass


def load_scenario(path_or_dict) -> Dict:
    scenario = path_or_dict if isinstance(path_or_dict, dict) else json.load(open(path_or_dict))
    if not isinstance(scenario.get("name"), str) or not isinstance(scenario.get("rules"), list):
        raise ScenarioError("a scenario needs a name and a list of rules")
    for rule in scenario["rules"]:
        if rule.get("action") not in ACTIONS:
            raise ScenarioError(f"unknown action {rule.get('action')!r}; expected one of {sorted(ACTIONS)}")
        if rule["action"] == "status" and not isinstance(rule.get("status"), int):
            raise ScenarioError("a status rule needs an integer status")
        if rule["action"] == "cost_multiplier" and not float(rule.get("factor", 0)) > 0:
            raise ScenarioError("a cost_multiplier rule needs a positive factor")
    return scenario


def read_bench_key() -> str:
    path = os.path.expanduser("~/.ridges/.env.miner")
    for line in open(path, encoding="utf-8"):
        if line.strip().startswith("RIDGES_OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return ""


class Rules:
    """Which rule applies to request `index` (1-based) for `model`; deterministic for a seed."""

    def __init__(self, scenario: Dict):
        self.scenario = scenario
        self.random = random.Random(scenario.get("seed", 0))
        self.lock = threading.Lock()
        self.index = 0

    def next(self, model: str) -> Tuple[int, Optional[Dict], List[Dict]]:
        """(request index, the first matching fault rule, every matching cost_multiplier rule)."""
        with self.lock:
            self.index += 1
            index = self.index
            fault, multipliers = None, []
            for rule in self.scenario["rules"]:
                if not self._matches(rule, index, model):
                    continue
                if rule["action"] == "cost_multiplier":
                    multipliers.append(rule)
                elif fault is None:
                    fault = rule
            return index, fault, multipliers

    def _matches(self, rule: Dict, index: int, model: str) -> bool:
        if rule.get("model") and rule["model"] != model:
            return False
        if index < int(rule.get("from_request", 1)):
            return False
        if rule.get("until_request") is not None and index > int(rule["until_request"]):
            return False
        every = int(rule.get("every", 1))
        if every > 1 and (index - int(rule.get("from_request", 1))) % every:
            return False
        probability = float(rule.get("probability", 1.0))
        return probability >= 1.0 or self.random.random() < probability  # one draw per probabilistic match


def forward(upstream: str, key: str, body: bytes, timeout: float = 300.0) -> Tuple[int, bytes, Dict[str, str]]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(upstream, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), {k.lower(): v for k, v in response.getheaders()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


def reported_cost(body: bytes) -> Optional[float]:
    try:
        cost = json.loads(body).get("usage", {}).get("cost")
    except (ValueError, AttributeError):
        return None
    return float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None


def multiply_cost(body: bytes, factor: float) -> bytes:
    data = json.loads(body)
    usage = data.get("usage")
    if isinstance(usage, dict) and isinstance(usage.get("cost"), (int, float)):
        usage["cost"] = usage["cost"] * factor
    return json.dumps(data).encode()


def make_handler(rules: Rules, upstream: str, key: str, log_path: Optional[str]):
    log_lock = threading.Lock()

    def log(entry: Dict) -> None:
        if not log_path:
            return
        with log_lock, open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def reply(self, status: int, body: bytes, headers: Optional[Dict[str, str]] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802 (http.server API)
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path.rstrip("/") != "/api/v1/chat/completions":
                self.reply(404, b'{"error": {"code": 404, "message": "unknown path"}}')
                return
            try:
                model = str(json.loads(body).get("model") or "")
            except ValueError:
                model = ""
            index, fault, multipliers = rules.next(model)
            entry = {"t": round(time.time(), 3), "index": index, "model": model, "rule": None, "stage": None,
                     "upstream_status": None, "real_cost": None, "reported_cost": None}
            if fault and STAGE[fault["action"]] == "before":
                entry.update(rule=fault.get("id") or fault["action"], stage="before")
                if fault["action"] == "status":
                    payload = json.dumps(fault.get("body") or {"error": {"code": fault["status"],
                                                                         "message": fault.get("message", "injected")}})
                    self.reply(fault["status"], payload.encode(), {str(k): str(v) for k, v in (fault.get("headers") or {}).items()})
                elif fault["action"] == "malformed":
                    self.reply(200, b'{"choices": "not a list", "usage": {}}')
                else:  # slow_body: a valid 503 body sent one byte at a time
                    payload = b'{"error": {"code": 503, "message": "injected slow body"}}'
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    pause = float(fault.get("seconds", 30.0)) / max(1, len(payload))
                    try:
                        for byte in payload:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(pause)
                    except (BrokenPipeError, ConnectionResetError):
                        entry["client_disconnected"] = True
                log(entry)
                return
            status, upstream_body, upstream_headers = forward(upstream, key, body)
            entry.update(upstream_status=status, real_cost=reported_cost(upstream_body))
            if fault and fault["action"] == "drop":
                entry.update(rule=fault.get("id") or "drop", stage="after")
                log(entry)
                self.close_connection = True
                self.connection.close()  # forwarded (possibly billed), then no response
                return
            if status == 200 and multipliers:
                factor = 1.0
                for rule in multipliers:
                    factor *= float(rule["factor"])
                upstream_body = multiply_cost(upstream_body, factor)
                entry.update(rule="cost_multiplier", stage="after", factor=factor)
            entry["reported_cost"] = reported_cost(upstream_body)
            keep = {k: v for k, v in upstream_headers.items() if k in ("retry-after",)}
            log(entry)
            self.reply(status, upstream_body, keep)

    return Handler


class FaultProxy:
    """Run the proxy in a background thread (for run_bench and tests)."""

    def __init__(self, scenario, port: int = 0, host: str = "0.0.0.0", upstream: str = UPSTREAM,
                 key: Optional[str] = None, log_path: Optional[str] = None):
        self.scenario = load_scenario(scenario)
        self.rules = Rules(self.scenario)
        handler = make_handler(self.rules, upstream, read_bench_key() if key is None else key, log_path)
        self.server = ThreadingHTTPServer((host, port), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> FaultProxy:
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario")
    parser.add_argument("--port", type=int, default=18800)
    parser.add_argument("--log", default="")
    parser.add_argument("--upstream", default=UPSTREAM)
    args = parser.parse_args(argv)
    with FaultProxy(args.scenario, args.port, upstream=args.upstream, log_path=args.log or None) as proxy:
        print(f"fault proxy '{proxy.scenario['name']}' on port {proxy.port}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
