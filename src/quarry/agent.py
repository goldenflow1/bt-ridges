"""Entry point: agent_main(input) -> unified diff of the change made in the current repository."""

from __future__ import annotations

import os

from quarry.shell import run_agent


def agent_main(input: dict) -> str:
    statement = str((input or {}).get("problem_statement") or "")
    diff = run_agent(statement, os.getcwd())
    if not diff.strip():
        raise RuntimeError("no change was produced")
    return diff
