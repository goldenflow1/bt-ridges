"""v004 B2/B3: finalization notice, empty-finish refusal (H-LOOP-06/07) and the finalization round (H-SHELL-15)."""

import json

from quarry.clock import Clock
from quarry.llm import ChatResult, LLMError, ModelRoute, ToolCall
from quarry.loop import DriverLoop
from quarry.proc import ProcResult
from quarry.shell import Settings, Workflow
from quarry.tools import ToolRegistry, default_tools
from quarry.wallet import BudgetExhausted
from tests.conftest import write
from tests.scenario.test_review_2026_09_29 import M, env
from tests.unit.test_llm_tools_loop import tool_ctx

READ = [("read", {"path": "m.py"})]
EDIT = [("edit", {"path": "m.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"})]
FINISH = [("finish", {"summary": "done"})]


class Client:
    """Scripted model; `before_call(n)` may raise (e.g. BudgetExhausted) to simulate the provider."""

    def __init__(self, steps, before_call=None):
        self.steps, self.before_call, self.n, self.seen = list(steps), before_call, 0, []
        self.telemetry = []

    def complete(self, messages, route, tools=None, role="driver", timeout=0, max_tokens=None, deadline=None):
        self.n += 1
        self.seen.append([dict(m) for m in messages])
        if self.before_call:
            self.before_call(self.n)
        step = self.steps.pop(0) if self.steps else FINISH
        calls = [ToolCall(f"c{self.n}_{i}", name, args) for i, (name, args) in enumerate(step)]
        msg = {"role": "assistant", "content": "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}} for c in calls]}
        return ChatResult("", calls, {}, "m", msg)


def loop_for(root, client, reserve=lambda: False, changed=lambda: False, seconds=100):
    ctx = tool_ctx(root, statement())
    return DriverLoop(client, ModelRoute("m"), ToolRegistry(default_tools()), ctx, Clock(seconds + 60).slice(1.0),
                      max_turns=10, reserve=reserve, has_changes=changed), ctx


def users(messages):
    return [m["content"] for m in messages if m["role"] == "user"]


# ---------------------------------------------------------------- H-LOOP-06


def test_H_LOOP_06_one_finalization_notice_when_the_reserve_is_reached(tmp_path):
    write(str(tmp_path), "m.py", M)
    client = Client([READ, READ, READ, FINISH])
    loop, _ = loop_for(str(tmp_path), client, reserve=lambda: client.n >= 2)
    messages = []
    loop.run(messages)
    notices = [u for u in users(messages) if "budget and time" in u]
    assert len(notices) == 1 and "make the change" in notices[0]


def test_H_LOOP_06_notice_asks_to_verify_and_finish_when_a_change_exists(tmp_path):
    write(str(tmp_path), "m.py", M)
    loop, _ = loop_for(str(tmp_path), Client([READ, FINISH]), reserve=lambda: True, changed=lambda: True)
    messages = []
    loop.run(messages)
    notice = [u for u in users(messages) if "budget and time" in u][0]
    assert "verify" in notice and "make the change" not in notice


# ---------------------------------------------------------------- H-LOOP-07


def test_H_LOOP_07_finish_with_an_unchanged_tree_is_refused_once(tmp_path):
    write(str(tmp_path), "m.py", M)
    loop, ctx = loop_for(str(tmp_path), Client([FINISH, READ, FINISH]))
    messages = []
    outcome = loop.run(messages)
    assert outcome.reason == "finished" and outcome.turns == 3
    refusals = [m["content"] for m in messages if m["role"] == "tool" and m["content"].startswith("Not finished")]
    assert len(refusals) == 1


def test_H_LOOP_07_finish_with_a_change_or_without_time_is_accepted(tmp_path):
    write(str(tmp_path), "m.py", M)
    loop, _ = loop_for(str(tmp_path), Client([FINISH]), changed=lambda: True)
    assert loop.run([]).turns == 1
    loop, _ = loop_for(str(tmp_path), Client([FINISH]), seconds=10)  # < 30 s left in the phase
    assert loop.run([]).turns == 1


# ---------------------------------------------------------------- H-SHELL-15


def statement():
    return "# Fix f\n\nChange only `f()` in `m.py` so it returns 2.\n"


def test_H_SHELL_15_driver_budget_exhausted_before_any_edit_still_hands_in_a_patch(make_repo, tmp_path):
    # The v003 failure shape: exploration uses the driver budget, no edit yet -> previously an empty patch.
    repo = make_repo({"m.py": M})
    holder = {}

    def provider(n):
        if holder["wf"].wallet._phase_name == "driver" and n >= 3:
            raise BudgetExhausted("driver phase budget used")

    client = Client([READ, READ, READ, EDIT, FINISH], before_call=provider)
    settings = Settings()
    settings.fix_rounds = 0
    wf = Workflow(statement(), repo.root, env(tmp_path), client, settings)
    holder["wf"] = wf
    wf.run()
    best = wf.store.best()
    assert best is not None and "return 2" in best.diff
    assert any("finalization round" in line for line in wf.log)
    assert any("budget and time" in u for u in users(client.seen[-1]))


def test_H_SHELL_15_no_finalization_round_after_a_hard_budget_refusal(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    holder = {}

    def provider(n):
        if n >= 2:
            holder["wf"].wallet.mark_spent()
            raise BudgetExhausted("hard cap")

    client = Client([READ, READ, EDIT], before_call=provider)
    settings = Settings()
    settings.fix_rounds = 0
    wf = Workflow(statement(), repo.root, env(tmp_path), client, settings)
    holder["wf"] = wf
    wf.run()
    assert wf.store.best() is None and client.n == 2
    assert not any("finalization round" in line for line in wf.log)


def test_H_SHELL_15_a_candidate_from_the_driver_skips_the_finalization_round(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    client = Client([EDIT, FINISH])
    settings = Settings()
    settings.fix_rounds = 0
    wf = Workflow(statement(), repo.root, env(tmp_path), client, settings)
    wf.run()
    assert wf.store.best() is not None and not any("finalization round" in line for line in wf.log)


def test_H_SHELL_15_long_baseline_preserves_time_for_recovery(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    now = [0.0]
    holder = {}

    def provider(n):
        if n == 1:
            now[0] = holder["wf"].clock.deadline - holder["wf"].settings.finalize_min_sec
            raise LLMError("driver attempt consumed its time slice")

    client = Client([EDIT, FINISH], before_call=provider)
    wf = Workflow(statement(), repo.root, env(tmp_path), client, Settings(fix_rounds=0))
    holder["wf"] = wf
    wf.clock = Clock(1500, now=lambda: now[0])
    wf.baseline_checks = lambda: now.__setitem__(0, 525.0)
    deadlines = []
    complete = client.complete

    def record_deadline(*args, **kwargs):
        deadlines.append(kwargs["deadline"])
        return complete(*args, **kwargs)

    client.complete = record_deadline
    gate = wf.gate

    def gate_with_overhead(*args):
        result = gate(*args)
        now[0] += 0.5
        return result

    wf.gate = gate_with_overhead
    wf.run()
    assert deadlines[0] <= wf.clock.deadline - wf.settings.finalize_min_sec
    assert wf.store.best() is not None


def test_H_SHELL_15_finalization_tools_use_the_finalization_timer(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    now = [0.0]

    def provider(n):
        if n == 1:
            now[0] = 1200.0  # the original driver timer is now expired; the run still has 225 s
            raise LLMError("driver deadline")

    client = Client([[('shell', {'command': 'probe-final-timeout'})], EDIT, FINISH], before_call=provider)
    wf = Workflow(statement(), repo.root, env(tmp_path), client, Settings(fix_rounds=0))
    wf.clock = Clock(1500, now=lambda: now[0])
    run = wf.runner.run
    timeouts = []

    def record_timeout(command, **kwargs):
        if command == "probe-final-timeout":
            timeouts.append(kwargs["timeout"])
            return ProcResult(0, "ok")
        return run(command, **kwargs)

    wf.runner.run = record_timeout
    wf.run()
    assert timeouts and timeouts[0] > 5
    assert wf.store.best() is not None


def test_H_SHELL_15_empty_tree_skips_redundant_checks_before_recovery(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = Workflow(statement(), repo.root, env(tmp_path), Client([FINISH]), Settings())
    wf.prepare()

    def unexpected_check(_label):
        raise AssertionError("an empty patch must not spend recovery time on unchanged checks")

    wf.run_checks = unexpected_check
    report, failures, checks = wf.gate(tool_ctx(repo.root), "r0")
    assert not report.diff.strip() and failures == [] and checks is None


def test_H_LOOP_07_multiple_finish_calls_in_one_reply_cannot_bypass_refusal(tmp_path):
    write(str(tmp_path), "m.py", M)
    loop, _ = loop_for(str(tmp_path), Client([FINISH + FINISH, READ, FINISH]))
    assert loop.run([]).turns == 3


def test_H_LOOP_07_refused_finish_does_not_leave_a_stale_target_symbol(tmp_path):
    write(str(tmp_path), "m.py", M)
    step = [('finish', {'summary': 'premature', 'symbol': 'wrong_symbol'})]
    client = Client([step, READ])
    loop, ctx = loop_for(str(tmp_path), client)
    loop.max_turns = 2
    loop.run([])
    assert not ctx.finished and not ctx.summary and not ctx.target_symbol


def test_H_LOOP_07_empty_finish_is_accepted_when_the_next_request_is_unaffordable(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    client = Client([FINISH])
    wf = Workflow(statement(), repo.root, env(tmp_path), client, Settings())
    wf.wallet.charge(wf.settings.driver.model, {"cost": wf.wallet.spendable - 0.000001})
    loop, ctx = loop_for(repo.root, client)
    loop.can_continue = lambda messages: wf.can_afford_turn(messages, loop.registry)
    outcome = loop.run([])
    assert outcome.turns == 1 and ctx.finished and not loop.empty_finish_refused


def test_H_SHELL_15_real_driver_phase_budget_can_spend_the_finalization_reserve(make_repo, tmp_path):
    repo = make_repo({"m.py": M})
    wf = Workflow(statement(), repo.root, env(tmp_path), settings=Settings(fix_rounds=0))
    replies = iter([(READ, 0.219), (EDIT, 0.003), (FINISH, 0.001)])

    def transport(url, body, headers, timeout):
        calls, cost = next(replies)
        return 200, json.dumps({
            "choices": [{"message": {"content": "", "tool_calls": [
                {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
                for i, (name, args) in enumerate(calls)
            ]}}],
            "usage": {"cost": cost},
        })

    wf.client.transport = transport
    patch = wf.handoff(wf.run())
    assert "return 2" in patch and not wf.repo.changed().all_paths()
    assert wf.repo.apply_check_worktree(patch).ok
    assert wf.wallet.by_phase["driver"] == 0.219
    assert wf.wallet.by_phase["finalize"] == 0.004
    assert not wf.wallet.spent and wf.wallet.accounting_complete


def test_H_LOOP_07_finish_then_edit_in_one_reply_is_not_mistaken_for_empty(tmp_path):
    write(str(tmp_path), "m.py", M)

    def changed():
        return "return 2" in (tmp_path / "m.py").read_text()

    loop, ctx = loop_for(str(tmp_path), Client([FINISH + EDIT]), changed=changed)
    assert loop.run([]).turns == 1 and ctx.finished and not loop.empty_finish_refused
