"""v004 B2/B3: finalization notice, empty-finish refusal (H-LOOP-06/07) and the finalization round (H-SHELL-15)."""

from quarry.clock import Clock
from quarry.llm import ChatResult, ModelRoute, ToolCall
from quarry.loop import DriverLoop
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
    ctx = tool_ctx(root)
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
