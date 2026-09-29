"""Unit tests: LLM client, tools, driver loop (docs/specs/harness.md §3, §8, §9)."""

import json
import os

import pytest

from quarry.clock import Clock
from quarry.llm import ChatResult, LLMError, ModelRoute, ProxyClient, ToolCall, parse_tool_calls, resolve_endpoint
from quarry.loop import DriverLoop
from quarry.proc import ProcessRunner
from quarry.spec import compile_statement
from quarry.tools import ToolContext, ToolRegistry, default_tools
from quarry.wallet import BudgetExhausted, Wallet
from tests.conftest import read, write

OK_BODY = {
    "choices": [{"message": {"content": "done", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "read", "arguments": '{"path": "a.py"}'}},
    ]}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001, "prompt_tokens_details": {"cached_tokens": 60}},
}


class Transport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, url, body, headers, timeout):
        self.requests.append((url, json.loads(body), headers))
        status, payload = self.replies.pop(0)
        return status, payload if isinstance(payload, str) else json.dumps(payload)


def client(replies, cap=1.0):
    transport = Transport(replies)
    c = ProxyClient(Wallet(cap, {"m": (1.0, 1.0), "fb": (1.0, 1.0)}), {"SANDBOX_PROXY_URL": "http://proxy"}, transport, sleep=lambda s: None)
    return c, transport


def test_H_LLM_01_endpoint_resolution():
    assert resolve_endpoint({"SANDBOX_PROXY_URL": "http://p:80/", "OPENROUTER_API_KEY": "k"}) == ("http://p:80/api/v1/chat/completions", "k")
    assert resolve_endpoint({"RIDGES_INFERENCE_BASE_URL": "https://x/api/v1", "RIDGES_INFERENCE_API_KEY": "l"}) == ("https://x/api/v1/chat/completions", "l")
    assert resolve_endpoint({})[0].endswith("/api/v1/chat/completions")


def test_H_LLM_02_retries_then_falls_back():
    c, transport = client([(503, "busy"), (429, "slow down"), (200, OK_BODY)])
    result = c.complete([{"role": "user", "content": "hi"}], ModelRoute("m", "fb"))
    models = [req[1]["model"] for req in transport.requests]
    assert models == ["m", "m", "fb"]
    assert result.tool_calls[0].name == "read"
    c2, _ = client([(500, "x")] * 4)
    with pytest.raises(LLMError):
        c2.complete([{"role": "user", "content": "hi"}], ModelRoute("m"))


def test_H_LLM_03_budget_refusal_is_not_retried():
    c, transport = client([(402, "payment required"), (200, OK_BODY)])
    with pytest.raises(BudgetExhausted):
        c.complete([{"role": "user", "content": "hi"}], ModelRoute("m", "fb"))
    assert len(transport.requests) == 1 and c.wallet.spent


def test_H_LLM_04_request_shape():
    c, transport = client([(200, OK_BODY)])
    c.complete([{"role": "user", "content": "hi"}], ModelRoute("m", max_tokens=321), tools=[{"type": "function"}])
    url, body, headers = transport.requests[0]
    assert url == "http://proxy/api/v1/chat/completions"
    assert body["temperature"] == 0 and body["max_tokens"] == 321 and body["tools"]


def test_H_LLM_05_defensive_tool_call_parsing():
    calls = parse_tool_calls({"tool_calls": [
        {"function": {"name": "edit", "arguments": "{not json"}},
        {"id": "", "function": {"name": "read", "arguments": {"path": "x"}}},
        {"id": "z", "function": {"name": "search", "arguments": "[1]"}},
    ]})
    assert calls[0].error and calls[0].id.startswith("call_")
    assert calls[1].arguments == {"path": "x"} and calls[1].id
    assert calls[2].error


def test_H_LLM_06_telemetry_records_tokens_and_cost():
    c, _ = client([(200, OK_BODY)])
    c.complete([{"role": "user", "content": "hi"}], ModelRoute("m"), role="driver")
    record = c.telemetry[-1]
    assert (record.role, record.prompt_tokens, record.cached_tokens, record.completion_tokens) == ("driver", 100, 60, 10)
    assert record.cost == pytest.approx(0.001) and c.wallet.spent_usd == pytest.approx(0.001)


