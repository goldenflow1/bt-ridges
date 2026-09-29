"""Offline end-to-end: the bundled dist/agent.py, loaded like the platform runtime loads it, against a fake proxy.

Covers H-SHELL-01 and H-SHELL-03 plus the M0 exit scenario (docs/plans/M0-harness.md).
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.conftest import write

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUNDLE = os.path.join(ROOT, "dist", "agent.py")

MOD = '''"""Reporting helpers."""

import math


class Report:
    def total(self, rows):
        return sum(r for r in rows)

    def other(self, rows):
        return len(rows)


def helper():
    return math.pi
'''

STATEMENT = """# Repair report totals

Work in `/app`. Limit production changes to `pkg/mod.py`, specifically
`Report.total()`. Keep its signature and the rest of the file unchanged,
including imports; use only names the file already imports.

- totals ignore negative rows;

Write the method without Python loops or comprehensions.

Run these checks before finishing:

```bash
python -c "import pkg.mod"
```
"""

GOOD_EDIT = ("edit", {"path": "pkg/mod.py", "old": "        return sum(r for r in rows)",
                      "new": "        return sum(filter(lambda r: r > 0, rows))"})
LOOP_EDIT = ("edit", {"path": "pkg/mod.py", "old": "        return sum(r for r in rows)",
                      "new": "        total = 0\n        for r in rows:\n            total += max(r, 0)\n        return total"})
FIX_LOOP = ("edit", {"path": "pkg/mod.py", "old": "        total = 0\n        for r in rows:\n            total += max(r, 0)\n        return total",
                     "new": "        return sum(map(lambda r: max(r, 0), rows))"})


def reply(*calls, cost=0.001):
    tool_calls = [
        {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]
    return 200, {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}],
                 "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "cost": cost}}


class FakeProxy:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                proxy.requests.append((self.path, body))
                status, payload = proxy.replies.pop(0) if proxy.replies else (500, {"error": "script exhausted"})
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


LOADER = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ridges_miner_agent", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
patch = module.agent_main({"problem_statement": open(sys.argv[2]).read()})
assert isinstance(patch, str) and patch.strip()
open(sys.argv[3], "w").write(patch)
"""


@pytest.fixture(scope="module", autouse=True)
def bundle():
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py")], check=True, capture_output=True)


def run_bundle(tmp_path, replies, statement=STATEMENT):
    repo = str(tmp_path / "app")
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/mod.py", MOD)
    write(repo, "pkg/views.py", "VIEW = 1\n")
    write(repo, "run.sh", "echo hi\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "base", "--no-gpg-sign"]):
        subprocess.run(cmd, cwd=repo, check=True)
    statement_file = str(tmp_path / "statement.md")
    patch_file = str(tmp_path / "patch.diff")
    with open(statement_file, "w") as handle:
        handle.write(statement)
    proxy = FakeProxy(replies)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RIDGES_", "SANDBOX_", "QUARRY_"))}
    env.update({"SANDBOX_PROXY_URL": proxy.url, "AGENT_TIMEOUT": "300", "RIDGES_MAX_COST_USD": "0.29"})
    try:
        result = subprocess.run([sys.executable, "-c", LOADER, BUNDLE, statement_file, patch_file],
                                cwd=repo, env=env, capture_output=True, text=True, timeout=240)
    finally:
        proxy.close()
    patch = open(patch_file).read() if os.path.exists(patch_file) else ""
    return result, patch, proxy, repo


def test_H_SHELL_01_messy_run_returns_only_the_in_scope_change(tmp_path):
    replies = [
        reply(("read", {"path": "pkg/mod.py"}), ("scratch", {"name": "probe.py", "content": "print(1)"})),
        reply(GOOD_EDIT),
        reply(("shell", {"command": "chmod +x pkg/mod.py && echo junk > notes.txt && echo 'VIEW = 2' > pkg/views.py"})),
        reply(("shell", {"command": "sed -i 's/return len(rows)/return len(list(rows))/' pkg/mod.py"})),
        reply(("finish", {"summary": "done"})),
    ]
    result, patch, proxy, repo = run_bundle(tmp_path, replies)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "filter(lambda r: r > 0, rows)" in patch
    assert "len(list(rows))" not in patch
    assert "views.py" not in patch and "notes.txt" not in patch and "old mode" not in patch
    assert proxy.requests[0][0] == "/api/v1/chat/completions"
    # The platform checks the patch against the working tree exactly as the agent leaves it: no cleanup here.
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout == ""
    assert subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo, text=True).returncode == 0


