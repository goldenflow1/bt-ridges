"""The tool-calling driver loop: bounded by turns, time, budget and stalls; keeps the transcript compact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from quarry.clock import PhaseTimer
from quarry.llm import LLMError, ModelRoute, estimate_tokens
from quarry.tools import ToolContext, ToolRegistry
from quarry.wallet import BudgetExhausted

NUDGE = "Continue with tool calls. When the change is complete and verified, call `finish`."
KEEP_RECENT = 8


@dataclass
class LoopOutcome:
    reason: str  # finished | deadline | budget | llm-error | stalled | max-turns
    turns: int
    detail: str = ""


class DriverLoop:
    def __init__(
        self,
        client,
        route: ModelRoute,
        registry: ToolRegistry,
        ctx: ToolContext,
        timer: PhaseTimer,
        max_turns: int = 40,
        compact_tokens: int = 40_000,
        pinned: int = 2,
        role: str = "driver",
    ):
        self.client = client
        self.route = route
        self.registry = registry
        self.ctx = ctx
        self.timer = timer
        self.max_turns = max_turns
        self.compact_tokens = compact_tokens
        self.pinned = pinned
        self.role = role

    def run(self, messages: List[Dict]) -> LoopOutcome:
        stalls = 0
        schemas = self.registry.schemas()
        for turn in range(1, self.max_turns + 1):
            if self.ctx.finished:
                return LoopOutcome("finished", turn - 1)
            if self.timer.expired():
                return LoopOutcome("deadline", turn - 1)
            self.compact(messages)
            try:
                reply = self.client.complete(
                    messages, self.route, tools=schemas, role=self.role, timeout=180.0, deadline=self.timer.end
                )
            except BudgetExhausted as exc:
                return LoopOutcome("budget", turn - 1, str(exc))
            except LLMError as exc:
                return LoopOutcome("llm-error", turn - 1, str(exc))
            messages.append(reply.message)
            if not reply.tool_calls:
                stalls += 1
                if stalls >= 3:
                    return LoopOutcome("stalled", turn)
                messages.append({"role": "user", "content": NUDGE})
                continue
            stalls = 0
            for call in reply.tool_calls:
                if self.timer.expired():
                    output = "skipped: the time for this phase is over"
                else:
                    output = call.error or self.registry.dispatch(self.ctx, call.name, call.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            if self.timer.expired() and not self.ctx.finished:
                return LoopOutcome("deadline", turn)
            if self.ctx.finished:
                return LoopOutcome("finished", turn)
        return LoopOutcome("max-turns", self.max_turns)

    def compact(self, messages: List[Dict]) -> Optional[int]:
        """Shrink old tool outputs once the transcript is too large. Pinned messages are never touched."""
        if estimate_tokens(messages) <= self.compact_tokens:
            return None
        shrunk = 0
        for message in messages[self.pinned:-KEEP_RECENT]:
            if message.get("role") == "tool" and len(message.get("content") or "") > 200:
                first = (message["content"].splitlines() or [""])[0][:160]
                message["content"] = f"{first}\n[older output compacted]"
                shrunk += 1
        return shrunk