BOUNDED = "# T\n\nLimit production changes to `pkg/mod.py`, specifically `f()`.\n"


def tool_ctx(root, statement=BOUNDED):
    return ToolContext(root, compile_statement(statement), ProcessRunner(root), os.path.join(root, "..", "scratch"))


def test_H_TOOL_01_registry_schemas_and_unknown_tool(tmp_path):
    registry = ToolRegistry(default_tools())
    names = [s["function"]["name"] for s in registry.schemas()]
    assert {"read", "search", "edit", "shell", "sql", "finish"} <= set(names)
    assert "unknown tool" in registry.dispatch(tool_ctx(str(tmp_path)), "nope", {})


def test_H_TOOL_02_read_is_capped_and_confined(tmp_path):
    root = str(tmp_path / "r")
    write(root, "big.py", "\n".join(f"x{i} = {i}" for i in range(1000)))
    registry = ToolRegistry(default_tools())
    ctx = tool_ctx(root)
    out = registry.dispatch(ctx, "read", {"path": "big.py", "start": 10})
    assert "lines 10-409" in out and "more lines" in out
    assert "outside" in registry.dispatch(ctx, "read", {"path": "../../etc/passwd"})


def test_H_TOOL_03_search_counts_and_skips_vendored(tmp_path):
    root = str(tmp_path / "r")
    for i in range(60):
        write(root, f"src/m{i:02}.py", "SELECT_ME = 1\n")
    write(root, "node_modules/x.js", "SELECT_ME\n")
    out = ToolRegistry(default_tools()).dispatch(tool_ctx(root), "search", {"pattern": "SELECT_ME", "glob": "*.py"})
    assert out.startswith("60 hits") and "node_modules" not in out and len(out.splitlines()) == 51