def test_H_SHELL_01_gate_feedback_drives_a_second_round(tmp_path):
    replies = [reply(LOOP_EDIT), reply(("finish", {"summary": "v1"})), reply(FIX_LOOP), reply(("finish", {"summary": "v2"}))]
    result, patch, proxy, _repo = run_bundle(tmp_path, replies)
    assert result.returncode == 0, result.stderr[-3000:]
    added = [line for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert any("map(lambda r: max(r, 0), rows)" in line for line in added)
    assert not any("for r in rows:" in line for line in added)
    feedback = [m["content"] for m in proxy.requests[2][1]["messages"] if m["role"] == "user"][-1]
    assert "statement-rules" in feedback and "no_loops" in feedback


def test_H_SHELL_03_provider_failure_after_an_edit_still_returns_the_edit(tmp_path):
    replies = [reply(GOOD_EDIT)] + [(500, {"error": "down"})] * 8
    result, patch, _proxy, repo = run_bundle(tmp_path, replies)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "filter(lambda r: r > 0, rows)" in patch
    assert subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=repo, text=True).returncode == 0


def test_H_SHELL_03_nothing_produced_raises(tmp_path):
    result, patch, proxy, _repo = run_bundle(tmp_path, [(402, {"error": "budget exhausted"})])
    assert result.returncode != 0 and patch == ""
    assert "no change was produced" in result.stderr
    assert len(proxy.requests) == 1


def test_H_WALLET_06_H_LLM_08_bundle_telemetry_to_csv(tmp_path):
    """Bundled agent → versioned telemetry line → bench parser → CSV, with the cost split and cache coverage."""
    import csv

    from quarry.telemetry import parse_log
    from tools.run_bench import TELEMETRY_FIELDS, flatten_telemetry

    status, body = reply(GOOD_EDIT)
    body["usage"] = {"prompt_tokens": 1000, "completion_tokens": 100, "cost": 0.0003,
                     "prompt_tokens_details": {"cached_tokens": 600}}
    estimated = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "f", "type": "function", "function": {"name": "finish", "arguments": "{\"summary\": \"ok\"}"}}]}}],
        "usage": {"prompt_tokens": 2000, "completion_tokens": 50}}  # no cost: must be labelled an estimate
    result, patch, _proxy, _repo = run_bundle(tmp_path, [(status, body), (200, estimated)])
    assert result.returncode == 0, result.stderr[-3000:]
    record = parse_log(result.stderr)
    assert record and record["version"] == 1
    row = flatten_telemetry(record)
    out = tmp_path / "results.csv"
    with open(out, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TELEMETRY_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    back = next(csv.DictReader(open(out)))
    assert back["telemetry"] == "v1" and back["attempts"] == "2"
    assert float(back["cost_provider"]) == 0.0003 and float(back["cost_estimate"]) > 0 and back["estimated_calls"] == "1"
    assert back["accounting_complete"] == "True" and back["unknown_attempts"] == "0"
    assert back["cache_read_reported"] == "1" and back["cache_read_tokens"] == "600" and back["successful_calls"] == "2"
    assert back["cache_write_tokens"] == ""  # never reported: empty, not 0
    assert back["read_share"] == "0.6" and back["read_share_calls"] == "1"