def test_H_TOOL_04_edit_exact_once_and_scope(tmp_path):
    root = str(tmp_path / "r")
    write(root, "pkg/mod.py", "def f():\n    return 1\n\n\ndef g():\n    return 1\n")
    write(root, "pkg/other.py", "X = 1\n")
    registry, ctx = ToolRegistry(default_tools()), tool_ctx(root)
    assert "matched 2 times" in registry.dispatch(ctx, "edit", {"path": "pkg/mod.py", "old": "return 1", "new": "return 2"})
    assert "Closest text" in registry.dispatch(ctx, "edit", {"path": "pkg/mod.py", "old": "retrun 1\n", "new": "x"})
    assert "edited" in registry.dispatch(ctx, "edit", {"path": "pkg/mod.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})
    assert "refused" in registry.dispatch(ctx, "edit", {"path": "pkg/other.py", "old": "X = 1", "new": "X = 2"})
    assert read(root, "pkg/other.py") == "X = 1\n"
    assert "refused" in registry.dispatch(ctx, "create", {"path": "pkg/new.py", "content": "x"})


def test_H_TOOL_05_shell_runs_in_repo_with_timeout(tmp_path):
    root = str(tmp_path / "r")
    write(root, "a.txt", "hello\n")
    registry, ctx = ToolRegistry(default_tools()), tool_ctx(root)
    assert "hello" in registry.dispatch(ctx, "shell", {"command": "cat a.txt"})
    assert "timed out" in registry.dispatch(ctx, "shell", {"command": "sleep 5", "timeout": 1})


def test_H_TOOL_06_scratch_is_outside_repo(tmp_path):
    root = str(tmp_path / "r")
    os.makedirs(root)
    path = ToolRegistry(default_tools()).dispatch(tool_ctx(root), "scratch", {"name": "../../probe.py", "content": "print(1)"})
    assert os.path.isfile(path) and not os.path.abspath(path).startswith(os.path.abspath(root))


def test_H_TOOL_07_sql_guards(tmp_path):
    from quarry.profile import DbTarget

    root = str(tmp_path / "r")
    os.makedirs(root)
    registry, ctx = ToolRegistry(default_tools()), tool_ctx(root)
    assert "no database" in registry.dispatch(ctx, "sql", {"query": "select 1"})
    ctx.databases = [DbTarget("clickhouse", "127.0.0.1", 1, "u", "", "d")]
    assert "refused" in registry.dispatch(ctx, "sql", {"query": "INSERT INTO t VALUES (1)"})
    assert "error" in registry.dispatch(ctx, "sql", {"query": "SELECT 1"})  # nothing listens on port 1


def test_H_TOOL_08_finish_sets_state(tmp_path):
    ctx = tool_ctx(str(tmp_path))
    ToolRegistry(default_tools()).dispatch(ctx, "finish", {"summary": "done", "symbol": "A.b"})
    assert ctx.finished and ctx.summary == "done" and ctx.target_symbol == "A.b"


class ScriptedClient:
    """Returns pre-baked replies: each item is a list of (tool, args) or a plain string (no tool calls)."""

    def __init__(self, script, raise_at=None):
        self.script = list(script)
        self.calls = 0
        self.raise_at = raise_at

    def complete(self, messages, route, tools=None, role="driver", timeout=0, max_tokens=None, deadline=None):
        self.calls += 1
        if self.raise_at == self.calls:
            raise BudgetExhausted("cap")
        step = self.script.pop(0) if self.script else ""
        if isinstance(step, str):
            return ChatResult(step, [], {}, "m", {"role": "assistant", "content": step})
        calls = [ToolCall(f"id{self.calls}_{i}", name, args) for i, (name, args) in enumerate(step)]
        message = {"role": "assistant", "content": "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in calls
        ]}
        return ChatResult("", calls, {}, "m", message)


def make_loop(root, script, raise_at=None, max_turns=10, seconds=100):
    ctx = tool_ctx(root)
    loop = DriverLoop(ScriptedClient(script, raise_at), ModelRoute("m"), ToolRegistry(default_tools()), ctx,
                      Clock(seconds + 60).slice(1.0), max_turns=max_turns)
    return loop, ctx


def test_H_LOOP_01_stop_reasons(tmp_path):
    root = str(tmp_path / "r")
    write(root, "pkg/mod.py", "def f():\n    return 1\n")
    loop, _ = make_loop(root, [[("read", {"path": "pkg/mod.py"})], [("finish", {"summary": "ok"})]])
    assert loop.run([{"role": "system", "content": "s"}]).reason == "finished"
    loop, _ = make_loop(root, [[("read", {"path": "pkg/mod.py"})]] * 20, max_turns=3)
    assert loop.run([]).reason == "max-turns"
    loop, _ = make_loop(root, [[("read", {"path": "pkg/mod.py"})]] * 5, raise_at=2)
    assert loop.run([]).reason == "budget"
    loop, _ = make_loop(root, [], seconds=0)
    loop.timer.end = loop.timer.clock.now() - 1
    assert loop.run([]).reason == "deadline"


def test_H_LOOP_02_all_tool_calls_answered_in_order(tmp_path):
    root = str(tmp_path / "r")
    write(root, "pkg/mod.py", "def f():\n    return 1\n")
    loop, _ = make_loop(root, [[("read", {"path": "pkg/mod.py"}), ("search", {"pattern": "def"}), ("finish", {"summary": "x"})]])
    messages = []
    loop.run(messages)
    tool_messages = [m for m in messages if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["id1_0", "id1_1", "id1_2"]


def test_H_LOOP_03_compaction_keeps_pinned_and_recent(tmp_path):
    loop, _ = make_loop(str(tmp_path), [])
    loop.compact_tokens = 1000
    messages = [{"role": "system", "content": "S" * 3000}, {"role": "user", "content": "U" * 3000}]
    messages += [{"role": "tool", "tool_call_id": str(i), "content": f"first line {i}\n" + "x" * 3000} for i in range(20)]
    loop.compact(messages)
    assert messages[0]["content"] == "S" * 3000 and messages[1]["content"] == "U" * 3000
    assert messages[2]["content"].endswith("[older output compacted]")
    assert all("compacted" not in m["content"] for m in messages[-8:])


def test_H_LOOP_04_stalls_after_three_empty_replies(tmp_path):
    loop, _ = make_loop(str(tmp_path), ["thinking", "", "still thinking"])
    messages = []
    outcome = loop.run(messages)
    assert outcome.reason == "stalled"
    assert sum(1 for m in messages if m["role"] == "user") == 2
