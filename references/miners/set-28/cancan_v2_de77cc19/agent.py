#!/usr/bin/env python3
"""Generated standalone Ridges agent submission."""

# --- foundation/config.py ---
from __future__ import annotations
import ast
import builtins
import collections
import hashlib
import importlib.machinery
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
FALLBACK_BASE_URL = "https://openrouter.ai/api/v1"
SYNTAX_CHECKS = {
    ".exs": ["elixir", "-e", "Code.string_to_quoted!(File.read!({path}))"],
    ".sh": ["bash", "-n"],
    ".py": [sys.executable, "-c", "import sys; compile(open(sys.argv[1], 'rb').read(), sys.argv[1], 'exec')"],
    ".go": ["gofmt", "-e"],
    ".js": ["node", "--check"],
    ".php": ["php", "-l"],
    ".rb": ["ruby", "-c"],
    ".lua": ["luac", "-p"],
    ".mjs": ["node", "--check"],
    ".cjs": ["node", "--check"],
    ".pl": ["perl", "-c"],
    ".bash": ["bash", "-n"],
    ".ex": ["elixir", "-e", "Code.string_to_quoted!(File.read!({path}))"],
}
SYNTAX_MARKERS = {
    ".exs": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
    ".ex": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
}
DRIVER_MODEL = os.getenv("RIDGES_AGENT_MODEL", "~openai/gpt-luna-latest")
RELIEF_MODEL = os.getenv("RIDGES_RELIEF_MODEL", "deepseek/deepseek-v4-pro-0813")
PLAN_MODEL = os.getenv("RIDGES_PLAN_MODEL", "~openai/gpt-luna-latest")
SCOUT_MODEL = os.getenv("RIDGES_SCOUT_MODEL", "~openai/gpt-luna-latest")
TRIAL_MODEL = os.getenv("RIDGES_TRIAL_MODEL", "~openai/gpt-luna-latest")
SEAT_CACHE_TERMS = {
    "tencent/hy3": (0.0330e-6, 262_144),
    "openai/gpt-5.6-luna": (0.0200e-6, 400_000),
    "deepseek/deepseek-v4-pro": (0.0036e-6, 1_048_576),
    "minimax/minimax-m3": (0.0750e-6, 204_800),
    "xiaomi/mimo-v2.5": (0.0050e-6, 262_144),
    "@preset/luna-high": (0.0200e-6, 400_000),
    "deepseek/deepseek-v4-pro-0813": (0.0220e-6, 1_048_576),
    "qwen/qwen3.8-2.4t-a95b": (0.2500e-6, 1_000_000),
    "google/gemini-3.7-flash": (0.0375e-6, 1_048_576),
    "minimax/minimax-m2.5": (0.0500e-6, 204_800),
    "@preset/qwen38-24t-lowthink": (0.2500e-6, 1_000_000),
    "~openai/gpt-luna-latest": (0.0200e-6, 400_000),
    "deepseek/deepseek-v4-flash-0731": (0.0280e-6, 1_048_576),
    "xiaomi/mimo-v2.5-pro": (0.0050e-6, 262_144),
    "openai/gpt-5.6-terra": (0.2000e-6, 400_000),
}
UNKNOWN_CACHE_TERMS = (0.1000e-6, 131_072)
MODEL_PRICING = {
    "tencent/hy3": (0.132e-6, 0.528e-6),
    "deepseek/deepseek-v4-flash-0731": (0.440e-6, 1.320e-6),
    "google/gemini-3.7-flash": (0.375e-6, 1.875e-6),
    "openai/gpt-5.6-terra": (2.000e-6, 12.000e-6),
    "@preset/luna-high": (0.200e-6, 1.200e-6),
    "minimax/minimax-m2.5": (0.150e-6, 0.900e-6),
    "xiaomi/mimo-v2.5": (0.140e-6, 0.280e-6),
    "deepseek/deepseek-v4-pro-0813": (0.660e-6, 1.980e-6),
    "qwen/qwen3.8-2.4t-a95b": (2.000e-6, 6.000e-6),
    "openai/gpt-5.6-luna": (0.200e-6, 1.200e-6),
    "minimax/minimax-m3": (0.375e-6, 1.500e-6),
    "@preset/qwen38-24t-lowthink": (2.000e-6, 6.000e-6),
    "~openai/gpt-luna-latest": (0.200e-6, 1.200e-6),
    "xiaomi/mimo-v2.5-pro": (0.600e-6, 1.201e-6),
}
UNKNOWN_TOKEN_PRICE = (1.0e-6, 4.0e-6)
TRANSCRIPT_SPEND_SHARE = 0.35
TURNS_PLANNED = 50
CHARS_PER_TOKEN = 3.5
TRANSCRIPT_FLOOR_CHARS = 40_000
DEFAULT_COST_LIMIT_USD = 0.29
DEFAULT_WALL_SEC = 1500.0
COST_SHARE = 0.88
WALL_SHARE = 0.90
WALL_RESERVE_SEC = 45.0
SECOND_PASS_MIN_CLOCK_SEC = 700.0
SECOND_PASS_ROOM_FACTOR = 1.25
SECOND_PASS_PICK_RESERVE_SEC = 120.0
SECOND_PASS_MIN_MONEY_USD = 0.06
PICK_MAX_PATCH_CHARS = 24_000
TURN_CEILING = 150
FIRST_EDIT_DEADLINE_TURN = 8
PLAN_READ_BUDGET = 150_000
PLAN_TURN_CAP = 40
PLAN_SPEND_SHARE = 0.75
PLAN_NOTE_CHARS = 4_000
SCOUT_READ_BUDGET = 60_000
SCOUT_TURN_CAP = 10
SCOUT_CARD_CHARS = 6_000
SCOUT_MAX_USD = 0.02
SCOUT_MIN_MONEY_USD = 0.10
SCOUT_MIN_CLOCK_SEC = 500.0
SCOUT_STATEMENT_CHARS = 18_000
SCOUT_QUOTE_CHARS = (8, 1200)
TRIAL_READ_BUDGET = 60_000
TRIAL_TURN_CAP = 12
TRIAL_RUNS_MAX = 3
TRIAL_MAX_USD = 0.03
TRIAL_MIN_MONEY_USD = 0.05
TRIAL_MIN_CLOCK_SEC = 330.0
TRIAL_FINISH_RESERVE_SEC = 180.0
TRIAL_MAX_SEC = 480.0
TRIAL_SIDE_MIN_SEC = 20.0
TRIAL_COMMAND_SEC = 150.0
TRIAL_FILES_MAX = 3
TRIAL_FILE_CHARS = 20_000
TRIAL_OUTPUT_CHARS = 2_000
TRIAL_PATCH_CHARS = 24_000
TRIAL_EVIDENCE_FILE_CHARS = 3_000
TRIAL_EVIDENCE_TAIL_CHARS = 600
PICK_EVIDENCE_CHARS = 12_000
WRAPUP_TURN = TURN_CEILING // 5
EDIT_PRESSES_MAX = 3
BLANK_REPLY_CEILING = 3
REPEAT_READ_CEILING = 2
REPLY_TOKEN_CEILING = 16000
REASONING_EFFORT = (os.getenv("RIDGES_REASONING_EFFORT") or "").strip().lower()
REQUEST_ATTEMPTS = 16
OLD_REQUEST_ATTEMPTS = 4
OLD_REFUSED_SWEEP_BENCH = 2
RETRY_TALLY = {"unusable": 0, "limited": 0, "quiet": 0, "retried": 0,
               "walled": 0, "recovered": 0, "unreachable": 0, "ladders": 0,
               "old_would_exhaust": 0, "old_would_bench": 0}
SEAT_REFUSED_WAIT_SEC = 20.0
# OpenRouter reserves the requested completion allowance for every concurrent
# request. A 402 in_flight_budget_exhausted response is a temporary concurrency
# refusal, not evidence that the account has no credit. Retry that response on
# the same messages so a validator burst does not end a run with an empty tree.
INFLIGHT_RETRIES = 6
INFLIGHT_BACKOFF_SECONDS = (8.0, 16.0, 30.0, 45.0, 60.0, 60.0)
SEAT_CALL_TIMEOUT_SEC = 240.0
CALL_CLOCK_SHARE = 0.34
SEAT_RETRY_FLOOR_SEC = 20.0
SEAT_RETRY_NAP_CEILING_SEC = 15.0
SEAT_UNUSABLE_NAP_SEC = 1.0
SEAT_QUIET_HANDOVER = 2
LIMIT_SWEEP_BENCH = 3
PRELOCATE_BUDGET_SEC = 60.0
PRELOCATE_TERM_SEC = 20.0
SHELL_BUDGET_CEILING_SEC = 180.0
READ_OUTPUT_CAP = 24_000
SEARCH_HEAD_LIMIT = 250
SHELL_OUTPUT_CAP = 8_000
SEARCH_OUTPUT_CAP = 8_000
TEMPERATURE = 0.0
BACKGROUND_POLL_WAIT_SEC = 20.0
ENVELOPE_JUNK = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache|\.tox|node_modules|\.cache|"
    r"\.DS_Store|nohup\.out)(/|$)|\.(pyc|pyo|pyd|orig|rej|bak|swp|log)$|(^|/)var/log/")
DISCOVERY_BUDGET_SEC = 60.0
SQL_OUTPUT_CAP = 12_000
STATED_FAST_FAIL_SEC = 30.0
STATED_BASELINE_SEC = 900.0
STATED_HOLD_SEC = 420.0
STATED_HOLD_MIN_ROOM_SEC = 600.0
STATED_RECHECK_SEC = 300.0
STATED_TAIL_CHARS = 900



# --- foundation/primitives.py ---

# reply_fingerprint / compact_text / reasoning_tokens / prompt_split normalize Seat usage.
# is_finite_number / coerce_integer / bounded_count sanitize wild provider numbers.

def reply_fingerprint(message: dict) -> str:
    import hashlib
    calls = (message or {}).get("tool_calls") if isinstance(message, dict) else None
    parts = []
    for call in calls if isinstance(calls, list) else []:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict):
            function = {}
        parts.append("%s(%s)" % (function.get("name") or "", function.get("arguments") or ""))
    content = message.get("content") if isinstance(message, dict) else ""
    said = "\n".join(parts) if parts else str(content or "")
    return hashlib.sha256(said.encode("utf-8", "replace")).hexdigest()[:8]

def compact_text(value: object) -> str:
    return " ".join(str(value or "").split())

def is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value == value and value not in (float("inf"), float("-inf"))

def coerce_integer(value: object) -> int:
    return int(value) if is_finite_number(value) else -1

COUNT_CEILING = 100_000_000

def bounded_count(value: object) -> int:
    return min(COUNT_CEILING, max(0, coerce_integer(value)))

def reasoning_tokens(usage: dict) -> int:
    details = (usage or {}).get("completion_tokens_details")
    return coerce_integer(details.get("reasoning_tokens")
                        if isinstance(details, dict) else None)

def prompt_split(usage: dict) -> tuple:
    usage = usage or {}
    total = usage.get("prompt_tokens")
    details = usage.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    total, cached = coerce_integer(total), coerce_integer(cached)
    if total < 0:
        return -1, cached
    return (total - cached if 0 <= cached <= total else total), cached

# read_env_flag / read_numeric_env / log_message are the env+log triad for RIDGES_* toggles.
# Prefer these over raw os.getenv so defaults stay consistent on cold start.

def read_env_flag(name: str, default: str = "1") -> bool:
    return (os.getenv(name) or default).strip().lower() not in ("0", "no", "off", "false", "")

TOOL_CALL_ID_NORMALISATION = read_env_flag("RIDGES_TOOL_CALL_ID_NORMALISATION", "1")
PARALLEL_TOOLS = read_env_flag("RIDGES_PARALLEL_TOOLS", "1")
REPLACE_ALL = read_env_flag("RIDGES_REPLACE_ALL")
ASYNC_SHELL = read_env_flag("RIDGES_ASYNC_SHELL")
PRELOCATE = read_env_flag("RIDGES_PRELOCATE", "1")
SWEEP_WORKFLOW = read_env_flag("RIDGES_SWEEP_WORKFLOW", "1")
TRANSCRIPT_CAP = read_env_flag("RIDGES_TRANSCRIPT_CAP")
SUBMISSION_WARDEN = read_env_flag("RIDGES_SUBMISSION_WARDEN", "0")
WARDEN_ASK = read_env_flag("RIDGES_WARDEN_ASK", "0")
LEDGER_READBACK = read_env_flag("RIDGES_LEDGER_READBACK", "0")
SHAPE_HINTS = read_env_flag("RIDGES_SHAPE_HINTS")
FOLD_ANCHORS = read_env_flag("RIDGES_FOLD_ANCHORS", "0")
MOVE_VERBATIM = read_env_flag("RIDGES_MOVE_VERBATIM")
SUBMIT_CONFORM = read_env_flag("RIDGES_SUBMIT_CONFORM", "0")
PLAN_SEAT = read_env_flag("RIDGES_PLAN_SEAT", "0")
SCOUT_SEAT = read_env_flag("RIDGES_SCOUT_SEAT", "0")
TRIAL = read_env_flag("RIDGES_TRIAL", "0")
SUITE_SCOPE = read_env_flag("RIDGES_SUITE_SCOPE", "0")
SUITE_IMPORTLIB = read_env_flag("RIDGES_SUITE_IMPORTLIB", "0")
SUITE_SHIM = read_env_flag("RIDGES_SUITE_SHIM", "0")
NETWORK_FENCE = read_env_flag("RIDGES_NETWORK_FENCE", "1")
SEARCH_LIMIT = read_env_flag("RIDGES_SEARCH_LIMIT", "0")
OUTLINE = read_env_flag("RIDGES_OUTLINE", "1")
FINDING_MAP = read_env_flag("RIDGES_FINDING_MAP", "0")
INVARIANT_BRIEF = read_env_flag("RIDGES_INVARIANT_BRIEF")
STATED_CHECKS = read_env_flag("RIDGES_STATED_CHECKS")
SCOPE_GATE = read_env_flag("RIDGES_SCOPE_GATE", "1")
DB_PROBE = read_env_flag("RIDGES_DB_PROBE", "0")
ADAPTIVE_DB_CONTEXT = read_env_flag("RIDGES_ADAPTIVE_DB_CONTEXT", "1")
PATCH_ENVELOPE = read_env_flag("RIDGES_PATCH_ENVELOPE", "1")
SECOND_PASS = read_env_flag("RIDGES_SECOND_PASS", "0")
SCOPE_READ = read_env_flag("RIDGES_SCOPE_READ", "0")
SCOPE_PUT_BACK = read_env_flag("RIDGES_SCOPE_PUT_BACK", "0")
CONTRACT_EDIT_NOTES = read_env_flag("RIDGES_CONTRACT_EDIT_NOTES", "1")
GO_BUILD_CHECK = read_env_flag("RIDGES_GO_BUILD_CHECK", "0")

def read_numeric_env(name: str, default: float) -> float:
    try:
        value = float((os.getenv(name) or "").strip())
    except (TypeError, ValueError):
        return default
    return value if value == value and value not in (float("inf"), float("-inf")) else default

# log_message is the one-line operator logger used by Beacon, Seat, Tree, and RUN.
# Suite and seat paths should re-check Allowance.clock_left mid-wait.
# Tool replies must stay JSON-serializable dicts for Seat transcript append.
# Git and shell side effects stay inside Tree/Shell — not in pure parsers.
# Statement parsers only read task text; they do not invent grader rules.
# Shim and fence paths must keep artifacts under the repository root.
# Related helpers nearby share Tree/Allowance/Beacon patterns.
# Prefer extending existing helpers over duplicating logic in the main loop.
# Timeouts and caps here are module-level constants near the file top.
# Suite and seat paths should re-check Allowance.clock_left mid-wait.
# Tool replies must stay JSON-serializable dicts for Seat transcript append.
# Git and shell side effects stay inside Tree/Shell — not in pure parsers.
# Statement parsers only read task text; they do not invent grader rules.
# Shim and fence paths must keep artifacts under the repository root.
# Related helpers nearby share Tree/Allowance/Beacon patterns.
# Prefer extending existing helpers over duplicating logic in the main loop.
# Timeouts and caps here are module-level constants near the file top.
# Suite and seat paths should re-check Allowance.clock_left mid-wait.
# Tool replies must stay JSON-serializable dicts for Seat transcript append.
# Git and shell side effects stay inside Tree/Shell — not in pure parsers.
# Statement parsers only read task text; they do not invent grader rules.
# Shim and fence paths must keep artifacts under the repository root.
# Related helpers nearby share Tree/Allowance/Beacon patterns.
# Prefer extending existing helpers over duplicating logic in the main loop.
# Timeouts and caps here are module-level constants near the file top.
# Suite and seat paths should re-check Allowance.clock_left mid-wait.
# Tool replies must stay JSON-serializable dicts for Seat transcript append.
# Git and shell side effects stay inside Tree/Shell — not in pure parsers.
# Statement parsers only read task text; they do not invent grader rules.
# Shim and fence paths must keep artifacts under the repository root.
# Related helpers nearby share Tree/Allowance/Beacon patterns.
# Prefer extending existing helpers over duplicating logic in the main loop.
# Timeouts and caps here are module-level constants near the file top.
# Suite and seat paths should re-check Allowance.clock_left mid-wait.
# Tool replies must stay JSON-serializable dicts for Seat transcript append.

def log_message(message: str) -> None:
    try:
        print(message, flush=True)
    except (OSError, ValueError):
        pass


# --- platform/repository.py ---

GIT_TIMED_OUT = 124
GIT_COMMAND = os.getenv("RIDGES_GIT_COMMAND") or shutil.which("git") or "git"
_RUNTIME_DEADLINE: float | None = None

def run_git_command(args: list[str], cwd: str, timeout: float = 60.0) -> tuple[int, str]:
    if _RUNTIME_DEADLINE is not None:
        timeout = min(timeout, _RUNTIME_DEADLINE - time.monotonic())
    if timeout <= 0:
        return GIT_TIMED_OUT, "git deadline exhausted"
    try:
        done = subprocess.run(
            [GIT_COMMAND] + args,
            cwd=cwd,
            capture_output=True,
            timeout=max(0.01, timeout),
        )
    except subprocess.TimeoutExpired:
        return GIT_TIMED_OUT, "git timed out"
    except Exception as error:
        return 1, "%s: %s" % (type(error).__name__, error)
    if done.returncode == 0:
        return 0, (done.stdout or b"").decode("utf-8", "surrogateescape")
    return done.returncode, ((done.stdout or b"") + (done.stderr or b"")).decode("utf-8", "replace")

class Tree:
    def __init__(self, root: str) -> None:
        self.root = root
        code, out = run_git_command(["rev-parse", "HEAD"], root, 30)
        self.base = out.strip() if code == 0 else ""
        self.untracked_at_start = self._untracked() or set()
        self.written: list = []
        self.restored = False

    def _untracked(self, budget: float = 30.0) -> set | None:
        code, out = run_git_command(["ls-files", "--others", "--exclude-standard", "-z"],
                        self.root, max(1.0, budget))
        return {p for p in out.split("\0") if p} if code == 0 else None

    def absolute(self, path: str) -> str:
        root = os.path.realpath(self.root)
        joined = os.path.realpath(os.path.join(root, path))
        if os.path.commonpath([root, joined]) != root:
            raise ToolFault("path escapes the repository: %s" % path)
        rel = os.path.relpath(joined, root).replace("\\", "/")
        if ".git" in rel.split("/"):
            raise ToolFault("Git metadata is not an editable source path")
        return joined

    def read(self, path: str) -> str:
        full = self.absolute(path)
        if not os.path.isfile(full):
            raise ToolFault("no such file: %s" % path)
        with open(full, "r", encoding="utf-8", errors="strict", newline="") as handle:
            return handle.read()

    def write(self, path: str, text: str) -> None:
        full = self.absolute(path)
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        if path not in self.written:
            self.written.append(path)

    def diff(self, budget: float = 60.0) -> str:
        started = time.monotonic()
        out = self.whole_diff(budget)
        if out.strip() or not self.written:
            return out
        left = max(DIFF_FALLBACK_FLOOR_SEC, budget - (time.monotonic() - started))
        kept = self.diff_written(left)
        if kept.strip():
            log_message("[TREE] the whole-tree diff did not come back; handed in the %d file(s) this run wrote"
                % kept.count("diff --git "))
        return kept

    def diff_written(self, budget: float) -> str:
        deadline = time.monotonic() + max(1.0, budget)
        paths = [p for p in self.written if os.path.exists(os.path.join(self.root, p))]
        if not paths:
            return ""
        run_git_command(["add", "-N", "--"] + paths, self.root, max(1.0, (deadline - time.monotonic()) / 3))
        args = ["diff", "--binary", "--no-color"] + ([self.base] if self.base else []) + ["--"] + paths
        code, out = run_git_command(args, self.root, max(1.0, deadline - time.monotonic()))
        return out if code == 0 else ""

    def whole_diff(self, budget: float = 60.0) -> str:
        deadline = time.monotonic() + budget

        def left(floor: float = 1.0) -> float:
            return max(floor, deadline - time.monotonic())
        listed = self._untracked(left())
        paths = sorted((listed or set()) - self.untracked_at_start)
        marked, said = run_git_command(["add", "-N", "--"] + paths, self.root, left()) if paths else (0, "")
        if marked != 0 and self._unlock(said):
            marked, said = run_git_command(["add", "-N", "--"] + paths, self.root, left())
        if marked != 0:
            log_message("[TREE] new files could not be marked and may be missing "
                "from the diff: %s" % said.strip()[:200])
        args = ["diff", "--binary", "--no-color"] + ([self.base] if self.base else [])
        code, out = run_git_command(args, self.root, left())
        if code != 0:
            if deadline - time.monotonic() < 10.0:
                log_message("[TREE] diff failed (%s) and there is no time to ask again: %s"
                    % (code, out.strip()[:200]))
                return ""
            log_message("[TREE] diff failed (%s), retrying once: %s" % (code, out.strip()[:200]))
            code, out = run_git_command(args, self.root, left())
            if code != 0:
                log_message("[TREE] diff failed again: %s" % out.strip()[:200])
                return ""
        return out

    def applies(self, patch: str, budget: float = 30.0) -> bool | None:
        if not patch.strip():
            log_message("[PATCH] empty: the run finished without changing a line")
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="ridges-patch-", suffix=".diff")
        except OSError as error:
            log_message("[PATCH] could not be written out for checking: %s" % error)
            return None
        try:
            with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                fh.write(patch)
            code, out = run_git_command(["apply", "--check", path], self.root, budget)
        except OSError as error:
            log_message("[PATCH] could not be filled for checking: %s" % error)
            return None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if code == 0:
            log_message("[PATCH] applies cleanly")
            return True
        if code == GIT_TIMED_OUT:
            log_message("[PATCH] could not be checked in time")
            return None
        log_message("[PATCH] will not apply: %s" % out.strip()[:200])
        return False

    def salvage(self, patch: str, budget: float = 45.0) -> str:
        deadline = time.time() + max(1.0, budget)
        parts = split_by_file(patch)
        if len(parts) < 2:
            log_message("[PATCH] nothing to salvage: %d section(s)" % len(parts))
            return ""
        kept, dropped, unread = [], 0, 0
        for part in parts:
            left = deadline - time.time()
            answer = self.applies_quietly(part, left) if left > 0 else None
            if answer is None:
                unread = len(parts) - len(kept) - dropped
                log_message("[PATCH] salvage left %d section(s) unread" % unread)
                break
            if answer:
                kept.append(part)
            else:
                dropped += 1
        if not kept:
            log_message("[PATCH] salvage kept nothing of %d section(s)" % len(parts))
            return ""
        joined = "".join(kept)
        whole = self.applies_quietly(joined, max(1.0, deadline - time.time()))
        if whole is None:
            log_message("[PATCH] salvage could not re-check its %d section(s)"
                % len(kept))
            return ""
        if not whole:
            log_message("[PATCH] salvage kept %d section(s) that will not apply together"
                % len(kept))
            return ""
        log_message("[PATCH] salvaged %d of %d section(s), dropped %d, unread %d"
            % (len(kept), len(parts), dropped, unread))
        return joined

    def applies_quietly(self, patch: str, budget: float) -> bool | None:
        if not patch.strip():
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="ridges-part-", suffix=".diff")
        except OSError:
            return None
        try:
            with os.fdopen(handle, "w", encoding="utf-8",
                           errors="surrogateescape") as fh:
                fh.write(patch)
            code, _ = run_git_command(["apply", "--check", path], self.root, budget)
        except OSError:
            return None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if code == GIT_TIMED_OUT:
            return None
        return code == 0

    def _unlock(self, said: str) -> bool:
        # A lock file alone is not evidence that its owner has stopped.
        return False

    def restore(self, budget: float = 60.0) -> bool:
        deadline = time.monotonic() + budget
        args = (["reset", "--hard", self.base] if self.base
                else ["checkout", "--", "."])
        code, out = run_git_command(args, self.root, budget)
        if code != 0 and self._unlock(out):
            code, out = run_git_command(args, self.root, max(1.0, deadline - time.monotonic()))
        if code != 0:
            log_message("[TREE] restore said: %s" % out.strip()[:200])
        listed = self._untracked(max(1.0, deadline - time.monotonic()))
        added = ((listed - self.untracked_at_start) if listed is not None
                 else set())
        gone = 0
        for path in sorted(added, key=len, reverse=True):
            try:
                full = self.absolute(path)
            except ToolFault:
                continue
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                gone += 1
            except OSError as error:
                log_message("[TREE] could not remove %s: %s" % (path, error))
        vouched = code == 0 and listed is not None and gone == len(added)
        self.restored = vouched
        log_message("[TREE] restored to %s, removed %d of %d path(s) the run created%s"
            % (self.base[:8] or "?", gone, len(added),
               "" if vouched else " -- not confirmed"))
        return vouched

class ToolFault(Exception):
    pass


# --- platform/database.py ---
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file, optionally a line range. Prefer a range once you know where you are looking. A read that does not fit stops early and the header says where to start again.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the repository root."},
                    "start": {"type": "integer", "description": "First line, 1-based."},
                    "count": {"type": "integer", "description": "How many lines to return."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Extended-regex search across tracked files. Use mode=files first to see where the matches are, then read narrowly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "Directory or file to search under. Defaults to the whole repository."},
                    "mode": {
                        "type": "string",
                        "enum": ["content", "files", "count"],
                        "description": "content returns matching lines, files returns paths only, count returns per-file totals.",
                    },
                    "include": {"type": "string", "description": "Only search paths matching this glob, e.g. *.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "List tracked files whose path matches a glob, e.g. src/**/*.py",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace an exact span of text in a file. Set replace_all when the same span occurs at several places and every one of them needs the same change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string", "description": "Exact text to find, including indentation."},
                    "new": {"type": "string", "description": "Replacement text."},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace every occurrence instead of requiring a unique one.",
                    },
                },
                "required": ["path", "old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Write a whole file, creating it or overwriting it.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the repository root. Set background for anything slow, such as a test suite, and collect it later with bash_poll instead of waiting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "background": {"type": "boolean"},
                    "timeout": {"type": "integer", "description": "Seconds to wait when not backgrounded."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash_poll",
            "description": "Collect output from a background command started with bash. It waits up to 20 seconds for the job to finish before returning, so do not poll in a tight loop.",
            "parameters": {
                "type": "object",
                "properties": {"job": {"type": "string"}},
                "required": ["job"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sql",
            "description": "Run SQL against the live database found for this repository (PostgreSQL via psql, ClickHouse via clickhouse-client or HTTP). Every PostgreSQL call runs inside one transaction that is rolled back afterwards, so you can insert scenario rows, run the query and read the result without changing the database; do not send BEGIN, COMMIT or ROLLBACK yourself. ClickHouse has no rollback, so statements that change its data or schema are refused; build scenario rows inline instead (SELECT ... FROM values('id UInt32, ts DateTime', (1, '2024-01-01 00:00:00')), numbers(n)), or use CREATE TEMPORARY TABLE within the same call. explain=true wraps a PostgreSQL statement in EXPLAIN (ANALYZE, BUFFERS, VERBOSE), or prefixes EXPLAIN indexes=1 on ClickHouse. Multiple statements are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "database": {"type": "string", "description": "Connection label or database name from the list you were given; defaults to the one with tables."},
                    "explain": {"type": "boolean"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": "Finish the run. Call it only after the statement's own check commands pass on the changed tree and you have verified the query's behaviour yourself.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]

def tool_schema(name: str) -> dict:
    return next(t["function"] for t in TOOL_SCHEMAS if t["function"]["name"] == name)

if SEARCH_LIMIT:
    _search = tool_schema("search_text")
    _search["parameters"]["properties"].update({
        "context": {"type": "integer",
                    "description": "Lines of surrounding code to return with each "
                                   "match, up to 20. Enough of them and the match "
                                   "is the read."},
        "head_limit": {"type": "integer",
                       "description": "Stop after this many matching lines "
                                      "(default %d)." % SEARCH_HEAD_LIMIT},
    })
    _search["description"] += (" Ask for context lines rather than following the "
                               "match with a read of the whole file.")
if OUTLINE:
    TOOL_SCHEMAS.append({
        "type": "function",
        "function": {
            "name": "outline",
            "description": "Index one Python file: every class and function in it "
                           "with the lines it spans, and nothing of what they say. "
                           "Call it before reading a long file, then read the range "
                           "it names.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    })
DOLLAR_QUOTED = re.compile(r"\$(\w*)\$.*?\$\1\$", re.S)
SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
TRANSACTION_VERB = re.compile(
    r"\s*(BEGIN|START\s+TRANSACTION|COMMIT|END|ROLLBACK|ABORT|PREPARE\s+TRANSACTION)\b(.*)", re.I | re.S)
CLICKHOUSE_WRITE = re.compile(
    r"^\s*(INSERT|ALTER|DELETE|UPDATE|DROP|TRUNCATE|CREATE|RENAME|OPTIMIZE|SYSTEM|KILL|GRANT|REVOKE|"
    r"ATTACH|DETACH|EXCHANGE|UNDROP|REPLACE|MOVE|BACKUP|RESTORE)\b", re.I)
DATABASE_CLIENT = re.compile(r"\b(?:psql|clickhouse-client|clickhouse\s+client)\b")
SHELL_SQL_WRITE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+[\w.\"`]+\s+SET|DELETE\s+FROM|TRUNCATE\b|"
    r"DROP\s+(?:TABLE|INDEX|VIEW|SCHEMA|DATABASE|FUNCTION|TRIGGER|MATERIALIZED|DICTIONARY)|"
    r"ALTER\s+(?:TABLE|INDEX|VIEW|SCHEMA|DATABASE|ROLE|USER)|"
    r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|VIEW|SCHEMA|DATABASE|FUNCTION|TRIGGER|MATERIALIZED|ROLE|USER|DICTIONARY|OR\s+REPLACE)|"
    r"GRANT\b|REVOKE\b|OPTIMIZE\s+TABLE|COPY\s+[\w.\"]+\s+FROM)", re.I)

def sql_statements(query: str) -> list:
    bare = SQL_COMMENT.sub(" ", DOLLAR_QUOTED.sub(" ", query or ""))
    return [s for s in bare.split(";") if s.strip()]

def transaction_control(query: str) -> str:
    if re.search(r"^\s*\\(?:c|connect)\b", query or "", re.M):
        return "\\connect"
    for statement in sql_statements(re.sub(r"^[ \t]*\\[^\n]*", " ", query or "", flags=re.M)):
        match = TRANSACTION_VERB.match(statement)
        if not match:
            continue
        if match.group(1).upper() == "ROLLBACK" and re.match(r"\s*(?:WORK\s+|TRANSACTION\s+)?TO\b", match.group(2), re.I):
            continue
        return " ".join(match.group(1).split()).upper()
    return ""

def temporary_tables(query: str) -> set:
    return {name.lower() for name in re.findall(
        r"\bCREATE\s+(?:TEMP|TEMPORARY)\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)", query or "", re.I)}

def clickhouse_write(query: str) -> str:
    scratch = temporary_tables(query)
    for statement in sql_statements(query):
        match = CLICKHOUSE_WRITE.match(statement)
        if not match:
            continue
        verb = match.group(1).upper()
        if verb == "CREATE" and re.match(r"\s*CREATE\s+TEMPORARY\s+TABLE\b", statement, re.I):
            continue
        if verb == "SYSTEM" and re.match(r"\s*SYSTEM\s+(?:FLUSH\s+LOGS|DROP\s+(?:\w+\s+)*CACHE)\b", statement, re.I):
            continue
        target = re.match(r"\s*(?:INSERT\s+INTO|DROP\s+(?:TEMPORARY\s+)?TABLE(?:\s+IF\s+EXISTS)?|"
                          r"TRUNCATE(?:\s+TABLE)?(?:\s+IF\s+EXISTS)?)\s+(?:TABLE\s+)?[`\"]?(\w+)", statement, re.I)
        if target and target.group(1).lower() in scratch:
            continue
        return verb
    return ""

def shell_database_write(command: str) -> str:
    if not DATABASE_CLIENT.search(command or ""):
        return ""
    if re.search(r"\bROLLBACK\b", command, re.I) and not re.search(r"\bCOMMIT\b", command, re.I):
        return ""
    scratch = temporary_tables(command)
    for match in SHELL_SQL_WRITE.finditer(command):
        into = re.match(r"INSERT\s+INTO\s+[`\"]?(\w+)", match.group(0) + command[match.end():match.end() + 80], re.I)
        if into and into.group(1).lower() in scratch:
            continue
        return " ".join(match.group(0).split()[:2]).upper()
    return ""

DATABASE_KEPT = ("The live database is left as it was found: %s is not sent to it from here. "
                 "Use the sql tool, where PostgreSQL work runs in a transaction that is rolled "
                 "back, so scenario rows are safe; on ClickHouse build scenario rows inline with "
                 "values(...) or numbers(n), or in a temporary table.")
HINT_MIN_SEC = 40.0
HINT_MIN_SEC_SHORT = 20.0
HINT_STILL = "This was noted when the edit was made, and the change still has it. "
HINT_EDIT_MIN_SEC = 30.0
ENGINE_FACT_MIN_SEC = 30.0
SHORT_WALL_SEC = 600.0
EARLY_EDIT_SHARE = 0.40
DIFF_FALLBACK_FLOOR_SEC = 15.0
HINT_CONTEXT_LINES = 25
WARDEN_READ_CAP_CHARS = 200_000
HINT_NEIGHBOURHOOD_LINES = 3
UPSERT_WRITE = re.compile(
    r"\bON\s+CONFLICT\b|\)\s*DO\s+(?:UPDATE\s+SET|NOTHING)\b|\bON\s+DUPLICATE\s+KEY\s+UPDATE\b", re.I)
COMMENT_LINE = re.compile(r"^\s*(?:#|//|--|/?\*)")
BATCH_ORDER = re.compile(
    r"\bsorted\(|ORDER\s+BY|\.sort\(|\bsort\.(?:Slice|SliceStable|Ints|Strings)\b|slices\.Sort|\.sort_by\b|\.order\(",
    re.I)
FLAG_KEYWORD = re.compile(
    r"\b(\w*(?:flags?|bits))(?:__exact)?\s*=\s*(?![\w.]*\.bit(?:or|and|xor)\b)"
    r"(?:[\w.]*\.mask\b|[\w.]*\bFlag\.\w+|[\w.]*\bFLAG_\w+|\d+\b)")
MASKED_NAME = re.compile(
    r"\b(\w+)\s*=\s*[^,\n=]*?(?:\.bit(?:and|or|xor)\(|"
    r"\bF\([^()]*\)\s*[&|^]|BitAnd\(|BitOr\(|BitXor\()")
FLAG_SQL_COMPARE = re.compile(r"\b\w*flags\s*(?:=|<>|!=)\s*(?:%s|\$\d+|:\w+|\d+)\b(?!\s*[&|])")
QUERY_OPENER = re.compile(r"\.(?:filter|exclude|get|update|exists)\(|\bQ\(")
BUILD_OPENER = re.compile(r"\.(?:create|bulk_create|get_or_create|update_or_create)\(|\b[A-Z][a-z]\w+\(")


# --- platform/shell.py ---
CLIP_NOTE = "\n... [%d characters of %s elided] ...\n"

def clip_output(text: str, cap: int, label: str = "output") -> str:
    if len(text) <= cap:
        return text
    keep = cap
    for _ in range(4):
        room = max(0, cap - len(CLIP_NOTE % (len(text) - keep, label)))
        if room == keep:
            break
        keep = room
    if keep <= 0:
        return (CLIP_NOTE % (len(text), label))[:cap]
    return (text[: keep // 2] + (CLIP_NOTE % (len(text) - keep, label))
            + text[len(text) - (keep - keep // 2):])

SHELL_REPORT_CAP = 120
STILL_RUNNING = "[still running]"

def report_shell(job: "Shell", out: str) -> None:
    tail = ""
    for line in reversed((out or "").splitlines()):
        if line.strip() and line.strip() != STILL_RUNNING:
            tail = line.strip()
            break
    log_message("[SHELL] %.1fs %dc :: %s :: %s"
        % (time.time() - job.started, len(out or ""),
           " ".join(job.command.split())[:SHELL_REPORT_CAP],
           tail[:SHELL_REPORT_CAP]))

FINDING_CHECK = re.compile(r"^\s*ruff\s+check\b")
FINDING_ARROW = re.compile(r"^\s*-->\s+(\S+?):(\d+):\d+\s*$", re.M)
FINDING_CONCISE = re.compile(r"^(\S+?):(\d+):\d+:\s", re.M)
HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")

def relative_path_tail(name: str, root: str = "") -> str:
    text = str(name or "").replace("\\", "/")
    base = str(root or "").replace("\\", "/").rstrip("/")
    if base and text.startswith(base + "/"):
        text = text[len(base) + 1:]
    while text.startswith("./"):
        text = text[2:]
    return text

def findings_from_text(out: str, root: str = "") -> dict:
    text = str(out or "")
    rows: dict = {}
    for pattern in (FINDING_ARROW, FINDING_CONCISE):
        for name, row in pattern.findall(text):
            try:
                number = int(row)
            except ValueError:
                continue
            if number >= 1:
                rows.setdefault(relative_path_tail(name, root), set()).add(number)
        if rows:
            return rows
    return findings_from_json(text, root)

def findings_from_json(text: str, root: str = "") -> dict:
    try:
        items = json.loads(text or "")
    except (TypeError, ValueError):
        return {}
    if not isinstance(items, list):
        return {}
    out: dict = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        where = item.get("location")
        row = where.get("row") if isinstance(where, dict) else None
        name = str(item.get("filename") or "")
        if not name or isinstance(row, bool) or not isinstance(row, int) or row < 1:
            continue
        out.setdefault(relative_path_tail(name, root), set()).add(row)
    return out

def split_by_file(patch: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    for line in (patch or "").splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                out.append("".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        out.append("".join(current))
    return out

def patch_touched_lines(patch: str) -> dict:
    out: dict = {}
    where = ""
    came_from = ""
    old = 0
    left = 0
    right = 0
    for line in (patch or "").splitlines():
        if left <= 0 and right <= 0:
            if line.startswith("diff "):
                where = ""
                came_from = ""
                old = 0
                continue
            if line.startswith("--- "):
                came_from = _diff_side(line[len("--- "):], "a/")
                continue
            if line.startswith("+++ "):
                where = _diff_side(line[len("+++ "):], "b/") or came_from
                continue
            head = HUNK_HEAD.match(line)
            if head:
                old = int(head.group(1))
                left = int(head.group(2) or 1)
                right = int(head.group(3) or 1)
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("-"):
            if where and old:
                out.setdefault(where, set()).add(old)
            old += 1
            left -= 1
        elif line.startswith("+"):
            if where and old:
                out.setdefault(where, set()).add(old)
            right -= 1
        else:
            old += 1
            left -= 1
            right -= 1
    return out

def _diff_side(name: str, prefix: str) -> str:
    text = name.strip()
    if text == "/dev/null" or not text:
        return ""
    if text.startswith(prefix):
        text = text[len(prefix):]
    return relative_path_tail(text)

def finding_distances(findings: dict, touched: dict) -> list:
    out = []
    for where in sorted(touched):
        rows = findings.get(where)
        if not rows:
            continue
        for line in sorted(touched[where]):
            out.append(min(abs(line - row) for row in rows))
    return out

def finding_record(findings: dict, touched: dict) -> str:
    reported = sum(len(rows) for rows in findings.values())
    changed = sum(len(rows) for rows in touched.values())
    silent = sum(1 for where in touched if where not in findings)
    gaps = sorted(finding_distances(findings, touched))
    if not gaps:
        return ("reported %d line(s) over %d file(s); patch changes %d line(s) over "
                "%d file(s), none in a file the check reported"
                % (reported, len(findings), changed, len(touched)))
    return ("reported %d line(s) over %d file(s); patch changes %d line(s), nearest "
            "reported line median=%d p90=%d beyond40=%d of %d; %d file(s) unreported"
            % (reported, len(findings), changed,
               gaps[len(gaps) // 2], gaps[min(len(gaps) - 1, int(len(gaps) * 0.9))],
               sum(1 for gap in gaps if gap > 40), len(gaps), silent))

class FindingMap:
    def __init__(self, root: str) -> None:
        self.root = root
        self.rows: dict = {}
        self.reads = 0
        self.beacon = Beacon("findings")

    def observe(self, command: str, out: str) -> None:
        text = compact_text(command)
        if not FINDING_CHECK.match(text):
            return
        self.reads += 1
        fresh = {where: rows for where, rows in findings_from_text(out, self.root).items()
                 if where not in self.rows}
        if not fresh:
            self.beacon.skipped("nothing new in the output of: %s" % text[:120])
            return
        self.rows.update(fresh)
        self.beacon.fired("%s -> %d line(s) over %d file(s)"
                          % (text[:120], sum(len(rows) for rows in fresh.values()), len(fresh)))

    def report(self, patch: str) -> None:
        if not self.rows:
            self.beacon.skipped("no reading of the check was recorded")
            return
        self.beacon.fired(finding_record(self.rows, patch_touched_lines(patch)))

SHELL_READ_HEAD = 64_000
SHELL_READ_TAIL = 2_000_000
COMMAND_STOPS_FIRST = "{ echo 1000 > /proc/self/oom_score_adj; } 2>/dev/null; "

def command_env() -> dict:
    env = dict(os.environ)
    flags = env.get("GOFLAGS", "")
    if not re.search(r"(?:^|\s)-p(?:=|\s)", flags):
        env["GOFLAGS"] = (flags + " -p=2").strip()
    env.setdefault("GOMAXPROCS", "2")
    return env

class Shell:
    counter = 0

    def __init__(self, command: str, cwd: str) -> None:
        Shell.counter += 1
        self.name = "job%d" % Shell.counter
        self.command = command
        self.started = time.time()
        self.sink = tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", errors="replace", suffix=".out", delete=False
        )
        self.process = subprocess.Popen(
            ["bash", "-lc", COMMAND_STOPS_FIRST + command],
            cwd=cwd,
            stdout=self.sink,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=command_env(),
        )

    def _text(self) -> str:
        try:
            self.sink.flush()
            size = os.path.getsize(self.sink.name)
            if size <= SHELL_READ_HEAD + SHELL_READ_TAIL:
                with open(self.sink.name, "r", encoding="utf-8", errors="replace") as handle:
                    return handle.read()
            with open(self.sink.name, "rb") as handle:
                head = handle.read(SHELL_READ_HEAD)
                handle.seek(size - SHELL_READ_TAIL)
                tail = handle.read(SHELL_READ_TAIL)
        except OSError:
            return ""

        def text(raw: bytes) -> str:
            return raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
        return "%s\n[... %d bytes of output not read back ...]\n%s" % (text(head), size - len(head) - len(tail), text(tail))

    def wait(self, timeout: float) -> tuple:
        if _RUNTIME_DEADLINE is not None:
            timeout = min(timeout, max(0.01, _RUNTIME_DEADLINE - time.monotonic()))
        try:
            self.process.wait(timeout=max(0.01, timeout))
            return True, self._text()
        except subprocess.TimeoutExpired:
            return False, self._text()

    def finished(self) -> bool:
        return self.process.poll() is not None

    def drain(self) -> str:
        if self.process.poll() is None:
            return self._text() + "\n" + STILL_RUNNING
        return self._text()

    def stop(self) -> None:
        if self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (AttributeError, OSError, ProcessLookupError):
                try:
                    self.process.kill()
                except Exception:
                    pass
        try:
            self.sink.close()
            os.unlink(self.sink.name)
        except OSError:
            pass

class ShellPool:
    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.jobs = {}

    def start(self, command: str) -> Shell:
        job = Shell(command, self.cwd)
        self.jobs[job.name] = job
        return job

    def get(self, name: str) -> Shell:
        job = self.jobs.get(name)
        if job is None:
            raise ToolFault("no background job named %s" % name)
        return job

    def close(self) -> None:
        for job in list(self.jobs.values()):
            try:
                report_shell(job, job.drain())
                job.stop()
            except Exception:
                pass
        self.jobs.clear()


# --- analysis/static_analysis.py ---
EMPTY_WINDOW = re.compile(r"\bOVER\s*\(\s*\)", re.I)
BUCKET_GROUPING = re.compile(r"toStartOf\w*\s*\(|\bGROUP\s+BY\b|granularity|bucket", re.I)
PARTITION_BY = re.compile(r"PARTITION\s+BY", re.I)
SLOT_EXPANSION = re.compile(r"\barrayMap\s*\(")
SLOT_RANGE = re.compile(r"\brange\s*\(")
SLOT_STEP = re.compile(r"\b(?:add(?:Seconds|Minutes|Hours|Days)|toInterval(?:Second|Minute|Hour|Day)|fromUnixTimestamp)\s*\(")
SLOT_ROUND_UP = re.compile(r"\bceil(?:ing)?\s*\(|\+\s*(?:59|899|1799|3599|86399)\b|\+\s*\(?\s*\d+\s*-\s*1\s*\)?\s*\)?\s*[,/]")
PICK_ONE = re.compile(r"\brow_number\s*\(\s*\)\s*OVER\b|\bLIMIT\s+\S+\s+BY\b|\barg(?:Max|Min)\s*\(", re.I)
PREWHERE_MOVE = re.compile(r"optimize_move_to_prewhere\W{1,6}1\b|[\"'`]WHERE[\"'`]\s*,\s*[\"'`]PREWHERE[\"'`]", re.I)
UNSTABLE_QUANTILES = {"quantile", "quantiles", "median", "quantileTDigest", "quantilesTDigest", "medianTDigest",
                      "quantileTDigestWeighted", "quantilesTDigestWeighted", "medianTDigestWeighted",
                      "quantileGK", "quantilesGK", "medianGK", "quantileGKWeighted", "quantilesGKWeighted"}
QUANTILE_COMBINATORS = re.compile(r"(?:If|State|Merge|OrNull|OrDefault|Array|ForEach|Distinct|Resample|SimpleState)+$")

def unstable_quantile(text: str) -> str:
    for match in CALL_NAME.finditer(text or ""):
        if (match.start() and text[match.start() - 1] in ".$^") or text[match.end():match.end() + 1] == "?":
            continue
        name = match.group(1)
        if QUANTILE_COMBINATORS.sub("", name) in UNSTABLE_QUANTILES or name in UNSTABLE_QUANTILES:
            return name
    return ""

RELATION_VALUE = re.compile(r"\.(?:select|reselect|where|rewhere|joins|left_joins|reorder|distinct|merge)\b")
LOADED_VALUE = re.compile(r"\.(?:pluck|ids|to_a|map|count|exists\?|first|last|find|take|sum|maximum|minimum)\b")
IN_BIND = re.compile(r"\bIN\s*\(\s*\?\s*\)", re.I)

def line_at(starts: list, index: int) -> int:
    low, high = 0, len(starts) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if starts[middle] <= index:
            low = middle
        else:
            high = middle - 1
    return low

def line_offsets(lines: list) -> list:
    starts, position = [], 0
    for line in lines:
        starts.append(position)
        position += len(line) + 1
    return starts

def float_division_findings(lines: list, added: set) -> list:
    text = "\n".join(lines)
    starts = line_offsets(lines)
    found: list = []
    for match in INTEGER_ARGUMENT_CALL.finditer(text):
        depth, braces, quote, index, quotient, end = 0, 0, "", match.end(), False, None
        while index < len(text):
            char = text[index]
            if quote:
                if char == quote:
                    quote = ""
                index += 1
                continue
            if text.startswith(("${", "#{"), index):
                braces += 1
                index += 2
                continue
            if braces:
                if char == "}":
                    braces -= 1
                index += 1
                continue
            if char in "'\"":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    end = index
                    break
                depth -= 1
            elif (char == "/" and depth == 0 and text[index + 1:index + 2] not in ("/", "*")
                  and text[index - 1:index] != "*"):
                quotient = True
            index += 1
        if end is None or not quotient:
            continue
        first, last = line_at(starts, match.start()), line_at(starts, end)
        if any(first <= offset <= last for offset in added):
            found.append((match.group(1), first))
    return found

def fragment_arity_findings(diff: str) -> list:
    found: list = []
    for start, added, lines in engine_hunks(diff):
        offsets = {offset for offset, _ in added}
        text = "\n".join(lines)
        starts = line_offsets(lines)
        for match in re.finditer(r"\bfragment\(\s*", text):
            index = match.end()
            if text.startswith('\"\"\"', index):
                close = text.find('\"\"\"', index + 3)
                if close < 0:
                    continue
                literal, index = text[index + 3:close], close + 3
            elif text.startswith('"', index):
                close = index + 1
                while close < len(text) and text[close] != '"':
                    close += 2 if text[close] == "\\" else 1
                if close >= len(text):
                    continue
                literal, index = text[index + 1:close], close + 1
            else:
                continue
            placeholders = literal.count("?")
            depth, arguments, current, end = 0, 0, "", None
            while index < len(text):
                char = text[index]
                if char in "([{":
                    depth += 1
                elif char in ")]}":
                    if depth == 0:
                        end = index
                        break
                    depth -= 1
                elif char == "," and depth == 0:
                    arguments += bool(current.strip())
                    current, index = "", index + 1
                    continue
                current += char
                index += 1
            if end is None:
                continue
            arguments += bool(current.strip())
            if placeholders == arguments:
                continue
            first, last = line_at(starts, match.start()), line_at(starts, end)
            if any(first <= offset <= last for offset in offsets):
                found.append(("ex_fragment_arity", "fragment(...) with %d ? placeholder(s) and %d argument(s)"
                              % (placeholders, arguments), start + first))
    return found

def relation_bind_findings(diff: str) -> list:
    found: list = []
    for start, added, lines in engine_hunks(diff):
        offsets = {offset for offset, _ in added}
        relations: set = set()
        for text, first, touched in ruby_statements(lines, offsets):
            assigned = RELATION_ASSIGN.match(text)
            if assigned:
                value = text[assigned.end():]
                if RELATION_VALUE.search(value) and not LOADED_VALUE.search(value):
                    relations.add(assigned.group(1))
                else:
                    relations.discard(assigned.group(1))
            if not touched:
                continue
            for call in re.finditer(r"\bwhere(?:\.not)?\(\s*", text):
                index, literal = call.end(), ""
                while index < len(text) and text[index] in "\"'":
                    quote, close = text[index], index + 1
                    while close < len(text) and text[close] != quote:
                        close += 2 if text[close] == "\\" else 1
                    literal += text[index + 1:close]
                    rest = text[close + 1:].lstrip(" \\")
                    index = len(text) - len(rest)
                if not literal or not IN_BIND.search(literal) or not text.startswith(",", index):
                    continue
                arguments = text[index + 1:]
                bound = next((name for name in sorted(relations, key=len, reverse=True)
                              if re.search(r"(?<![\w.])%s(?![\w])" % re.escape(name), arguments)), None)
                if bound is None and RELATION_VALUE.search(arguments) and not LOADED_VALUE.search(arguments):
                    bound = "the relation passed to where"
                if bound is not None:
                    found.append(("ar_relation_bind", bound, start + first))
                    break
    return found

def engine_fact_findings(diff: str, engine: str, source: str = "") -> list:
    found: list = []
    nulls_in_file = bool(JOIN_USE_NULLS.search(source or ""))
    for start, added, lines in engine_hunks(diff):
        everything = "\n".join(lines)
        real_nulls = nulls_in_file or bool(JOIN_USE_NULLS.search(everything))
        for offset, text in added:
            if CODE_COMMENT.match(text):
                continue
            if engine == "clickhouse":
                test = NULL_TEST.search(text)
                if test and not real_nulls and OUTER_JOIN.search(everything):
                    found.append(("ch_outer_null", test.group(0).rstrip("( "), start + offset))
                if TIME_SLOTS.search(text) and ZONE_WORD.search(everything):
                    found.append(("ch_time_slots", "timeSlots", start + offset))
                if (EMPTY_WINDOW.search(text) and (BUCKET_GROUPING.search(everything)
                                                   or BUCKET_GROUPING.search(source or ""))
                        and not PARTITION_BY.search(everything)):
                    found.append(("ch_window_bucket", "OVER ()", start + offset))
                round_up = SLOT_ROUND_UP.search(text)
                if (round_up and SLOT_EXPANSION.search(everything) and SLOT_RANGE.search(everything)
                        and SLOT_STEP.search(everything)):
                    found.append(("ch_slot_count", round_up.group(0).strip(" ,/"), start + offset))
                pick = PICK_ONE.search(text)
                if pick and PREWHERE_MOVE.search(source or everything):
                    found.append(("ch_prewhere_pick", " ".join(pick.group(0).split()), start + offset))
                estimate = unstable_quantile(text)
                if estimate:
                    found.append(("ch_quantile_unstable", estimate, start + offset))
                window = " ".join([text] + lines[offset + 1:offset + 3])
                coarse = coarse_ngram_index(window, source)
                if coarse and " ".join(window.split()).find(coarse) < len(" ".join(text.split())):
                    found.append(("ch_skip_index", coarse, start + offset))
            if engine in ("postgresql", "") and distinct_order_mismatch(text):
                found.append(("pg_distinct_order", text.strip()[:60], start + offset))
        if engine == "clickhouse":
            for name, line in float_division_findings(lines, {offset for offset, _ in added}):
                found.append(("ch_float_division", name, start + line))
    return found

NAME_CHECK = read_env_flag("RIDGES_NAME_CHECK")
NAME_CHECK_MAX_FILES = 12
MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__package__", "__spec__", "__loader__", "__builtins__",
                  "__path__", "__all__", "__dict__", "__annotations__", "__cached__", "__debug__", "__class__",
                  "__qualname__", "__module__"}
NAME_NOTE = ("`%s` is used at %s:%d, and nothing in that module binds it: no import, definition or assignment, "
             "and %s. Python raises NameError the moment that line runs, and neither compiling the file nor "
             "a lint that ignores star imports can see it. Import the name explicitly, or reach it through a "
             "module the file already binds.")

def bound_names(tree) -> set:
    bound: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != "*":
                    bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.MatchAs) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
    return bound

def annotation_nodes(tree) -> set:
    skip: set = set()
    for node in ast.walk(tree):
        parts = []
        if isinstance(node, ast.arg) and node.annotation is not None:
            parts.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            parts.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            parts.append(node.annotation)
        for part in parts:
            skip.update(id(n) for n in ast.walk(part))
    return skip

def dynamic_module(tree) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__":
            return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("exec", "eval", "globals", "vars", "locals", "__import__"):
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("__dict__",) and isinstance(node.value, ast.Name):
            return True
    return False

def star_sources(tree) -> list:
    return [(node.level, node.module or "") for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)]

def module_file(root: str, path: str, level: int, module: str) -> str | None:
    if level:
        base = os.path.dirname(path)
        for _ in range(level - 1):
            base = os.path.dirname(base)
    else:
        base = ""
    parts = [p for p in module.split(".") if p] if module else []
    candidates = []
    stem = os.path.join(base, *parts) if parts else base
    candidates.append(stem + ".py")
    candidates.append(os.path.join(stem, "__init__.py"))
    if not level:
        for top in sorted({p.split("/")[0] for p in [path] if "/" in p}):
            candidates.append(os.path.join(top, *parts) + ".py")
            candidates.append(os.path.join(top, *parts, "__init__.py"))
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(root, candidate)):
            return candidate
    return None

def literal_all(tree) -> set | None:
    found = None
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AugAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        if not isinstance(value, (ast.List, ast.Tuple)) or not all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts):
            return None
        names = {e.value for e in value.elts}
        found = names if found is None or isinstance(node, ast.Assign) else found | names
    return found if found is not None else set()

def star_exports(root: str, path: str, seen: set | None = None) -> set | None:
    seen = set() if seen is None else seen
    if path in seen:
        return set()
    seen.add(path)
    try:
        tree = ast.parse(open(os.path.join(root, path), encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError, ValueError):
        return None
    if dynamic_module(tree):
        return None
    declared = literal_all(tree)
    has_all = any(isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and any(
        isinstance(t, ast.Name) and t.id == "__all__"
        for t in (n.targets if isinstance(n, ast.Assign) else [n.target])) for n in tree.body)
    if declared is None:
        return None
    if has_all:
        return declared
    exported = {name for name in top_level_names(tree) if not name.startswith("_")}
    for level, module in star_sources(tree):
        target = module_file(root, path, level, module)
        if target is None:
            return None
        more = star_exports(root, target, seen)
        if more is None:
            return None
        exported |= more
    return exported

def top_level_names(tree) -> set:
    names: set = set()

    def visit(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.name != "*":
                        names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                visit(getattr(node, "body", []))
                visit(getattr(node, "orelse", []))
                visit(getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    visit(handler.body)
    visit(tree.body)
    return names

def unbound_names(root: str, path: str, source: str, lines: set) -> list:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    if dynamic_module(tree):
        return []
    bound = bound_names(tree) | MODULE_DUNDERS | set(dir(builtins))
    skip = annotation_nodes(tree)
    gaps = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.lineno in lines
                and node.id not in bound and id(node) not in skip):
            gaps.append((node.id, node.lineno))
    if not gaps:
        return []
    stars = star_sources(tree)
    why = "the module has no star import"
    if stars:
        exported: set = set()
        for level, module in stars:
            target = module_file(root, path, level, module)
            if target is None:
                return []
            names = star_exports(root, target)
            if names is None:
                return []
            exported |= names
        gaps = [(name, line) for name, line in gaps if name not in exported]
        why = "none of its star imports exports it"
    seen: set = set()
    out = []
    for name, line in sorted(gaps, key=lambda g: g[1]):
        if name not in seen:
            seen.add(name)
            out.append((name, line, why))
    return out

def added_line_numbers(diff: str) -> set:
    numbers: set = set()
    current = 0
    for line in (diff or "").splitlines():
        head = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if head:
            current = int(head.group(1))
            continue
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            numbers.add(current)
            current += 1
        elif line.startswith(" "):
            current += 1
    return numbers


# --- platform/model_seats.py ---

# Beacon: telemetry handle for reached/skipped/fired style run-log lines.
# Spent below ends the run when Allowance exhausts budget or wall.

class Beacon:
    def __init__(self, slug: str) -> None:
        self.slug = slug.upper()
        self.calls = 0
        self.usd = 0.0

    def reached(self, step: int, spent: float, clock: float) -> None:
        log_message("[%s] reached step=%d spent=$%.4f clock=%.0fs" % (self.slug, step, spent, clock))

    def skipped(self, reason: str) -> None:
        log_message("[%s] skipped: %s" % (self.slug, reason))

    def fired(self, detail: str) -> None:
        log_message("[%s] fired: %s" % (self.slug, detail[:400]))

    def artefact(self, when: str, blob: str) -> str:
        import hashlib
        digest = hashlib.sha256((blob or "").encode("utf-8", "replace")).hexdigest()[:8]
        log_message("[%s] %s %s %dB" % (self.slug, when, digest, len(blob or "")))
        return digest

    def outcome(self, before_digest: str, after: str) -> None:
        import hashlib
        digest = hashlib.sha256((after or "").encode("utf-8", "replace")).hexdigest()[:8]
        changed = "yes" if digest != before_digest else "no"
        log_message("[%s] after %s %dB changed=%s" % (self.slug, digest, len(after or ""), changed))

    def bill(self) -> None:
        log_message("[%s] cost calls=%d usd=%.4f" % (self.slug, self.calls, self.usd))

class Spent(Exception):
    pass

# Allowance tracks wall, USD, calls, and presses for one agent_main invocation.
# should_press and retry tallies consult it before another Seat ask.

class Allowance:
    quoted_calls = 0

    def __init__(self) -> None:
        self.started = time.monotonic()
        wall = read_numeric_env("AGENT_TIMEOUT", DEFAULT_WALL_SEC)
        self.ceiling_usd = read_numeric_env("RIDGES_MAX_COST_USD", DEFAULT_COST_LIMIT_USD)
        self.soft_usd = self.ceiling_usd * COST_SHARE
        self.wall = wall
        self.deadline = self.started + max(0.0, wall * WALL_SHARE - min(WALL_RESERVE_SEC, wall * 0.15))
        self.spent = 0.0
        self.calls = 0
        self.edits = 0
        self.tests_run = 0

    def clock_left(self) -> float:
        return self.deadline - time.monotonic()

    def total(self) -> float:
        return self.deadline - self.started

    def money_left(self) -> float:
        return self.soft_usd - self.spent

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def halt_reason(self) -> str:
        if self.clock_left() <= 0:
            return "wall clock"
        if self.money_left() <= 0:
            return "budget"
        return ""

    def charge(self, model: str, usage: dict) -> float:
        self.calls += 1
        quoted = usage.get("cost")
        if is_finite_number(quoted) and 0 <= quoted <= self.ceiling_usd:
            self.spent += float(quoted)
            self.quoted_calls += 1
            return float(quoted)
        prompt = bounded_count(usage.get("prompt_tokens"))
        completion = bounded_count(usage.get("completion_tokens"))
        details = usage.get("prompt_tokens_details") or {}
        cached = bounded_count(details.get("cached_tokens")) if isinstance(details, dict) else 0
        fresh = max(0, prompt - cached)
        in_price, out_price = MODEL_PRICING.get(model, UNKNOWN_TOKEN_PRICE)
        cache_price = SEAT_CACHE_TERMS.get(model, UNKNOWN_CACHE_TERMS)[0]
        cost = fresh * in_price + cached * cache_price + completion * out_price
        self.spent += cost
        return cost

def call_ident(call: dict, index: int) -> str:
    ident = call.get("id")
    return ident if isinstance(ident, str) and ident else "call_%d" % index

def recorded_calls(calls: list) -> list:
    kept = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        function = call.get("function")
        function = dict(function) if isinstance(function, dict) else {}
        written = function.get("arguments")
        try:
            if not isinstance(written, str) or not written.strip():
                raise ValueError("nothing was written")
            if not isinstance(json.loads(written), dict):
                raise ValueError("not an object")
        except Exception:
            function["arguments"] = "{}"
        kept.append({"id": call_ident(call, index), "type": "function",
                     "function": function})
    return kept

def normalise_tool_call_ids(calls: list, turn: int) -> int:
    """Give one model turn stable tool-call IDs before recording or dispatch.

    Some OpenAI-compatible providers reuse IDs or emit IDs that are rejected
    when the assistant message and its following tool results are validated as
    a pair.  The same call objects are used for both messages, so normalising
    once here prevents a history mismatch without changing dispatch semantics.
    """
    if not TOOL_CALL_ID_NORMALISATION:
        return 0
    changed = 0
    for index, call in enumerate(calls, 1):
        if not isinstance(call, dict):
            continue
        stable = "call_g_t%d_i%d" % (turn, index)
        if call.get("id") != stable:
            call["id"] = stable
            changed += 1
    return changed

def transcript_cap_chars(model: str, ceiling_usd: float) -> int:
    cache_price, window = SEAT_CACHE_TERMS.get(model, UNKNOWN_CACHE_TERMS)
    affordable = (ceiling_usd * TRANSCRIPT_SPEND_SHARE) / (TURNS_PLANNED * cache_price)
    tokens = min(affordable, window * 0.6)
    return int(max(TRANSCRIPT_FLOOR_CHARS, tokens * CHARS_PER_TOKEN))

FINISH_REASONS = ("stop", "length", "tool_calls", "content_filter", "error", "")

def extract_foreign_text(text: str) -> str:
    body = "" if text is None else str(text)
    return "%dB" % len(body.encode("utf-8", "replace")) if body else "empty"

def reply_shape(parsed, error) -> str:
    reason = str(error) if isinstance(error, Spent) else type(error).__name__
    parts = []
    if isinstance(parsed, dict):
        fields = sorted(k for k in parsed if isinstance(k, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", k))
        parts.append("fields=%s" % (",".join(fields[:8]) or "none"))
        if isinstance(parsed.get("choices"), list):
            parts.append("choices=%d" % len(parsed["choices"]))
        problem = parsed.get("error")
        if isinstance(problem, dict):
            for field in ("code", "status", "type"):
                value = problem.get(field)
                if isinstance(value, bool):
                    continue
                if isinstance(value, int):
                    parts.append("error.%s=%d" % (field, value))
                elif isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", value):
                    parts.append("error.%s=%s" % (field, value))
            detail = problem.get("metadata")
            provider = detail.get("provider_name") if isinstance(detail, dict) else None
            if isinstance(provider, str) and re.fullmatch(r"[A-Za-z0-9 _.-]{1,40}", provider.strip()):
                parts.append("error.provider=%s" % provider.strip().replace(" ", "_"))
            if problem.get("message"):
                parts.append("error.message=%s" % extract_foreign_text(problem.get("message")))
        elif problem is not None:
            parts.append("error=%s" % extract_foreign_text(problem))
    elif parsed is not None:
        parts.append("json=%s" % type(parsed).__name__)
    return "%s [%s]" % (reason, " ".join(parts)) if parts else reason

def configured_server(conn) -> bool:
    return not str(conn.label).startswith("guess:") and conn.host not in ("", "localhost", "127.0.0.1", "::1")

class SeatRefused(Exception):
    pass

class SeatTimedOut(SeatRefused):
    pass

class SeatRateLimited(SeatRefused):
    pass

def base_urls() -> list[str]:
    # Choose one credential/endpoint pair. Never reuse a local provider key
    # while falling through to an unrelated endpoint.
    local = (os.getenv("RIDGES_INFERENCE_BASE_URL") or "").strip().rstrip("/")
    if local or os.getenv("RIDGES_INFERENCE_PROVIDER"):
        return [local or FALLBACK_BASE_URL]
    injected = (os.getenv("OPENROUTER_BASE_URL") or "").strip().rstrip("/")
    if injected:
        return [injected]
    proxy = (os.getenv("SANDBOX_PROXY_URL") or "").strip().rstrip("/")
    return [proxy + "/api/v1" if proxy else FALLBACK_BASE_URL]

class Seat:
    roster: list = []
    patient = True

    def __init__(self, allowance: Allowance, models: list | None = None,
                 patient: bool = True) -> None:
        self.allowance = allowance
        self.patient = patient
        if models:
            self.models = list(models)
        else:
            self.models = [DRIVER_MODEL]
            if RELIEF_MODEL and RELIEF_MODEL != DRIVER_MODEL:
                self.models.append(RELIEF_MODEL)
        self.roster = list(self.models)
        self.timeouts: dict = {}
        self.bases = base_urls()
        self.reply_serial = 0
        self.key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("RIDGES_OPENROUTER_API_KEY")
            or os.getenv("AI_PROXY_KEY")
            or ""
        )
        if os.getenv("RIDGES_INFERENCE_PROVIDER") or os.getenv("RIDGES_INFERENCE_BASE_URL"):
            self.key = os.getenv("RIDGES_INFERENCE_API_KEY") or ""

    def current(self) -> str:
        return self.models[0]

    def retire(self, model: str) -> bool:
        if model in self.models and len(self.models) > 1:
            self.models.remove(model)
            if model in self.roster:
                self.roster.remove(model)
            log_message("[SEAT] retired %s, now on %s" % (model, self.models[0]))
            return True
        return False

    def ask(self, messages: list[dict], tools: list[dict] | None) -> dict:
        budget = self._budget()
        aside: list[str] = []
        try:
            return self._ask(messages, tools, budget, aside)
        finally:
            for model in reversed(aside):
                if model not in self.models and model in self.roster:
                    self.models.insert(0, model)
            if aside:
                log_message("[SEAT] %s back on: a limit is the key's state, not the seat's"
                    % ", ".join(aside))

    def _ask(self, messages: list[dict], tools: list[dict] | None,
             budget, aside: list) -> dict:
        # A rejected endpoint must not consume the entire run in outer retries.
        for sweep in range(2):
            if self.allowance.halt_reason():
                raise Spent(self.allowance.halt_reason())
            model = self.current()
            try:
                return self._attempt(model, messages, tools, budget)
            except SeatRefused as refusal:
                log_message("[SEAT] %s refused: %s" % (model, str(refusal)[:200]))
                if (isinstance(refusal, SeatTimedOut)
                        and self.timeouts.get(model, 0) >= 2
                        and self.retire(model)):
                    continue
                if len(self.models) > 1:
                    self.models.remove(model)
                    if isinstance(refusal, SeatRateLimited):
                        if model not in aside:
                            aside.append(model)
                    elif model in aside:
                        aside.remove(model)
                    log_message("[SEAT] benched %s, now on %s" % (model, self.models[0]))
                    continue
                if isinstance(refusal, SeatTimedOut):
                    raise Spent("every seat went quiet: %s" % refusal)
                if not self.patient:
                    raise
                wait = SEAT_REFUSED_WAIT_SEC
                if (self.allowance.clock_left() - wait
                        < SEAT_RETRY_FLOOR_SEC + 10.0):
                    raise Spent("no seat will serve this run")
                log_message("[SEAT] every seat refused; asking again in %.0fs" % wait)
                time.sleep(wait)
                self.models = list(self.roster)
                budget = self._budget()
        raise Spent("provider retry budget exhausted")

    def _budget(self):
        left = self.allowance.clock_left()
        share = min(max(0.0, left - 10.0), SEAT_CALL_TIMEOUT_SEC,
                    max(30.0, left * CALL_CLOCK_SHARE))
        return share, time.monotonic(), left

    def _attempt(self, model: str, messages: list[dict], tools: list[dict] | None,
                 budget=None, inflight_state: dict | None = None) -> dict:
        if inflight_state is None:
            inflight_state = {"retries": 0}
        body = {
            "model": model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": REPLY_TOKEN_CEILING,
        }
        if REASONING_EFFORT:
            body["reasoning"] = {"effort": REASONING_EFFORT, "exclude": True}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        backoff = 3.0
        sweep: list[str] = []
        refusal = ""
        refused_sweeps = 0
        timed_out = 0
        unreachable = 0
        unusable = 0
        unusable_seen = 0
        last_unusable = ""
        last_spoken = ""
        old_refused = 0
        old_bench_at = 0
        all_limits = False
        walls_seen = 0
        limits_seen = 0
        quiet_sweeps = 0
        old_dead_base = bool((os.getenv("SANDBOX_PROXY_URL") or "").strip().rstrip("/"))
        RETRY_TALLY["ladders"] += 1
        attempts = REQUEST_ATTEMPTS if self.patient else 1
        ceiling = SEAT_CALL_TIMEOUT_SEC if self.patient else 60.0
        share, began, started_with = budget if budget else self._budget()

        def spent_share() -> float:
            return max(time.monotonic() - began,
                       started_with - self.allowance.clock_left())

        def handover_reserve() -> float:
            return SEAT_RETRY_FLOOR_SEC + 5.0 if len(self.models) > 1 else 0.0

        def room_left() -> float:
            return min(share - spent_share() - handover_reserve(),
                       self.allowance.clock_left() - 10)

        def room_now() -> float:
            return min(share - spent_share(), self.allowance.clock_left() - 10)
        for attempt in range(attempts):
            if self.allowance.clock_left() <= 5 or self.allowance.money_left() <= 0:
                raise Spent("allowance exhausted mid-request")
            asked = 0
            walled = 0
            quiet = 0
            unusable = 0
            limited = 0
            sweep = []
            granted = ceiling
            for base in self.bases:
                room = room_left()
                if room < SEAT_RETRY_FLOOR_SEC:
                    break
                asked += 1
                parsed = None
                try:
                    request = urllib.request.Request(
                        base + "/chat/completions", data=payload, headers=headers
                    )
                    with urllib.request.urlopen(
                            request, timeout=min(granted, room_now())) as response:
                        parsed = json.loads(response.read().decode("utf-8", "replace"))
                except urllib.error.HTTPError as error:
                    try:
                        detail = error.read()[:400].decode("utf-8", "replace")
                    except Exception:
                        detail = ""
                    finally:
                        try:
                            error.close()
                        except Exception:
                            pass
                    sweep.append("%s %s" % (error.code, extract_foreign_text(detail)))
                    lowered = detail.lower()
                    inflight = error.code == 402 and any(marker in lowered for marker in (
                        "in_flight_budget_exhausted",
                        "in-flight requests",
                        "in flight requests",
                    ))
                    if inflight:
                        inflight_retry = int(inflight_state.get("retries", 0))
                        if inflight_retry >= INFLIGHT_RETRIES:
                            raise Spent(
                                "temporary in-flight allowance remained busy after %d retries"
                                % INFLIGHT_RETRIES
                            )
                        retry_after = 0.0
                        try:
                            retry_after = float(error.headers.get("Retry-After", "0"))
                        except (AttributeError, TypeError, ValueError):
                            pass
                        # Delay jitter comes from the prompt so two validators do not
                        # wake on the same instant. The messages themselves stay put.
                        seed = json.dumps(messages[:2], sort_keys=True,
                                          default=str).encode("utf-8")
                        jitter = (sum(seed) % 2000) / 1000.0
                        delay = max(
                            retry_after,
                            INFLIGHT_BACKOFF_SECONDS[inflight_retry] + jitter,
                        )
                        if self.allowance.clock_left() <= delay + WALL_RESERVE_SEC + 30.0:
                            raise Spent(
                                "temporary in-flight allowance outlasted safe retry window"
                            )
                        inflight_state["retries"] = inflight_retry + 1
                        log_message("[SEAT] in-flight allowance busy; retry %d/%d in %.1fs"
                            % (inflight_retry + 1, INFLIGHT_RETRIES, delay))
                        time.sleep(delay)
                        return self._attempt(model, messages, tools, None, inflight_state)
                    if error.code in (401, 403, 404):
                        walled += 1
                        continue
                    if error.code in (400, 402, 413):
                        raise Spent("endpoint refused the request: " + sweep[-1])
                    if error.code == 429 and ("budget" in detail.lower() or "cost" in detail.lower()):
                        raise Spent("allowance exhausted upstream")
                    if error.code == 429:
                        limited += 1
                        walled += 1
                        continue
                except Exception as error:
                    reason = getattr(error, "reason", None)
                    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
                        timed_out += 1
                        quiet += 1
                        sweep.append("timed out after %.0fs" % min(granted, room_now()))
                    else:
                        unreachable += 1
                        sweep.append("%s: %s" % (type(error).__name__, extract_foreign_text(error)))
                if parsed is not None:
                    try:
                        booked = self._book(model, parsed)
                    except Spent:
                        raise
                    except Exception as error:
                        unusable += 1
                        unusable_seen += 1
                        last_unusable = reply_shape(parsed, error)
                        sweep.append("unusable reply: %s" % last_unusable)
                        continue
                    if unusable_seen:
                        log_message("[SEAT] %s answered after %d unusable repl%s; the last: %s"
                            % (model, unusable_seen, "y" if unusable_seen == 1 else "ies", last_unusable))
                    if attempt:
                        self._tally(attempt, old_bench_at, recovered=True)
                    return booked
            RETRY_TALLY["walled"] += walled
            RETRY_TALLY["quiet"] += quiet
            RETRY_TALLY["unreachable"] += unreachable
            RETRY_TALLY["unusable"] += unusable
            RETRY_TALLY["limited"] += limited
            walls_seen += walled
            limits_seen += limited
            unreachable = 0
            if old_dead_base and asked and not quiet:
                old_refused += 1
                if old_refused >= OLD_REFUSED_SWEEP_BENCH and not old_bench_at:
                    old_bench_at = attempt + 1
            if asked and walled and not quiet:
                refused_sweeps += 1
                refusal = " | ".join(sweep)
                all_limits = limits_seen >= walls_seen
                rope = 2
                if all_limits and room_left() >= SEAT_RETRY_FLOOR_SEC * 3:
                    rope = LIMIT_SWEEP_BENCH
                if refused_sweeps >= rope:
                    self._tally(attempt, old_bench_at, recovered=False)
                    if all_limits:
                        raise SeatRateLimited(refusal)
                    raise SeatRefused(refusal)
            if quiet:
                quiet_sweeps += 1
            if (quiet_sweeps >= SEAT_QUIET_HANDOVER and len(self.models) > 1
                    and room_left() >= SEAT_RETRY_FLOOR_SEC):
                self.timeouts[model] = self.timeouts.get(model, 0) + 1
                self._tally(attempt, old_bench_at, recovered=False)
                raise SeatTimedOut("%d quiet sweep(s) in %d attempt(s): %s"
                                   % (quiet_sweeps, attempt + 1,
                                      " | ".join(sweep) or last_spoken))
            if sweep:
                last_spoken = " | ".join(sweep)
            if attempt + 1 >= attempts or room_left() < SEAT_RETRY_FLOOR_SEC:
                break
            only_unusable = bool(asked) and unusable == asked
            nap = min(SEAT_UNUSABLE_NAP_SEC if only_unusable else backoff,
                      max(0.0, self.allowance.clock_left() - 5),
                      max(0.0, room_left() - SEAT_RETRY_FLOOR_SEC))
            if nap <= 0:
                break
            time.sleep(nap)
            if not only_unusable:
                backoff = min(backoff * 2, SEAT_RETRY_NAP_CEILING_SEC)
        said = " | ".join(sweep) or last_spoken or "no base was asked"
        if timed_out:
            self.timeouts[model] = self.timeouts.get(model, 0) + 1
            if attempt:
                self._tally(attempt, old_bench_at, recovered=False)
            raise SeatTimedOut("%d timeout(s) in %d attempt(s): %s"
                               % (timed_out, attempt + 1, said))
        if attempt:
            self._tally(attempt, old_bench_at, recovered=False)
        if len(self.models) > 1 and (share - spent_share()) >= SEAT_RETRY_FLOOR_SEC:
            raise SeatRefused("%s (nothing left on this seat)" % said)
        if (self.patient and len(self.models) == 1
                and self.allowance.clock_left() - SEAT_REFUSED_WAIT_SEC
                >= SEAT_RETRY_FLOOR_SEC + 10.0):
            raise SeatRefused("%s (this share is spent, the run is not)" % said)
        raise Spent("no reply after %d attempts: %s" % (attempt + 1, said))

    def _tally(self, attempt: int, old_bench_at: int, recovered: bool) -> None:
        RETRY_TALLY["retried"] += 1
        if recovered:
            RETRY_TALLY["recovered"] += 1
        was = "carried on"
        if old_bench_at:
            RETRY_TALLY["old_would_bench"] += 1
            was = "benched the seat at sweep %d" % old_bench_at
        elif attempt + 1 > OLD_REQUEST_ATTEMPTS:
            RETRY_TALLY["old_would_exhaust"] += 1
            was = "run out of sweeps at %d" % OLD_REQUEST_ATTEMPTS
        log_message("[RETRY] sweeps=%d recovered=%s old_ladder=%s"
            % (attempt + 1, "yes" if recovered else "no", was))

    def _book(self, model: str, parsed: dict) -> dict:
        if not isinstance(parsed, dict):
            raise ValueError("reply is not an object")
        usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
        quoted_before = self.allowance.quoted_calls
        cost = self.allowance.charge(model, usage)
        if self.allowance.money_left() <= 0:
            raise Spent("inference budget exhausted")
        choices = parsed.get("choices") or []
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("reply carried no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("reply carried no message object")
        self.reply_serial += 1
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            calls = [c for c in calls if isinstance(c, dict)]
            for index, call in enumerate(calls):
                call["id"] = "call_%d_%d" % (self.reply_serial, index)
            message["tool_calls"] = calls
        served = compact_text(parsed.get("provider") or parsed.get("served_by"))
        answered = compact_text(parsed.get("model"))
        aside = ""
        if served:
            aside += " via=%s" % served[:40]
        if answered and answered != model:
            aside += " answered=%s" % answered[:60]
        thought = reasoning_tokens(usage)
        if thought >= 0:
            aside += " thought=%d" % thought
        fresh, cached = prompt_split(usage)
        if fresh >= 0:
            aside += " fresh=%d" % fresh
        if cached >= 0:
            aside += " cached=%d" % cached
        out = coerce_integer(usage.get("completion_tokens"))
        if out >= 0:
            aside += " out=%d" % out
        if self.allowance.quoted_calls == quoted_before:
            aside += " est"
        log_message(
            "[SEAT] %s call=%d $%.4f total=$%.4f left=%.0fs said=%s%s"
            % (model, self.allowance.calls, cost, self.allowance.spent,
               self.allowance.clock_left(), reply_fingerprint(message), aside)
        )
        finish = choices[0].get("finish_reason") or ""
        message["_finish"] = finish
        if finish not in ("stop", "tool_calls", ""):
            named = finish if finish in FINISH_REASONS else "other"
            log_message("[SEAT] %s reply ended on %s after %d token(s)"
                % (model, named, bounded_count(usage.get("completion_tokens"))))
        return message


# --- analysis/scope.py ---
STATEMENT_BREAK = re.compile(r"^\s*(?:def |class |@)|^\S")

def statement_span(lines: list, index: int) -> str:
    low = high = index
    while low > 0:
        previous = lines[low - 1]
        if not previous.strip() or STATEMENT_BREAK.match(previous):
            break
        low -= 1
    while high + 1 < len(lines):
        following = lines[high + 1]
        if not following.strip() or STATEMENT_BREAK.match(following):
            break
        high += 1
    return "\n".join(lines[low:high + 1])

DEFINITION_START = re.compile(r"^\s*(?:async\s+def|def|func|fn|function)\b")

def preceding_body(lines: list, index: int) -> str:
    line = lines[index]
    indent = len(line) - len(line.lstrip())
    low = index
    while low > 0:
        previous = lines[low - 1]
        if previous.strip():
            lead = len(previous) - len(previous.lstrip())
            if lead == 0 or (DEFINITION_START.match(previous) and lead < indent):
                break
        low -= 1
    return "\n".join(lines[low:index])

def match_index(pattern, lines: list) -> int:
    for offset, line in enumerate(lines):
        if pattern.search(line):
            return offset
    return 0

def first_match(pattern, start: int, lines: list) -> int:
    for offset, line in enumerate(lines):
        if pattern.search(line):
            return start + offset
    return start

def post_image_hunks(diff: str) -> list:
    return [(start, lines) for start, lines, _ in near_hunks(diff)]

def near_hunks(diff: str) -> list:
    hunks: list = []
    for line in (diff or "").splitlines():
        head = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if head:
            hunks.append((int(head.group(1)), [], []))
            continue
        if not hunks or line.startswith(("+++", "---", "\\")):
            continue
        if line.startswith(("+", "-")):
            if hunks[-1][1] and line.startswith("-"):
                hunks[-1][2][-1] = True
            if line.startswith("+"):
                hunks[-1][1].append(line[1:])
                hunks[-1][2].append(True)
        elif line.startswith(" "):
            hunks[-1][1].append(line[1:])
            hunks[-1][2].append(False)
    return [(start, lines, spread_hunks(touched)) for start, lines, touched in hunks]

def spread_hunks(touched: list) -> list:
    near = list(touched)
    for index, changed in enumerate(touched):
        if not changed:
            continue
        for step in range(-HINT_NEIGHBOURHOOD_LINES, HINT_NEIGHBOURHOOD_LINES + 1):
            if 0 <= index + step < len(near):
                near[index + step] = True
    return near

def near_match(pattern, lines: list, near: list) -> int | None:
    for offset, line in enumerate(lines):
        if near[offset] and pattern.search(line):
            return offset
    return None

def context_store(lines: list, near: list) -> int | None:
    for offset, line in enumerate(lines):
        if not near[offset] or COMMENT_LINE.match(line):
            continue
        match = CONTEXT_STORE.search(line)
        if match and not REQUEST_SCOPED.search(line[match.start():]):
            return offset
    return None

def definition_start(lines: list, index: int) -> int:
    line = lines[index]
    indent = len(line) - len(line.lstrip())
    low = index
    while low > 0:
        previous = lines[low - 1]
        if previous.strip():
            lead = len(previous) - len(previous.lstrip())
            if lead == 0 or (DEFINITION_START.match(previous) and lead < indent):
                break
        low -= 1
    return low

def queryset_or_fallback(lines: list, near: list) -> int | None:
    code = [line if not COMMENT_LINE.match(line) else "" for line in lines]
    hits = [offset for offset, line in enumerate(code) if QUERYSET_OR_MANAGER.search(line)]
    if not hits:
        return None
    for offset, line in enumerate(code):
        if not near[offset] or not line.strip():
            continue
        if line == line.lstrip() or DEFINITION_START.match(line):
            low = offset
        else:
            low = definition_start(code, offset)
        for hit in hits:
            if low <= hit <= offset:
                return hit
    return None

NARROW_LOOKUP = re.compile(r"\b\w+__(?:lt|lte|gt|gte)\s*=")
AGGREGATE_CALL = re.compile(r"\b(?:Sum|Count|Avg|Max|Min|aggregate|SubquerySum|SubqueryCount)\(")
LISTING_OPEN = re.compile(r"\.(?:filter|exclude)\(")
RELATION_PATH = re.compile(r"\bF\(\s*f?['\"](?:\{\w+\})?([A-Za-z_]\w*(?:__[A-Za-z_]\w*)+)['\"]")
PY_COMMENT = re.compile(r"^\s*#")

def diff_hunks_added(diff: str) -> list:
    hunks: list = []
    number = 0
    for line in (diff or "").splitlines():
        head = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if head:
            number = int(head.group(1))
            hunks.append([])
            continue
        if not hunks or line.startswith(("+++", "---", "\\")):
            continue
        if line.startswith("+"):
            hunks[-1].append((number, line[1:], True))
            number += 1
        elif line.startswith(" "):
            hunks[-1].append((number, line[1:], False))
            number += 1
    return hunks

def narrowed_list_query(diff: str) -> int | None:
    owner_of: dict = {}
    for index, hunk in enumerate(diff_hunks_added(diff)):
        owner = ("hunk", index)
        for position, (number, text, added) in enumerate(hunk):
            if DEFINITION_START.match(text):
                owner = ("def", index, position)
            owner_of[(index, position)] = owner
    hunks = diff_hunks_added(diff)
    summing = {owner_of[(index, position)]
               for index, hunk in enumerate(hunks) for position, (_, text, added) in enumerate(hunk)
               if added and AGGREGATE_CALL.search(text) and not PY_COMMENT.match(text)}
    if not summing:
        return None
    for index, hunk in enumerate(hunks):
        for position, (number, text, added) in enumerate(hunk):
            if not added or PY_COMMENT.match(text) or not NARROW_LOOKUP.search(text):
                continue
            if owner_of[(index, position)] in summing:
                continue
            above = "\n".join(line for _, line, _ in hunk[max(0, position - 6):position + 1])
            if LISTING_OPEN.search(above):
                return number
    return None

def factor_off_path(diff: str) -> int | None:
    found: list = []
    for hunk in diff_hunks_added(diff):
        run: list = []
        for number, text, added in hunk + [(0, "", False)]:
            if added and not PY_COMMENT.match(text):
                run.append((number, text))
                continue
            if run:
                joined, starts, offset = "", [], 0
                for line_number, line_text in run:
                    starts.append((offset, line_number))
                    joined += line_text + "\n"
                    offset += len(line_text) + 1
                for match in RELATION_PATH.finditer(joined):
                    where = max(n for o, n in starts if o <= match.start(1))
                    found.append((match.group(1), where))
                run = []
    prefixes: dict = {}
    for path in {path for path, _ in found}:
        prefix = "__".join(path.split("__")[:-1])
        prefixes[prefix] = prefixes.get(prefix, 0) + 1
    shared = [prefix for prefix, count in prefixes.items() if count >= 2]
    if not shared:
        return None
    trunk = max(shared, key=lambda prefix: prefix.count("__")) + "__"
    for path, number in found:
        if path.startswith(trunk) and len(path[len(trunk):].split("__")) >= 2:
            return number
    return None

PERIOD_START_WORDS = {"from": ("to", "until", "till"), "start": ("end", "stop", "finish"), "starts": ("ends",),
                      "begin": ("end",), "begins": ("ends",)}
PERIOD_TIME_WORDS = frozenset(("date", "datetime", "time", "timestamp", "at", "on", "ts", "day", "period", "valid",
                               "effective"))
PERIOD_EQUALITY = re.compile(r"(?<![\w.$@])([A-Za-z_]\w*?)(?:__(?:exact|date))?\s*(?::(?![:=])|=(?![=~>])|=>)")
PERIOD_QUERY_OPEN = re.compile(r"\b(?:where|rewhere|find_by|find_or_create_by|find_or_initialize_by|filter|"
                               r"filter_by|exclude|get|Q|Where|Filter|FilterBy)\s*(?:\(|:\s*\{)")
PERIOD_CARRIES_ON = (",", "(", "[", "{", "\\", "+", "&&", "||", ".", "=")
PERIOD_SQL_WORD = re.compile(r"\b(WHERE|AND|OR|ON(?!\s+CONFLICT)|SET|SELECT|VALUES|BY|WHEN|THEN|ELSE|RETURNING)\b")

def period_end_names(name: str) -> list:
    if "__" in name:
        return []
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)
    lowered = [word.lower() for word in words]
    if len(words) < 2 or "".join(lowered) != name.replace("_", "").lower():
        return []
    if not PERIOD_TIME_WORDS.intersection(lowered):
        return []
    ends = []
    for index, word in enumerate(lowered):
        for other in PERIOD_START_WORDS.get(word, ()):
            swapped = list(words)
            swapped[index] = other.capitalize() if words[index][:1].isupper() else other
            ends.append(("_" if "_" in name else "").join(swapped))
    return ends

def period_value(text: str, end: int) -> str:
    depth, out = 0, []
    for char in text[end:end + 120]:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if not depth:
                break
            depth -= 1
        elif char == "," and not depth:
            break
        out.append(char)
    return "".join(out).strip()

def inside_query_call(text: str, position: int) -> bool:
    for opened in PERIOD_QUERY_OPEN.finditer(text):
        if opened.end() > position:
            break
        depth = 1
        for char in text[opened.end():position]:
            depth += (char in "([{") - (char in ")]}")
            if not depth:
                break
        if depth > 0:
            return True
    return False

def chain_span(lines: list, index: int) -> tuple:
    low = index
    while low > 0 and (lines[low].strip().startswith(".")
                       or lines[low - 1].strip().endswith(PERIOD_CARRIES_ON)):
        low -= 1
    high = index
    while high + 1 < len(lines) and (lines[high + 1].strip().startswith(".")
                                     or lines[high].strip().endswith(PERIOD_CARRIES_ON)):
        high += 1
    return low, high

def period_bound_findings(diff: str, source: str) -> list:
    found: list = []
    hunks: list = []
    for line in (diff or "").splitlines():
        head = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if head:
            hunks.append((int(head.group(1)), [], []))
        elif hunks and not line.startswith(("+++", "---", "\\")) and line[:1] in ("+", " "):
            hunks[-1][1].append(line[1:])
            hunks[-1][2].append(line[:1] == "+")
    for start, lines, added in hunks:
        for index, text in enumerate(lines):
            if not added[index] or CODE_COMMENT.match(text):
                continue
            for match in PERIOD_EQUALITY.finditer(text):
                ends = period_end_names(match.group(1))
                value = period_value(text, match.end())
                if not ends or ".." in value or re.match(r"(?:nil|None|null|NULL)\b", value):
                    continue
                before = "\n".join(lines[max(0, index - 2):index])
                joined = (before + "\n" if before else "") + text
                position = len(joined) - len(text) + match.start(1)
                words = list(PERIOD_SQL_WORD.finditer(joined[:position]))
                condition = (match.group(0).rstrip().endswith("=") and bool(words)
                             and words[-1].group(1) in ("WHERE", "AND", "OR", "ON"))
                if not (condition or inside_query_call(joined, position)):
                    continue
                either = "|".join(re.escape(end) for end in ends)
                low, high = chain_span(lines, index)
                if re.search(r"(?<!\w)(?:%s)(?!\w)" % either, "\n".join(lines[low:high + 1])):
                    continue
                if not re.search(r"(?<![\w.])(?:%s)(?!\w)" % either, source or ""):
                    continue
                found.append(("period_bounds", start + index))
                break
    return found

def shape_findings(diff: str, source: str = "") -> list:
    found: list = []
    hunks = near_hunks(diff)
    head = re.search(r"^\+\+\+ b/(\S+)", diff or "", re.M)
    if head and head.group(1).endswith((".rb", ".rake")):
        for start, lines, near in hunks:
            held = handed_record_lock(lines)
            if held is not None and near[held]:
                found.append(("lock", start + held))
                break
        for start, lines, near in hunks:
            swallowed = heredoc_swallowed_arguments(lines)
            if swallowed is not None and near[swallowed]:
                found.append(("heredoc", start + swallowed))
                break
        for start, lines, near in hunks:
            through = near_match(CLASS_LOCK, lines, near)
            if through is not None:
                found.append(("class_lock", start + through))
                break
    for start, lines, near in hunks:
        code = [line if not COMMENT_LINE.match(line) else "" for line in lines]
        where = near_match(UPSERT_WRITE, code, near)
        if (where is not None and not BATCH_ORDER.search(statement_span(code, where))
                and not BATCH_ORDER.search(preceding_body(code, where))):
            found.append(("upsert", start + where))
        flagged = flag_whole_value(lines)
        if flagged is not None and near[flagged]:
            found.append(("flags", start + flagged))
        bare = near_match(BARE_PREDICATE, lines, near)
        if bare is not None:
            found.append(("predicate", start + bare))
    if head and head.group(1).endswith(".go"):
        for start, lines, near in hunks:
            stored = context_store(lines, near)
            if stored is not None:
                found.append(("ctx_value", start + stored))
                break
    if head and head.group(1).endswith(".py"):
        for start, lines, near in hunks:
            fallback = queryset_or_fallback(lines, near)
            if fallback is not None:
                found.append(("qs_or", start + fallback))
                break
        narrowed = narrowed_list_query(diff)
        if narrowed is not None:
            found.append(("narrow_list", narrowed))
        off_path = factor_off_path(diff)
        if off_path is not None:
            found.append(("factor_path", off_path))
    whole = "\n".join("\n".join(lines) for _, lines, _ in hunks)
    if DB_CASE_FOLD.search(whole):
        for start, lines, near in hunks:
            folded = near_match(APP_CASE_FOLD, lines, near)
            if folded is not None:
                found.append(("case", start + folded))
                break
    if source:
        for kind, line in period_bound_findings(diff, source):
            found.append((kind, line))
            break
    return found

HISTORY_GIT = re.compile(
    r"\bgit\s+(?:-[^\s]+\s+)*(commit|stash|checkout|switch|restore|reset|clean|revert|rebase|merge|cherry-pick|push)\b"
)
NETWORK_COMMAND = re.compile(
    r"(?:^|[|&;]|\$\(|`)\s*(?:sudo\s+)?"
    r"(curl|wget|nc|ncat|telnet|ssh|scp|rsync|ftp|"
    r"git\s+(?:fetch|pull|clone|remote|ls-remote|submodule))(?![\w-])"
)
TEST_PATH = re.compile(
    r"(^|/)conftest\.py$|(^|/)tests?(/|$)|(^|/)test_[^/]*\.py$|_test\.py$")
NOQA_DIRECTIVE = re.compile(r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b", re.I)
FAILED_TEST = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)
PASSED_COUNT = re.compile(r"(\d+) passed")
FENCED_BLOCK = re.compile(r"```(?:[A-Za-z0-9_+-]*)\n(.*?)```", re.S)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
COMMAND_SEPARATOR = frozenset(("&&", "||", "|", "|&", "&", ";", ";;"))
REDIRECT_OPERATOR = frozenset((">", ">>", "<", "<<", "2>", "2>>"))

def statement_lines(statement: str) -> list:
    found: list = []
    for block in FENCED_BLOCK.findall(statement or ""):
        lines = block.splitlines()
        index = 0
        while index < len(lines):
            logical = lines[index]
            while logical.rstrip().endswith("\\") and index + 1 < len(lines):
                index += 1
                logical = logical.rstrip()[:-1] + " " + lines[index].strip()
            index += 1
            text = logical.strip()
            if text.startswith("$ "):
                text = text[2:].strip()
            if text and not text.startswith("#"):
                found.append(text)
    for span in re.findall(r"`([^`]+)`", FENCED_BLOCK.sub(" ", statement or "")):
        text = " ".join(span.replace("\\\n", " ").split())
        if text and text not in found and (RUNNER_LINE.search(text) or LINT_LINE.search(text)):
            found.append(text)
    return found

RUNNER_LINE = re.compile(
    r"(?:^|[\s;&|(])(?:python[0-9.]*\s+(?:-m\s+)?(?:pytest|py\.test|unittest|\S*manage\.py\s+test|django-admin\s+test)"
    r"|pytest|py\.test|\S*manage\.py\s+test|django-admin\s+test"
    r"|go\s+test|mix\s+test|cargo\s+test|dotnet\s+test|make\s+test"
    r"|npm\s+(?:run\s+)?test\S*"
    r"|(?:npm|yarn|pnpm)\s+(?:run\s+)?(?:test|check|verify|spec|unit|integration|e2e"
    r"|jest|vitest|mocha|ava|karma|cypress|playwright)[\w:.@-]*"
    r"|npx\s+(?:jest|vitest|mocha)|jest|vitest|mocha"
    r"|bundle\s+exec\s+(?:rspec|rails\s+test|rake\s+test)|rspec|rails\s+test|rake\s+test"
    r"|phpunit|php\s+artisan\s+test|\./gradlew\s+test|mvn\s+test)(?=\s|$)")
LINT_LINE = re.compile(
    r"(?:^|[\s;&|(])(?:ruff\s+(?:check|format\s+--check)|eslint|npx\s+(?:eslint|tsc)|tsc|mypy|pyright|flake8|black\s+--check"
    r"|isort\s+--check\S*|gofmt|go\s+vet|golangci-lint|staticcheck|rubocop|mix\s+format|mix\s+compile|mix\s+credo"
    r"|sqlfluff|prettier\s+--check|yarn\s+(?:run\s+)?(?:lint|typecheck|tsc)|npm\s+run\s+(?:lint|typecheck))(?=\s|$)")

def stated_checks(statement: str) -> list:
    found: list = []
    for line in statement_lines(statement):
        if LINT_LINE.search(line):
            rest = line.split(None, 1)[1] if " " in line else ""
            if re.search(r"(?:^|\s)[\w./*-]*(?:/[\w.*-]+|\.\w{1,5})(?:\s|$)", rest):
                found.append(("lint", line))
        elif RUNNER_LINE.search(line):
            found.append(("test", line))
    return found

def command_lines(statement: str) -> list:
    found = []
    for line in statement_lines(statement):
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        current = []
        skip = False
        for token in tokens + [";"]:
            if skip:
                skip = False
            elif token in REDIRECT_OPERATOR:
                skip = True
            elif token in COMMAND_SEPARATOR:
                if len(current) > 2 and current[:2] == ["ruff", "check"]:
                    found.append(current)
                current = []
            else:
                current.append(token)
    return found

CHECK_FAILED = (
    re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M),
    re.compile(r"^(?:FAIL|ERROR):\s+(\S+(?:\s+\([^)]*\))?)", re.M),
    re.compile(r"^\s*--- FAIL:\s+(\S+)", re.M),
    re.compile(r"^\s*(?:\u2715|\u00d7|\u2716)\s+(.+?)(?:\s+\(\d+\s*ms\))?\s*$", re.M),
    re.compile(r"^\s*\d+\)\s+(.+?)\s+\([A-Za-z0-9_.]+\)\s*$", re.M),
    re.compile(r"^rspec\s+(\S+)\s+#", re.M),
    re.compile(r"^test\s+(\S+)\s+\.\.\.\s+FAILED", re.M),
    re.compile(r"^FAIL\s+(\S+)\s*$", re.M),
)
CHECK_PASSED = (
    re.compile(r"(\d+) passed"),
    re.compile(r"^Ran (\d+) tests?.*\n+OK", re.M),
    re.compile(r"^ok\s+\S+", re.M),
    re.compile(r"(\d+) tests?, 0 failures"),
    re.compile(r"(\d+) examples?, 0 failures"),
    re.compile(r"test result: ok\. (\d+) passed"),
    re.compile(r"OK \((\d+) tests?"),
)

def failed_names(out: str) -> set:
    names: set = set()
    for pattern in CHECK_FAILED:
        for hit in pattern.findall(out or ""):
            if hit.startswith("("):
                continue
            names.add(compact_text(hit)[:160])
    return names

def passed_count(out: str) -> int:
    text = out or ""
    total = 0
    for pattern in CHECK_PASSED:
        hits = pattern.findall(text)
        if not hits:
            continue
        if pattern.pattern.startswith("^ok"):
            total += len(hits)
        else:
            try:
                total += int(hits[-1])
            except (TypeError, ValueError):
                pass
    return total

def repo_relative(path: str, root: str):
    if not path.startswith("/"):
        return path
    full = os.path.normpath(path)
    for base in dict.fromkeys((os.path.normpath(root), os.path.realpath(root))):
        base = base.rstrip("/") or "/"
        if full == base:
            return None
        if full.startswith(base + "/"):
            return full[len(base) + 1:]
    return None

def scope_targets(statement: str, root: str) -> list:
    found: list = []
    seen: set = set()
    for phrase in SCOPE_PHRASE.finditer(statement or ""):
        for token in re.findall(r"`([^`\s]+)`", phrase.group(1)):
            path = repo_relative(token.strip().rstrip(",;:"), root)
            if not path or "(" in path or path.startswith(("-", "--")) or path in seen:
                continue
            if TEST_PATH.search(path):
                continue
            full = os.path.join(root, path.rstrip("/"))
            if os.path.isfile(full):
                seen.add(path); found.append(("file", path))
            elif os.path.isdir(full) and "/" in path.rstrip("/"):
                seen.add(path); found.append(("dir", path.rstrip("/")))
    return found

def scope_allows(path: str, targets: list) -> bool:
    for kind, target in targets:
        if kind == "file" and path == target:
            return True
        if kind == "dir" and (path == target or path.startswith(target + "/")):
            return True
    return False

SUITE_TALLY = re.compile(r"^=*\s*(\d+ (?:failed|passed|error|errors)[^=]*?)\s*=*$", re.M)
SUITE_REASON = re.compile(r"^\S+\.py:\d+:\s*(\S.*)$", re.M)
SUITE_FAULT = re.compile(r"^E[ \t]+([\w.]*(?:Error|Exception)\w*)\b(.*)$", re.M)
SUITE_TIERS = ("", " --noconftest", " --noconftest --import-mode=importlib")
MISSING_MODULE = re.compile(r"ModuleNotFoundError: No module named '([A-Za-z_][A-Za-z_0-9.]*)'")
MISSING_DIST = re.compile(
    r"^(?:E[ \t]+)?(?:[\w.]+\.)?PackageNotFoundError: "
    r"No package metadata was found for "
    r"([A-Za-z0-9](?:[\w.-]*[A-Za-z0-9])?)[ \t]*$", re.M)
SUITE_SHIM_LIMIT = 6
SUITE_SHIM_MIN_GREEN = 0.5
SHIM_SOURCE = '''"""Stands in for a distribution this image does not carry.

It answers the import, and it survives being *used* by the package that is
importing it, which is not the same as being a mock of it.

Raising on every use was the first design, and the reasoning was sound as far as
it went: a stand-in that answered attribute access lets a test that really
exercises the absent package pass for a reason unconnected to the project, and a
refusal aimed at an answer that was right is the expensive direction.  What that
reasoning missed is where the import usually is.  A test package's own
`__init__` routinely *calls* what it imports -- to register a plugin, install a
hook, enable a checker -- and a stand-in that raises there fails before a single
test is collected.  That is not one test lost to a missing package.  It is every
test under that package, which is the whole reading.

So attribute access gives back something callable that returns its argument when
it is used as a decorator and another one of itself otherwise.  Nothing it does
is an answer about the project.  A test that really exercises the absent package
gets the same nothing in both readings, so it lands on both sides of the
difference and cancels exactly as a raising stand-in would; the difference is
only that everything beside it still runs.

The guard that makes this safe is not in here.  It is the admission check on the
recovered reading: a reading that comes back mostly red over stand-ins is a
reading about the stand-ins, and is refused whatever this module does.
"""
import functools as _functools
import importlib.abc as _abc
import importlib.machinery as _machinery
import inspect as _inspect
import sys as _sys


class _Null:
    __slots__ = ("_name",)

    def __init__(self, name="?"):
        object.__setattr__(self, "_name", name)

    def __call__(self, *args, **kwargs):
        # Two shapes arrive here and they want opposite answers.  Used bare, as
        # `@thing`, the one argument IS the test being decorated and handing it
        # back unchanged is the only answer that leaves the test as the project
        # wrote it.  Used as a factory, as `@thing(spec)`, the argument is the
        # spec and handing it back would put the spec where the test belongs.
        #
        # Narrow on purpose.  Only something that is itself a definition is
        # taken for a decoration; any other callable -- a strategy object, a
        # registry, anything of this module's own -- is not.  `callable` alone
        # made `register(handler)` hand `handler` back as though it had been
        # decorated, which is a claim about the project rather than an absence
        # of one.
        #
        # But "a definition" is wider than `def`.  Stacked decorators hand this
        # one whatever the decorator below it returned, and that is routinely a
        # `classmethod`, a `staticmethod`, a `functools.partial` or a builtin;
        # dropping those replaces the test with nothing, which is the same loss
        # by a different route.  So the test is `isroutine`, plus the two
        # descriptors and `partial` by name.
        #
        # The residue, written down rather than papered over: a factory handed a
        # plain function still gets it back.  `@thing` and `thing(fn)` are the
        # same call and nothing at this end can separate them.
        if len(args) == 1 and not kwargs and (
                _inspect.isroutine(args[0]) or _inspect.isclass(args[0])
                or isinstance(args[0], (classmethod, staticmethod,
                                        _functools.partial))):
            return args[0]
        return _Null(self._name + "()")

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Null(self._name + "." + name)

    def __mro_entries__(self, bases):
        # `class Thing(absent.Base):` at import time is one of the commonest
        # ways a suite touches an optional dependency, and without this it is a
        # TypeError -- the very failure this module exists to prevent,
        # reintroduced one line lower down.  The interpreter asks a non-class
        # used as a base what to put there instead, and the answer is NOTHING:
        # an empty tuple drops this base and leaves the others alone.  Naming
        # `object` instead looks equivalent and is not -- in
        # `class Thing(absent.Base, Real)` it produces `(object, Real)`, whose
        # linearisation does not exist, so the class raises at definition time
        # and the collection is lost exactly as before.  With no bases left
        # Python supplies `object` by itself.
        return ()

    def __getitem__(self, item):
        # `absent.Type[int]` in an annotation evaluated at runtime.
        return self

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __setitem__(self, item, value):
        # `absent.REGISTRY[name] = handler`, run by a test package's own
        # `__init__` as it registers itself.  Reading an item was answered from
        # the first version and writing one was not, which is the wrong place
        # to draw the line: a registry that is read is a registry that is
        # written, and the write comes first.  Nothing is stored, for the same
        # reason nothing else here is: what comes back out is `__getitem__`'s
        # stand-in either way, so remembering the value would only make the
        # answer look more like the absent package than it is.
        return None

    def __delitem__(self, item):
        return None

    def __repr__(self):
        return "<stand-in %s>" % self._name


def _combine(kind):
    """One answer for every binary operator, rather than the met ones.

    A module being imported combines what it imported with something of its
    own, and which operator it reaches for belongs to that module rather than
    to this one: `PREFIX + absent.NAME` while a message is built,
    `absent.Markup | None` in an annotation that is evaluated at runtime,
    `flags & absent.MASK` in a default.  Adding them one at a time as they are
    met means the next absent package still loses a whole reading to the next
    operator -- which is exactly how `|` came to be missing after `+` and `%`
    had been written down.  Answered rather than raised for the reason the rest
    of this module is answered: nothing that comes back is a claim about the
    project, and the guard is the admission check on the recovered reading, not
    the poverty of what a stand-in can do.
    """

    def operator(self, other, *rest):
        # `*rest` is three-argument `pow`, which hands the modulus here as a
        # third positional and would otherwise be the one arithmetic call that
        # still raises.
        return _Null(self._name + kind)

    return operator


for _op in ("add sub mul matmul truediv floordiv mod divmod pow lshift rshift"
            " and xor or").split():
    for _form in ("__%s__", "__r%s__"):
        setattr(_Null, _form % _op, _combine("<" + _op + ">"))

# Ordering, for the same reason and with one more thing to say.  `if limit >
# absent.THRESHOLD:` raises without these, and the answer is a stand-in, which
# is false -- so the branch that would have run over the real package does not
# run, deterministically, in both readings.  The four are reflections of each
# other, so `int > stand-in` is answered by `__lt__` and needs nothing more.
#
# Equality and hashing are deliberately not here.  Those two are what a dict
# and a set are built out of; answering them with something that is neither
# true nor false does not make a reading inert, it makes lookups wrong in a way
# that has nothing to do with the absent package.  Identity is the right answer
# for a stand-in and it is already the default.
for _op in ("lt", "le", "gt", "ge"):
    setattr(_Null, "__%s__" % _op, _combine("<" + _op + ">"))

# The loop variables, which are otherwise two ordinary strings sitting in a
# module whose whole contract is that every name in it answers with a stand-in.
del _op, _form


def __getattr__(name):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    return _Null(__name__ + "." + name)


class _Finder(_abc.MetaPathFinder, _abc.Loader):
    """Answers for any submodule of this stand-in, however deep.

    A single module file cannot: `from x.y import z` needs `x` to be a package
    with a `y` inside it, and the interpreter reports the missing name one level
    at a time, so the name written down is the top one.
    """

    def find_spec(self, fullname, path=None, target=None):
        if fullname == __name__ or fullname.startswith(__name__ + "."):
            return _machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__name__

        def _attr(attr, _n=name):
            if attr.startswith("__") and attr.endswith("__"):
                raise AttributeError(attr)
            return _Null(_n + "." + attr)

        module.__getattr__ = _attr
        module.__path__ = []


__path__ = []
_sys.meta_path.append(_Finder())
'''

def resolvable(name: str) -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except BaseException:
        return True

def missing_modules(out: str) -> list:
    seen = []
    for name in MISSING_MODULE.findall(out or ""):
        if "." in name:
            continue
        if name not in seen and name.isidentifier() and not resolvable(name):
            seen.append(name)
    return seen

def missing_dists(out: str) -> list:
    seen = []
    for name in MISSING_DIST.findall(out or ""):
        if name not in seen and re.fullmatch(r"[A-Za-z0-9._-]+", name):
            seen.append(name)
    return seen

def path_is_inside(path: str, root: str) -> bool:
    try:
        path, root = os.path.realpath(path), os.path.realpath(root)
        if (os.path.splitdrive(path)[0].lower()
                != os.path.splitdrive(root)[0].lower()):
            return False
        return os.path.commonpath([path, root]) == root
    except (ValueError, OSError, TypeError):
        return True

def write_dist_records(names: list, where: str) -> list:
    made = []
    for name in names:
        try:
            room = os.path.join(where, "%s-0.0.0.dist-info"
                                % re.sub(r"[-_.]+", "_", name))
            os.makedirs(room, exist_ok=True)
            with open(os.path.join(room, "METADATA"), "w", encoding="utf-8") as handle:
                handle.write("Metadata-Version: 2.1\nName: %s\nVersion: 0.0.0\n" % name)
        except OSError:
            continue
        made.append(name)
    return made

def write_shims(names: list, where: str) -> list:
    made = []
    for name in names:
        try:
            room = os.path.join(where, name)
            os.makedirs(room, exist_ok=True)
            with open(os.path.join(room, "__init__.py"), "w", encoding="utf-8") as handle:
                handle.write(SHIM_SOURCE)
        except OSError:
            continue
        made.append(name)
    return made

SUITE_BASELINE_SEC = 300.0
SUITE_RECHECK_SEC = 240.0
SUITE_SETTLE_SEC = 90.0
WARDEN_REFUSALS_MAX = 3
CONFIRM_MAX = 12
WARDEN_RELEASE_SEC = 150.0
RUNG_MIN_WALL_SEC = WARDEN_RELEASE_SEC + SUITE_SETTLE_SEC
WARDEN_QUESTION = (
    " Before changing anything, name it: which kind of input that this file "
    "already handles does the patched code treat differently from the "
    "original, and on which line? If nothing does, the cause is not the "
    "change in behaviour and the named tests are where to look."
)
CONFORM_MIN_WALL_SEC = 300.0
STANDIN_MIN_WALL_SEC = CONFORM_MIN_WALL_SEC + SUITE_SETTLE_SEC
LEDGER_BULLET = re.compile(r"^[-*][ \t]+(.*)$")
LEDGER_FENCE = re.compile(r"^[ \t]*(?:```|~~~)")
LEDGER_MIN = 3
LEDGER_MAX_ASKS = 2

def bullet_runs(text: str) -> list[list[str]]:
    runs: list[list[str]] = []
    current: list[str] = []
    fenced = False
    for line in (text or "").splitlines():
        if LEDGER_FENCE.match(line):
            if current and not fenced and not line[:1].isspace():
                runs.append(current)
                current = []
            fenced = not fenced
            continue
        if fenced:
            continue
        bullet = LEDGER_BULLET.match(line)
        if bullet:
            current.append(bullet.group(1).strip())
        elif line.strip() and current:
            if line.startswith((" ", "\t")):
                current[-1] += " " + line.strip()
            else:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    return [[item for item in run if item] for run in runs]

def stated_requirements(text: str) -> list[str]:
    runs = bullet_runs(text)
    if not runs:
        return []
    return max(runs, key=len)

LEDGER_GUARD = re.compile(
    r"\b(preserve|preserves|keep|keeps|retain|retains|remain|remains|"
    r"continue|continues|unchanged|intact|still|do not|don't|must not|"
    r"never|leave|leaves|untouched)\b", re.I)

def wants_an_edit(item: str) -> bool:
    return not LEDGER_GUARD.search(item or "")

def read_back(items: list[str]) -> str:
    lines = "\n".join("  %d. %s" % (n + 1, item) for n, item in enumerate(items))
    return ("Before this goes in, put the diff beside what the task asked for. "
            "These are its own words:\n%s\n"
            "Anything on that list with nothing in the diff answering for it "
            "is not done yet; do those now. Where the list asks that existing "
            "behaviour be kept, leaving that code alone is how it is met. If "
            "every item already has something answering for it, hand in again "
            "-- this is asked once." % lines)

def importable(path: str) -> bool:
    return any(path.endswith(suffix) for suffix in importlib.machinery.SOURCE_SUFFIXES)

NESTED_SOURCE = "src"

def package_roots(root: str) -> list[str]:
    nested = os.path.join(root, NESTED_SOURCE)
    return [root, nested] if os.path.isdir(nested) else [root]

def declared_file(statement: str, root: str) -> str | None:
    found = set()
    for argv in command_lines(statement):
        for token in argv[2:]:
            if token.startswith("-") or not token.endswith(".py"):
                continue
            if TEST_PATH.search(token):
                continue
            if os.path.isfile(os.path.join(root, token)):
                found.add(token)
    return found.pop() if len(found) == 1 else None

def declared_trace(statement: str, root: str) -> str:
    argvs = command_lines(statement)
    seen = dropped = existed = 0
    for argv in argvs:
        for token in argv[2:]:
            if token.startswith("-") or not token.endswith(".py"):
                continue
            seen += 1
            if TEST_PATH.search(token):
                dropped += 1
            elif os.path.isfile(os.path.join(root, token)):
                existed += 1
    return ("%d check command(s), %d path(s) on them, %d dropped as tests, "
            "%d that exist here" % (len(argvs), seen, dropped, existed))

def suite_scope(root: str, declared: str | None) -> list[str]:
    if not declared:
        return []
    parts = declared.split("/")
    if parts and parts[0] == NESTED_SOURCE:
        parts = parts[1:]
    inner = parts[1:-1]
    base = os.path.splitext(os.path.basename(declared))[0]
    names = [base]
    if base.startswith("_"):
        names.append(base.strip("_") or base)
    names.extend(reversed(inner))
    ancestors, here = [], os.path.dirname(declared)
    while here:
        ancestors.append(here)
        here = os.path.dirname(here)
    ancestors.append("")
    tries = []

    def every_top(make):
        for stem in ancestors:
            for top in ("tests", "test"):
                root_dir = os.path.join(stem, top) if stem else top
                got = make(root_dir)
                if got:
                    tries.append(got)
    if inner:
        every_top(lambda d: (os.path.join(d, *inner, "test_%s.py" % base),
                             os.path.isfile))
    for name in names:
        every_top(lambda d, n=name: (os.path.join(d, "test_%s.py" % n), os.path.isfile))
    for cut in range(len(inner)):
        every_top(lambda d, c=cut: (os.path.join(d, *inner[c:]), os.path.isdir))
    every_top(lambda d: (os.path.join(d, "test_%s" % base), os.path.isdir))
    every_top(lambda d: (d, os.path.isdir))
    for rel, is_right in tries:
        if is_right(os.path.join(root, rel)):
            return [rel]
    return []

DIFF_TRIVIAL = re.compile(r"^[\s)\]}:,]*$")


# --- platform/database_runtime.py ---
URL_IN_TEXT = re.compile(r"\b((?:postgres(?:ql)?|clickhouse|clickhousedb|jdbc:postgresql|jdbc:clickhouse)://[^\s'\"<>]+)")
KV_IN_TEXT = re.compile(r"\b(POSTGRES_(?:USER|PASSWORD|DB|HOST|PORT)|PG(?:USER|PASSWORD|DATABASE|HOST|PORT)|"
                        r"CLICKHOUSE_(?:USER|PASSWORD|DB|DATABASE|HOST|PORT|HTTP_PORT)|DB_(?:USER|USERNAME|PASSWORD|PASS|NAME|DATABASE|HOST|PORT))"
                        r"\s*[:=]\s*[\"']?([^\s\"',;]+)")
CONFIG_FILE_HINT = re.compile(r"(^|/)(settings[^/]*\.py|configuration[^/]*\.py|config[^/]*\.(py|ya?ml|json|toml|exs|rb)|database\.ya?ml|\.env(\.[\w.-]+)?|"
                              r"docker-compose[^/]*\.ya?ml|compose[^/]*\.ya?ml|knexfile\.[jt]s|schema\.prisma|alembic\.ini|ormconfig[^/]*|"
                              r"drizzle\.config\.[jt]s|application[^/]*\.(properties|ya?ml)|appsettings[^/]*\.json|datasource[^/]*|\.env\.example)$", re.I)

def clip_text_tail(text: str, cap: int) -> str:
    text = text or ""
    return text if len(text) <= cap else "..." + text[-cap:]

def run_silent_command(command, cwd: str, timeout: float, shell: bool = False,
              env: dict | None = None) -> tuple[int, str]:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, errors="replace",
                              timeout=max(1.0, timeout), shell=shell, env=merged)
    except subprocess.TimeoutExpired:
        return 124, "timed out after %.0fs" % timeout
    except Exception as error:
        return 1, "%s: %s" % (type(error).__name__, error)
    return done.returncode, (done.stdout or "") + (done.stderr or "")

def detect_engine_hint(statement: str) -> str:
    text = statement or ""
    if re.search(r"clickhouse", text, re.I):
        return "clickhouse"
    if re.search(r"postgres", text, re.I):
        return "postgresql"
    return ""

def adaptive_context_needed(statement: str) -> bool:
    """Use repository and database context only for database-shaped tasks."""
    if detect_engine_hint(statement):
        return True
    return bool(re.search(
        r"\b(?:database|db|sql|query|queryset|orm|migration|postgres(?:ql)?|"
        r"clickhouse|django|active\s*record|relation|model)\b",
        statement or "", re.I))

DJANGO_DB_SNIPPET = (
    "import json\n"
    "from django.conf import settings\n"
    "out = {}\n"
    "for alias, cfg in settings.DATABASES.items():\n"
    "    out[alias] = {k: (str(cfg.get(k)) if cfg.get(k) is not None else None) for k in ('ENGINE', 'NAME', 'USER', 'PASSWORD', 'HOST', 'PORT')}\n"
    "    test = cfg.get('TEST') or {}\n"
    "    out[alias]['TEST_NAME'] = str(test.get('NAME')) if test.get('NAME') else None\n"
    "print('RIDGES_DB_JSON=' + json.dumps(out))\n"
)

class Connection:
    def __init__(self, engine: str, label: str, url: str, host: str = "", port: str = "", user: str = "",
                 password: str = "", database: str = "") -> None:
        self.engine = engine
        self.label = label
        self.url = url
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.tables = -1
        self.version = ""
        self.tool = ""

    def describe(self) -> str:
        shown = self.url
        if self.engine == "clickhouse" and not shown:
            shown = "%s:%s db=%s user=%s" % (self.host, self.port, self.database or "default", self.user or "default")
        extra = []
        if self.tables >= 0:
            extra.append("%d user table(s)" % self.tables)
        if self.version:
            extra.append(self.version[:60])
        return "[%s] %s %s%s" % (self.label, self.engine, shown, (" -- " + ", ".join(extra)) if extra else "")

def build_postgres_url(user: str, password: str, host: str, port: str, name: str) -> str:
    auth = user or "postgres"
    if password:
        auth += ":" + password
    return "postgresql://%s@%s:%s/%s" % (auth, host or "localhost", port or "5432", name or "postgres")

class Database:
    def __init__(self, tree: Tree, files: list, engine_hint: str, allowance: Allowance) -> None:
        self.tree = tree
        self.files = files
        self.engine_hint = engine_hint
        self.allowance = allowance
        self.connections: list = []
        self.notes: list = []
        self.config_files: list = []
        self.hosts: list = []
        self.manage_py = next((p for p in files if p.endswith("manage.py") and p.count("/") <= 2), None)
        self.deadline = time.monotonic() + DISCOVERY_BUDGET_SEC
        self.names: "ClickHouseNames | None" = None

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def discover(self) -> None:
        started = time.monotonic()
        try:
            self._from_env()
            self._config_files()
            candidates = self._candidates()
            self._probe_all(candidates)
        except Exception as error:
            self.notes.append("discovery stopped early: %s: %s" % (type(error).__name__, str(error)[:120]))
        log_message("[DB] discovery %.0fs: %d connection(s) usable, %d candidate host(s): %s"
            % (time.monotonic() - started, len([c for c in self.connections if c.tables >= 0 or c.version]),
               len(self.hosts), "; ".join(c.describe() for c in self.connections)[:400]))

    def _from_env(self) -> None:
        for key, value in os.environ.items():
            if URL_IN_TEXT.search(value or ""):
                self.notes.append("environment %s=%s" % (key, value))
            elif re.match(r"^(POSTGRES_|PG|CLICKHOUSE_|DATABASE_|DB_)", key) and key not in ("PGDATA",):
                self.notes.append("environment %s=%s" % (key, value if "PASS" not in key else value))

    def _config_files(self) -> None:
        hits = [p for p in self.files if CONFIG_FILE_HINT.search(p) and not TEST_PATH.search(p)
                and "node_modules" not in p and "/site-packages/" not in p]
        hits.sort(key=lambda p: (p.count("/"), len(p)))
        self.config_files = hits[:12]

    def _text_of(self, path: str, cap: int = 200_000) -> str:
        try:
            with open(os.path.join(self.tree.root, path), "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(cap)
        except OSError:
            return ""

    def _candidates(self) -> list:
        found: list = []
        seen: set = set()

        def add(conn: Connection) -> None:
            key = (conn.engine, conn.url or (conn.host, conn.port, conn.user, conn.database))
            if key in seen:
                return
            seen.add(key)
            found.append(conn)
        if self.manage_py and self.left() > 20:
            for alias, cfg in self._django_databases().items():
                engine = str(cfg.get("ENGINE") or "").lower()
                kind = "clickhouse" if "clickhouse" in engine else ("postgresql" if "postgres" in engine else "")
                if not kind:
                    self.notes.append("Django alias %s uses %s" % (alias, engine or "?"))
                    continue
                host, port, user, password = cfg.get("HOST") or "localhost", cfg.get("PORT") or "", cfg.get("USER") or "", cfg.get("PASSWORD") or ""
                if kind == "postgresql":
                    add(Connection(kind, "django:%s" % alias, build_postgres_url(user, password, host, port, cfg.get("NAME") or ""),
                                   host, port or "5432", user, password, cfg.get("NAME") or ""))
                    if cfg.get("TEST_NAME"):
                        add(Connection(kind, "django:%s:test" % alias, build_postgres_url(user, password, host, port, cfg["TEST_NAME"]),
                                       host, port or "5432", user, password, cfg["TEST_NAME"]))
                else:
                    add(Connection(kind, "django:%s" % alias, "", host, port or "8123", user, password, cfg.get("NAME") or ""))
        texts = {}
        for path in self.config_files:
            texts[path] = self._text_of(path)
        for key, value in os.environ.items():
            texts["env:" + key] = value or ""
        for source, text in texts.items():
            for url in URL_IN_TEXT.findall(text):
                url = url.rstrip(".,;)")
                engine = "clickhouse" if "clickhouse" in url.split("://")[0] else "postgresql"
                url = url.replace("jdbc:", "")
                add(Connection(engine, "url:" + os.path.basename(source), url if engine == "postgresql" else "", *self._split_url(url)))
        for source, text in texts.items():
            if "DATABASES" not in text or "postgres" not in text.lower():
                continue
            block = text[text.find("DATABASES"):][:4000]
            fields = {k: v for k, v in re.findall(r"['\"](ENGINE|NAME|USER|PASSWORD|HOST|PORT)['\"]\s*:\s*['\"]?([^'\",\s}]+)", block)}
            if "postgres" in fields.get("ENGINE", "").lower() and fields.get("NAME"):
                host = fields.get("HOST") or "localhost"
                add(Connection("postgresql", "settings:" + os.path.basename(source),
                               build_postgres_url(fields.get("USER", ""), fields.get("PASSWORD", ""), host, fields.get("PORT", "5432"), fields["NAME"]),
                               host, fields.get("PORT", "5432"), fields.get("USER", ""), fields.get("PASSWORD", ""), fields["NAME"]))
                test_name = re.search(r"['\"]TEST['\"]\s*:\s*\{[^}]*['\"]NAME['\"]\s*:\s*['\"]([^'\"]+)", block)
                if test_name:
                    add(Connection("postgresql", "settings:test", build_postgres_url(fields.get("USER", ""), fields.get("PASSWORD", ""), host, fields.get("PORT", "5432"), test_name.group(1)),
                                   host, fields.get("PORT", "5432"), fields.get("USER", ""), fields.get("PASSWORD", ""), test_name.group(1)))
        kv: dict = {}
        for source, text in texts.items():
            for key, value in KV_IN_TEXT.findall(text):
                kv.setdefault(key, value)
        if any(k.startswith(("POSTGRES_", "PG")) for k in kv) or any(k.startswith("DB_") for k in kv):
            user = kv.get("POSTGRES_USER") or kv.get("PGUSER") or kv.get("DB_USER") or kv.get("DB_USERNAME") or "postgres"
            password = kv.get("POSTGRES_PASSWORD") or kv.get("PGPASSWORD") or kv.get("DB_PASSWORD") or kv.get("DB_PASS") or ""
            name = kv.get("POSTGRES_DB") or kv.get("PGDATABASE") or kv.get("DB_NAME") or kv.get("DB_DATABASE") or user
            port = kv.get("POSTGRES_PORT") or kv.get("PGPORT") or kv.get("DB_PORT") or "5432"
            for host in self._hosts([kv.get("POSTGRES_HOST"), kv.get("PGHOST"), kv.get("DB_HOST")], ("postgres", "postgresql", "db", "database", "localhost")):
                add(Connection("postgresql", "config:" + host, build_postgres_url(user, password, host, port, name), host, port, user, password, name))
        if any(k.startswith("CLICKHOUSE_") for k in kv) or "clickhouse" in (self.engine_hint or "") or any("clickhouse" in t.lower() for t in texts.values()):
            user = kv.get("CLICKHOUSE_USER") or "default"
            password = kv.get("CLICKHOUSE_PASSWORD") or ""
            name = kv.get("CLICKHOUSE_DB") or kv.get("CLICKHOUSE_DATABASE") or "default"
            port = kv.get("CLICKHOUSE_HTTP_PORT") or "8123"
            for host in self._hosts([kv.get("CLICKHOUSE_HOST")], ("clickhouse", "clickhouse-server", "ch", "localhost")):
                add(Connection("clickhouse", "config:" + host, "", host, port, user, password, name))
        if not found:
            for host in self._hosts([], ("postgres", "postgresql", "db", "database", "localhost")):
                add(Connection("postgresql", "guess:" + host, build_postgres_url("postgres", os.getenv("PGPASSWORD", ""), host, "5432", "postgres"),
                               host, "5432", "postgres", os.getenv("PGPASSWORD", ""), "postgres"))
            for host in self._hosts([], ("clickhouse", "clickhouse-server", "localhost")):
                add(Connection("clickhouse", "guess:" + host, "", host, "8123", "default", "", "default"))
        return found

    @staticmethod
    def _split_url(url: str) -> tuple:
        match = re.match(r"^[a-z]+://(?:([^:@/]+)(?::([^@/]*))?@)?([^:/?]+)(?::(\d+))?(?:/([^?]*))?", url)
        if not match:
            return ("", "", "", "", "")
        user, password, host, port, name = match.groups()
        return (host or "", port or "", user or "", password or "", (name or "").strip("/"))

    def _hosts(self, named: list, defaults: tuple) -> list:
        out: list = []
        for host in [h for h in named if h] + list(defaults):
            if host in out:
                continue
            if host in self.hosts or self._resolves(host):
                out.append(host)
                if host not in self.hosts:
                    self.hosts.append(host)
            if len(out) >= 3:
                break
        return out

    def _resolves(self, host: str) -> bool:
        if self.left() < 3:
            return False
        code, _ = run_silent_command(["getent", "hosts", host], self.tree.root, min(3.0, self.left()))
        return code == 0

    def _django_databases(self) -> dict:
        manage = self.tree.absolute(self.manage_py)
        code, out = run_silent_command([sys.executable, manage, "shell", "-c", DJANGO_DB_SNIPPET], os.path.dirname(manage) or self.tree.root,
                              min(45.0, max(5.0, self.left() - 20)))
        for line in out.splitlines():
            if line.startswith("RIDGES_DB_JSON="):
                try:
                    return json.loads(line[len("RIDGES_DB_JSON="):])
                except ValueError:
                    break
        self.notes.append("`%s shell` could not report DATABASES (rc=%s): %s" % (self.manage_py, code, clip_text_tail(compact_text(out), 200)))
        return {}

    def _probe_all(self, candidates: list) -> None:
        for conn in candidates:
            if self.left() < 4:
                self.notes.append("discovery budget spent before probing every candidate")
                break
            if conn.engine == "postgresql":
                self._probe_pg(conn)
            else:
                self._probe_ch(conn)
            self.connections.append(conn)
        self.connections.sort(key=lambda c: (-(c.tables if c.tables >= 0 else -1), c.label))

    def _probe_pg(self, conn: Connection) -> None:
        query = ("select version(), (select count(*) from pg_tables where schemaname not in ('pg_catalog','information_schema'))")
        budget = min(8.0, self.left())
        if shutil.which("psql"):
            code, out = run_silent_command(["psql", conn.url, "-X", "-At", "-F", "|", "-c", query], self.tree.root, budget,
                                  env={"PGCONNECT_TIMEOUT": "5"})
            if code == 0 and "|" in out:
                version, tables = out.strip().rsplit("|", 1)
                conn.version, conn.tables, conn.tool = version.split(",")[0], int(tables.strip() or -1), "psql"
                return
            conn.version = "" if code == 0 else "psql: " + compact_text(out)[:100]
        snippet = ("import sys\n"
                   "try:\n    import psycopg as pg\nexcept ImportError:\n    import psycopg2 as pg\n"
                   "c = pg.connect(sys.argv[1], connect_timeout=5)\n"
                   "cur = c.cursor(); cur.execute(%r); print('RIDGES_PG=' + '|'.join(str(x) for x in cur.fetchone()))\n" % query)
        code, out = run_silent_command([sys.executable, "-c", snippet, conn.url], self.tree.root, min(10.0, self.left()))
        for line in out.splitlines():
            if line.startswith("RIDGES_PG="):
                version, tables = line[len("RIDGES_PG="):].rsplit("|", 1)
                conn.version, conn.tables, conn.tool = version.split(",")[0], int(tables.strip() or -1), "python"
                return
        if not conn.version:
            conn.version = "unreachable: " + compact_text(out)[-120:]

    def _probe_ch(self, conn: Connection) -> None:
        query = "SELECT version(), (SELECT count() FROM system.tables WHERE database NOT IN ('system','INFORMATION_SCHEMA','information_schema'))"
        if shutil.which("clickhouse-client") or shutil.which("clickhouse"):
            binary = ["clickhouse-client"] if shutil.which("clickhouse-client") else ["clickhouse", "client"]
            args = binary + ["--host", conn.host, "--user", conn.user or "default"]
            if conn.password:
                args += ["--password", conn.password]
            args += ["-q", query]
            code, out = run_silent_command(args, self.tree.root, min(8.0, self.left()))
            if code == 0 and out.strip():
                parts = out.strip().split("\t")
                conn.version, conn.tables, conn.tool = "ClickHouse " + parts[0], int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else -1, "clickhouse-client"
                return
        url = "http://%s:%s/?query=%s" % (conn.host, conn.port or "8123", urllib.request.quote(query + " FORMAT TabSeparated"))
        request = urllib.request.Request(url)
        if conn.user or conn.password:
            request.add_header("X-ClickHouse-User", conn.user or "default")
            request.add_header("X-ClickHouse-Key", conn.password or "")
        if conn.database:
            request.add_header("X-ClickHouse-Database", conn.database)
        try:
            with urllib.request.urlopen(request, timeout=min(5.0, max(1.0, self.left()))) as response:
                parts = response.read().decode("utf-8", "replace").strip().split("\t")
                conn.version, conn.tool = "ClickHouse " + parts[0], "http"
                conn.tables = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else -1
        except Exception as error:
            conn.version = "unreachable: %s" % compact_text(getattr(error, "reason", error))[:100]

    def usable(self) -> list:
        return [c for c in self.connections if c.tool]

    def clickhouse_rows(self, query: str, budget: float) -> tuple[int, str]:
        conn = next((c for c in self.usable() if c.engine == "clickhouse"), None)
        if conn is None:
            return 1, "no ClickHouse connection answered a probe"
        if conn.tool == "clickhouse-client" and (shutil.which("clickhouse-client") or shutil.which("clickhouse")):
            binary = ["clickhouse-client"] if shutil.which("clickhouse-client") else ["clickhouse", "client"]
            args = binary + ["--host", conn.host, "--user", conn.user or "default"]
            if conn.password:
                args += ["--password", conn.password]
            return run_silent_command(args + ["-q", query], self.tree.root, budget)
        request = urllib.request.Request("http://%s:%s/" % (conn.host, conn.port or "8123"),
                                         data=query.encode("utf-8"), method="POST")
        request.add_header("X-ClickHouse-User", conn.user or "default")
        request.add_header("X-ClickHouse-Key", conn.password or "")
        try:
            with urllib.request.urlopen(request, timeout=max(1.0, budget)) as response:
                return 0, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace")[:400]
        except Exception as error:
            return 1, "%s: %s" % (type(error).__name__, error)

    def clickhouse_names(self) -> "ClickHouseNames":
        if self.names is not None:
            return self.names
        self.names = ClickHouseNames([], [])
        budget = max(2.0, min(10.0, self.allowance.clock_left() - 5.0))
        code, out = self.clickhouse_rows(
            "SELECT name, is_aggregate, case_insensitive FROM system.functions FORMAT TabSeparated", budget)
        rows = []
        if code == 0:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3 and parts[0]:
                    rows.append((parts[0], parts[1].strip() == "1", parts[2].strip() == "1"))
        combinators: list = []
        if len(rows) >= ENGINE_NAMES_FLOOR:
            code, out = self.clickhouse_rows(
                "SELECT name FROM system.aggregate_function_combinators FORMAT TabSeparated", budget)
            combinators = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []
            self.names = ClickHouseNames(rows, combinators)
        log_message("[ENGINE] ClickHouse names read: %d function(s), %d combinator(s)%s"
            % (len(rows), len(combinators), "" if self.names else " -- not enough to judge a name by"))
        return self.names

    def pick(self, wanted: str | None) -> Connection | None:
        usable = self.usable()
        if not usable:
            return None
        if wanted:
            for conn in usable:
                if wanted in (conn.label, conn.database, conn.url, conn.host):
                    return conn
            for conn in usable:
                if wanted.lower() in conn.label.lower() or wanted.lower() in (conn.database or "").lower():
                    return conn
        with_tables = [c for c in usable if c.tables > 0]
        return (with_tables or usable)[0]

    def brief(self) -> str:
        lines = []
        rows = []
        for conn in self.usable():
            if conn.engine == "postgresql":
                command = 'psql "%s"' % conn.url
            else:
                auth = (" --user %s" % conn.user if conn.user else "") + (
                    " --password %s" % conn.password if conn.password else "")
                command = "clickhouse-client --host %s%s  (HTTP on port %s)" % (
                    conn.host, auth, conn.port or "8123")
            rows.append((conn.engine, command))
        if rows:
            lines.append("Live database connections (use the sql tool, or the command shown):")
            for engine, command in sorted(rows):
                lines.append("  %s\n      %s" % (engine, command))
        if self.config_files:
            lines.append("Configuration files worth reading for connection details: "
                         + ", ".join(sorted(self.config_files)[:8]))
        return "\n".join(lines)

WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
QUOTED_RE = re.compile(r"[`'\"]([A-Za-z_][A-Za-z0-9_.]{2,})[`'\"]")
COMMON_WORDS = frozenset(
    """the this that with from when what which should would could have been
    test tests file files line lines code error errors return returns value
    values method function class module import python true false none self
    argument arguments result results object objects string strings expected""".split()
)


# --- analysis/findings.py ---
def flag_whole_value(lines: list) -> int | None:
    for index, line in enumerate(lines):
        found = FLAG_KEYWORD.search(line)
        if not found:
            continue
        window = "\n".join(lines[max(0, index - 8): index + 1])
        if found.group(1) in masked_names(window):
            continue
        queries = [m.end() for m in QUERY_OPENER.finditer(window)]
        builds = [m.end() for m in BUILD_OPENER.finditer(window)]
        if queries and (not builds or max(queries) > max(builds)):
            return index
    for index, line in enumerate(lines):
        if FLAG_SQL_COMPARE.search(line):
            return index
    return None

def masked_names(window: str) -> set:
    return {m.group(1) for m in MASKED_NAME.finditer(window)}

DB_CASE_FOLD = re.compile(
    r"\b(?:Lower|Upper)\(|\b(?:lower|upper)\s*\(\s*[\w\"'.]|__iexact\b|\bILIKE\b|__icontains\b|__istartswith\b|"
    r"\bLOWER\(|\bUPPER\(")
APP_CASE_FOLD = re.compile(
    r"\.(?:lower|upper|casefold)\(\)|\.toLowerCase\(\)|\.toUpperCase\(\)|\.downcase\b|\.upcase\b|"
    r"strings\.To(?:Lower|Upper)\(|String\.downcase")
BARE_PREDICATE = re.compile(
    r"\b(?:AND|OR|WHERE)\s+%\w+%(?!\s*\))|\b(?:AND|OR|WHERE)\s+\{\w*(?:query|filter|where|cond|expr|clause)\w*\}|"
    r"(?:AND|OR)\s*[\"']\s*\+\s*\w*(?:query|filter|where|cond|expr|clause)\w*|"
    r"(?:AND|OR)\s+%s[\"']\s*%\s*\(?\w*(?:query|filter|where|cond|expr|clause)", re.I)
RUBY_DEF = re.compile(r"^\s*def\s+(?:self\.)?[\w?!=]+\s*(?:\((.*)\)|\s+(.*))?\s*$")
HELD_OBJECT_LOCK = re.compile(r"\b(\w+)\.(?:with_lock\b|lock!)")
CLASS_LOCK = re.compile(r"\.class\.lock\b")
CONTEXT_STORE = re.compile(r"\bctx\s*:?=\s*(?:\w+\.)?(?:ContextWith\w*|With[A-Z]\w*)\(\s*ctx\s*,")
REQUEST_SCOPED = re.compile(r"(?i)span|trac|log|timeout|deadline|cancel|baggage|meter|metric|signal")
QUERYSET_OR_MANAGER = re.compile(r"\b\w+\s+or\s+[A-Z]\w*\.(?:objects|_default_manager|_base_manager)\b")

def ruby_parameters(text: str) -> set:
    names = set()
    for part in (text or "").split(","):
        name = re.sub(r"^[*&]+", "", part.strip()).split("=")[0].split(":")[0].strip()
        if re.match(r"^\w+$", name):
            names.add(name)
    return names

def handed_record_lock(lines: list) -> int | None:
    params: set = set()
    for index, line in enumerate(lines):
        head = RUBY_DEF.match(line)
        if head:
            params = ruby_parameters(head.group(1) or head.group(2))
            continue
        for match in HELD_OBJECT_LOCK.finditer(line):
            if match.group(1) in params:
                return index
    return None

HEREDOC_OPENER = re.compile(r"<<([~-]?)([\"'`]?)([A-Za-z_]\w*)\2")
HEREDOC_ARGUMENT = re.compile(r"^\s*[A-Za-z_@:][\w.:@!?\[\]()]*\s*[,)]\s*$")

def heredoc_swallowed_arguments(lines: list) -> int | None:
    for index, line in enumerate(lines):
        if COMMENT_LINE.match(line):
            continue
        for match in HEREDOC_OPENER.finditer(line):
            indented, word = match.group(1), match.group(3)
            if not indented and not word.isupper():
                continue
            if not line[match.end():].rstrip().endswith(","):
                continue
            end = next((later for later in range(index + 1, len(lines))
                        if (lines[later].strip() if indented else lines[later].rstrip()) == word), None)
            if end is None:
                continue
            after = next((text.strip() for text in lines[end + 1:] if text.strip()), "")
            if after.startswith(")") and any(HEREDOC_ARGUMENT.match(text) for text in lines[index + 1:end]):
                return index
    return None

SHAPE_NOTES = {
    
    "qs_or": ("`%s` picks a queryset with `or`. That asks the database whether the first queryset has any "
              "rows, and an empty one counts as missing, so a filter that matches nothing falls back to the "
              "other queryset, often every row. When the first one stands for 'not given', write "
              "`first if first is not None else other`."),
    "flags": ("`%s` compares a flag column as a whole value, so a row that also carries other "
              "bits does not match. Test the bit itself ((flags & bit) != 0), the way other queries "
              "in this repository test the same flag: search for them and copy their lookup."),
    "period_bounds": ("`%s` finds rows of one period by where the period starts. A period is its start and its "
                      "end together: two rows can start at the same moment and end at different ones (a period cut "
                      "short, extended or computed again), and matching the start alone takes one for the other. "
                      "The rows here record an end as well, so match the end too."),
    "heredoc": ("`%s` opens a heredoc on a line that ends with a comma, and the call's closing parenthesis comes "
                "after the heredoc's terminator. Ruby starts the heredoc's text on the line after the opener, so "
                "every argument written on the lines below it is part of that string and never reaches the call; "
                "ruby -c still reports Syntax OK. Put the other arguments on the opener's own line, as in "
                "call(<<~SQL, first, second), and let the heredoc text follow."),
    "factor_path": ("`%s` reads a factor for each summed row through a path that runs on past those rows and back "
                    "in through a foreign key, two hops beyond the rows being summed. Inside an aggregate over a "
                    "relation path a factor is taken from a hop the aggregate already stands on, the summed rows or "
                    "a row on the way to them; a path that continues past them is another join, and the aggregate "
                    "does not tie its value to the row it is summing. Read the factor from the hop where it lives, "
                    "and do not paper over an empty factor with a default."),
    "lock": ("`%s` takes the row lock with with_lock/lock! on the record this method was handed. "
             "lock! reloads that very object, and Rails raises when it carries unsaved changes, as "
             "a record handed over from a callback or a caller can. Lock a fresh copy instead, through "
             "the model class written by name inside a transaction (for an order: Order.transaction do "
             "... fresh = Order.lock.find(order.id) ... end), never through record.class, and read the "
             "current values from that copy."),
    "class_lock": ("`%s` takes a row lock through an instance's class (record.class.lock). Write the model "
                   "class by its name, Order.lock.find(order.id) inside Order.transaction do ... end: the "
                   "code then reads as the model it locks, and a reader checking which rows a change locks "
                   "can see it."),
    "predicate": ("`%s` inserts a caller-supplied condition into the query without parentheses. "
                  "An OR inside it escapes the conditions around it (scope, paging, counts). Wrap "
                  "the inserted condition in parentheses everywhere it is placed."),
    "upsert": ("`%s` writes a batch with an upsert (INSERT ... ON CONFLICT; bulk_create with "
               "ignore_conflicts or update_conflicts, upsert_all and insert_all send the same "
               "statement). PostgreSQL locks the rows in the order they arrive, so two calls whose "
               "batches overlap in a different order deadlock, and one statement cannot update the "
               "same row twice. Sort the rows by the conflict key and drop duplicates before the "
               "statement; DISTINCT, GROUP BY or a set does not fix the order."),
    "case": ("`%s` folds case both in the application (.lower(), .upper(), .casefold()) and in "
             "the database (Lower, Upper, iexact, ILIKE) in the same change. Their Unicode rules "
             "differ (final sigma, dotted I, sharp s), so a key built one way does not match a key "
             "built the other. Keep case-insensitive matching inside the database, with the same "
             "function on both sides, and carry the caller's own spelling as the key."),
    "ctx_value": ("`%s` stores a value in the context so that code further down reads it back out. A value "
                  "that decides what that code does, such as which rows a query may return, belongs in the "
                  "parameters of the functions that use it: callers then have to pass it, and a reader can "
                  "see where it comes from. Add it to those functions' parameters and pass it explicitly."),
    "narrow_list": ("`%s` adds a comparison to the filter of a query that returns rows, in the same change that "
                    "turns another query into a sum. A list and a number are two different facts of the same rows: "
                    "a row whose remainder is zero still belongs to the list, and narrowing the list changes what "
                    "every caller of it sees. Keep the remainder inside the aggregate (subtract, floor at zero, sum) "
                    "and leave the query that lists rows as it was."),
}
HINT_HEAD = "Not handed in yet: the changed code has a shape that is easy to get wrong. One look before it goes:"
HINT_TAIL = ("Fix what applies. If a point does not apply to this code, say why in one line and call "
             "submit again; this is asked once.")
ENGINE_HEAD = ("Not handed in yet: the changed code runs into how the database engine behaves, and the "
               "answer breaks where it does. One look before it goes:")
NAME_HEAD = ("Not handed in yet: the changed code reads a name its module never binds, so it fails the "
             "moment that line runs. One look before it goes:")
ENGINE_FACTS = read_env_flag("RIDGES_ENGINE_FACTS")
ENGINE_FACT_CONTEXT = 3
ENGINE_NAMES_FLOOR = 200
CH_FAMILY = re.compile(
    r"^(?:arrayMap|arrayFilter|arrayJoin|arrayDistinct|arraySort|arrayReduce|arrayStringConcat|multiIf|"
    r"mannWhitney|studentTTest|welchTTest|timeSlots?|toStartOf|toTimeZone|dateDiff|JSONExtract|"
    r"simpleLinearRegression|stochastic|entropy|deltaSum|exponentialMovingAverage|sparkbar|kolmogorov|"
    r"sumMap|minMap|maxMap|avgWeighted|histogram|sequenceMatch|sequenceCount|windowFunnel|retention|"
    r"quantiles?|median|uniq|argMin|argMax|groupArray|groupUniqArray|groupBit|anyHeavy|anyLast|topK|"
    r"(?:count|sum|avg|min|max|any)(?:If|State|Merge|OrNull)|uniqState|uniqMerge)")
CH_BUNDLED_AGGREGATES = """
BIT_AND BIT_OR BIT_XOR COVAR_POP COVAR_SAMP STD STDDEV_POP STDDEV_SAMP VAR_POP VAR_SAMP aggThrow
analysisOfVariance anova any anyHeavy anyLast anyLastRespectNulls anyLast_respect_nulls
anyRespectNulls anyValueRespectNulls any_respect_nulls any_value any_value_respect_nulls
approx_top_count approx_top_k approx_top_sum argMax argMin array_agg array_concat_agg avg
avgWeighted boundingRatio categoricalInformationValue contingency corr corrMatrix corrStable count
covarPop covarPopMatrix covarPopStable covarSamp covarSampMatrix covarSampStable cramersV
cramersVBiasCorrected deltaSum deltaSumTimestamp denseRank dense_rank distinctDynamicTypes
distinctJSONPaths distinctJSONPathsAndTypes entropy estimateCompressionRatio
exponentialMovingAverage exponentialTimeDecayedAvg exponentialTimeDecayedCount
exponentialTimeDecayedMax exponentialTimeDecayedSum firstValueRespectNulls first_value
first_value_respect_nulls flameGraph groupArray groupArrayInsertAt groupArrayIntersect
groupArrayLast groupArrayMovingAvg groupArrayMovingSum groupArraySample groupArraySorted groupBitAnd
groupBitOr groupBitXor groupBitmap groupBitmapAnd groupBitmapOr groupBitmapXor groupConcat
groupUniqArray group_concat histogram intervalLengthSum kolmogorovSmirnovTest kurtPop kurtSamp
lagInFrame largestTriangleThreeBuckets lastValueRespectNulls last_value last_value_respect_nulls
leadInFrame lttb mannWhitneyUTest max maxIntersections maxIntersectionsPosition maxMappedArrays
meanZTest median medianBFloat16 medianBFloat16Weighted medianDD medianDeterministic medianExact
medianExactHigh medianExactLow medianExactWeighted medianExactWeightedInterpolated medianGK
medianInterpolatedWeighted medianTDigest medianTDigestWeighted medianTiming medianTimingWeighted min
minMappedArrays nonNegativeDerivative nothing nothingNull nothingUInt64 nth_value ntile percentRank
percent_rank quantile quantileBFloat16 quantileBFloat16Weighted quantileDD quantileDeterministic
quantileExact quantileExactExclusive quantileExactHigh quantileExactInclusive quantileExactLow
quantileExactWeighted quantileExactWeightedInterpolated quantileGK quantileInterpolatedWeighted
quantileTDigest quantileTDigestWeighted quantileTiming quantileTimingWeighted quantiles
quantilesBFloat16 quantilesBFloat16Weighted quantilesDD quantilesDeterministic quantilesExact
quantilesExactExclusive quantilesExactHigh quantilesExactInclusive quantilesExactLow
quantilesExactWeighted quantilesExactWeightedInterpolated quantilesGK quantilesInterpolatedWeighted
quantilesTDigest quantilesTDigestWeighted quantilesTiming quantilesTimingWeighted rank rankCorr
retention row_number sequenceCount sequenceMatch sequenceMatchEvents sequenceNextNode
simpleLinearRegression singleValueOrNull skewPop skewSamp sparkBar sparkbar stddevPop
stddevPopStable stddevSamp stddevSampStable stochasticLinearRegression stochasticLogisticRegression
studentTTest sum sumCount sumKahan sumMapFiltered sumMapFilteredWithOverflow sumMapWithOverflow
sumMappedArrays sumWithOverflow theilsU topK topKWeighted uniq uniqCombined uniqCombined64 uniqExact
uniqHLL12 uniqTheta uniqUpTo varPop varPopStable varSamp varSampStable welchTTest windowFunnel
""".split()
CH_BUNDLED_FUNCTIONS = """
JSONExtract JSONExtractArrayRaw JSONExtractBool JSONExtractFloat JSONExtractInt JSONExtractKeys
JSONExtractKeysAndValues JSONExtractKeysAndValuesRaw JSONExtractRaw JSONExtractString
JSONExtractUInt arrayDistinct arrayFilter arrayJoin arrayMap arrayReduce arrayReduceInRanges
arraySort arrayStringConcat dateDiff multiIf timeSlot timeSlots toStartOfDay toStartOfFifteenMinutes
toStartOfFiveMinute toStartOfFiveMinutes toStartOfHour toStartOfISOYear toStartOfInterval
toStartOfMicrosecond toStartOfMillisecond toStartOfMinute toStartOfMonth toStartOfNanosecond
toStartOfQuarter toStartOfSecond toStartOfTenMinutes toStartOfWeek toStartOfYear toTimeZone
uniqThetaIntersect uniqThetaNot uniqThetaUnion
""".split()
CH_BUNDLED_COMBINATORS = "ArgMax ArgMin Array Distinct ForEach If Map Merge Null OrDefault OrNull Resample SimpleState State".split()
CALL_NAME = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
CODE_COMMENT = re.compile(r"^\s*(?://|#|--|\*|/\*)")
OUTER_JOIN = re.compile(r"\b(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?\s+(?:ANY\s+|ALL\s+)?JOIN\b|:(?:left|right|full)\b|"
                        r"\b(?:leftJoin|fullJoin|rightJoin)\b|join_type", re.I)
NULL_TEST = re.compile(r"\b(?:coalesce|ifNull|isNull|isNotNull|assumeNotNull)\s*\(|\bIS\s+(?:NOT\s+)?NULL\b", re.I)
JOIN_USE_NULLS = re.compile(r"\bjoin_use_nulls\b['\"]?\s*(?:=>|=|:|,)\s*['\"]?(?:1|true)\b", re.I)
TIME_SLOTS = re.compile(r"\btimeSlots\s*\(")
ZONE_WORD = re.compile(r"toTimeZone|timezone|time_zone|\btz\b", re.I)
DJANGO_DISTINCT_AGG = re.compile(
    r"\b\w+\(\s*([^,()]+?)\s*,[^()]*?\bdistinct\s*=\s*True\b[^()]*?\border_by\s*=\s*(\[[^\]]*\]|\([^)]*\)|[^,()]+)")
DJANGO_ORDER_FIRST = re.compile(
    r"\b\w+\(\s*([^,()]+?)\s*,[^()]*?\border_by\s*=\s*(\[[^\]]*\]|\([^)]*\)|[^,()]+)[^()]*?\bdistinct\s*=\s*True\b")
DJANGO_DISTINCT_TAIL = re.compile(
    r"^\s*([^,()=\s][^,()=]*?)\s*,[^()]*?\bdistinct\s*=\s*True\b[^()]*?\border_by\s*=\s*(\[[^\]]*\]|\([^)]*\)|[^,()]+)")
SQL_DISTINCT_AGG = re.compile(r"\(\s*DISTINCT\s+([^()]+?)\s+ORDER\s+BY\s+([^()]+?)\)", re.I)
SKIP_INDEX_NGRAM = re.compile(
    r"\bTYPE\s+ngrambf_v1\s*\(\s*(\d+)\s*,\s*(\d+)\s*,[^()]*\)(?:\s+GRANULARITY\s+(\d+))?", re.I)
TABLE_GRANULARITY = re.compile(r"\bindex_granularity\s*=\s*(\d+)", re.I)
SKIP_INDEX_NGRAM_MIN = 4
SKIP_INDEX_ROW_BITS_MIN = 64
CH_ROWS_PER_MARK = 8192

def coarse_ngram_index(text: str, source: str = "") -> str:
    table = TABLE_GRANULARITY.search(source or "")
    rows_per_mark = int(table.group(1)) if table else CH_ROWS_PER_MARK
    for match in SKIP_INDEX_NGRAM.finditer(text or ""):
        size, size_bytes, granularity = int(match.group(1)), int(match.group(2)), int(match.group(3) or 1)
        if (size < SKIP_INDEX_NGRAM_MIN
                or size_bytes * 8 < SKIP_INDEX_ROW_BITS_MIN * max(1, granularity) * max(1, rows_per_mark)):
            return " ".join(match.group(0).split())
    return ""

ENGINE_NOTES = {
    "ch_float_division": ("`%s` divides with / inside an argument that must be an integer. On ClickHouse, / always "
                          "returns Float64, even for two integers, and range(), timeSlots(), repeat(), leftPad(), "
                          "arraySlice(), bitShiftLeft() and toFixedString() reject a Float64 there (Illegal type). "
                          "Use intDiv(a, b), or convert the quotient with toUInt32()/toInt64() before it reaches "
                          "the function, then run the statement once with the sql tool."),
    "ch_window_bucket": ("`%s` is a window over every row of the result (an empty OVER ()). The query also groups "
                         "rows by a time bucket, and a total meant for each bucket needs PARTITION BY the bucket "
                         "expression in that window; without it the total spans all buckets. Check which total "
                         "the task asks for."),
    "ex_fragment_arity": ("`%s`. Ecto checks a fragment when the module compiles and rejects one whose count of ? "
                          "placeholders differs from the number of arguments after the string, so the module does "
                          "not compile. Give every ? exactly one argument, in order."),
    "ar_relation_bind": ("`%s` is a relation bound into a SQL string through IN (?). ActiveRecord loads that "
                         "relation first and writes its ids into the SQL as a literal list: a second query that "
                         "runs before the main one, and conditions added to the main scope later do not reach "
                         "it. Pass the relation as a hash condition instead, where(column: relation) or "
                         "where.not(column: relation), so it stays a subquery inside the one statement."),
    "ch_missing": ("`%s` is not a function on this ClickHouse server, so the query fails the moment it runs. "
                   "Look the real names up with the sql tool (for example SELECT name FROM system.functions "
                   "WHERE name ILIKE '%%quantile%%') and use one that exists; a combinator such as If, State, "
                   "Merge or OrNull attaches to a real base name."),
    "ch_lists": ("`%s` is given three or more argument lists. A ClickHouse parametric aggregate takes at most two, "
                 "name(parameters)(arguments), so the query does not parse. Put every parameter in the first list."),
    "ch_outer_null": ("`%s` tests for NULL next to an outer join on ClickHouse. There, a LEFT, RIGHT or FULL join "
                      "fills the columns of the missing side with their type's default value (0, '', "
                      "1970-01-01 00:00:00), not NULL, unless join_use_nulls = 1 is set, so isNull(), coalesce() "
                      "and ifNull() never see a NULL on that side. To take the side that is present, use "
                      "greatest(a, b) for dates and non-negative numbers (the default is the smallest value) or "
                      "compare with the default itself, if(a = toDateTime(0), b, a); empty() and notEmpty() "
                      "accept only strings, arrays and UUIDs, not dates or numbers. Run the join with the sql "
                      "tool on a key that exists on only one side and check which value the expression returns."),
    "ch_time_slots": ("`%s` builds slots with timeSlots() in a query that works in a time zone. timeSlots() rounds "
                      "each slot down to a multiple of its step in Unix time, not in that zone: with an hour step, a "
                      "zone offset such as +05:45 or +09:30 puts every slot at :45 or :30 local time. Build local "
                      "buckets with toStartOfHour() and addHours() in the zone, or keep a step that divides every "
                      "zone offset and round afterwards, and check a +05:45 zone with the sql tool. A replacement "
                      "has to return the same slots timeSlots() does: every slot from the one holding the start "
                      "through the one holding start + duration, that last one included even when the end falls "
                      "exactly on a slot boundary (timeSlots(toDateTime('2024-01-01 10:00:00', 'UTC'), "
                      "toUInt32(3600), 3600) returns 10:00 and 11:00). From the start's slot `first`, that is "
                      "intDiv(dateDiff('second', first, end), step) + 1 slots; rounding the span up with ceil() or "
                      "+ (step - 1) drops the last slot on every boundary."),
    "ch_slot_count": ("`%s` rounds a span up to count the slots it expands into, so a span that ends exactly on a slot "
                      "boundary gets no slot for its last instant. timeSlots(start, duration, step) includes the slot "
                      "holding start + duration even on a boundary (timeSlots(toDateTime('2024-01-01 10:00:00', "
                      "'UTC'), toUInt32(3600), 3600) returns 10:00 and 11:00). If these slots stand for the instants "
                      "a row covers, build intDiv(dateDiff('second', first, end), step) + 1 of them from the first "
                      "slot, and compare with timeSlots() on the sql tool for an end on a boundary and one second "
                      "before it."),
    "ch_prewhere_pick": ("`%s` keeps one row per key, and this file also moves conditions into PREWHERE (a WHERE "
                         "rewritten to PREWHERE, or optimize_move_to_prewhere = 1). A condition in the same SELECT "
                         "as the pick, in WHERE or PREWHERE, runs on the raw rows before the pick: when the "
                         "duplicates of a key differ in the filtered column, a later duplicate that matches becomes "
                         "the kept row, so the condition no longer tests the row the pick chose. Next to the pick "
                         "keep only conditions on the columns every duplicate shares (the pick's own key); put the "
                         "others in an outer query over the picked rows and keep them out of PREWHERE. ClickHouse "
                         "accepts PREWHERE only in a SELECT that reads a table and rejects it over a subquery "
                         "(ILLEGAL_PREWHERE). Check on the sql tool with a key whose duplicates differ in the "
                         "filtered column."),
    "ch_quantile_unstable": ("`%s` estimates a quantile in a way that depends on how the rows reach it. quantile and "
                             "median (reservoir sampling), quantileTDigest and quantileGK return different values "
                             "for the same rows when the thread count, block size or part layout changes: on "
                             "ClickHouse 25.3 one 95th percentile over a few hundred thousand rows came out four ways across "
                             "max_threads 1 and 8 and two part layouts, while quantileExact, quantileExactWeighted, "
                             "quantileBFloat16 and quantileBFloat16Weighted gave one value every time. When a "
                             "percentile has to come out the same on every run, use one of those, and run the query "
                             "twice on the sql tool with different max_threads."),
    "pg_distinct_order": ("`%s` orders a DISTINCT aggregate by something other than what it aggregates. PostgreSQL "
                          "rejects that (\"in an aggregate with DISTINCT, ORDER BY expressions must appear in "
                          "argument list\"). Order by the aggregated expression itself, or drop DISTINCT and make "
                          "the rows unique another way, then run the statement once."),
    "ch_skip_index": ("`%s` declares an n-gram Bloom filter index that can hardly skip anything. ClickHouse skips a "
                      "block of rows only when an n-gram of the searched term is missing from that block's filter, "
                      "and one filter holds the n-grams of every row in GRANULARITY marks (index_granularity rows "
                      "each, 8192 unless the table sets it). N-grams shorter than four characters recur across any "
                      "few thousand rows of text, so nearly every block keeps them; a filter with fewer than about "
                      "64 bits (8 bytes) for each row it covers fills up with a few n-grams per row and matches "
                      "everything. Use n-grams as long as the shortest term the index has to serve (a term shorter "
                      "than n cannot use the index at all), give the filter at least 8 bytes per covered row, more "
                      "for long text, keep GRANULARITY 1, and check with EXPLAIN indexes = 1 on the sql tool that a "
                      "term absent from the rows drops granules."),
    "ar_limit_filter": ("`%s` adds a condition to a relation that already has limit or offset. ActiveRecord puts that "
                        "condition into the same query, and the database applies WHERE before LIMIT and OFFSET, so "
                        "the result is the first rows that pass the condition, not the rows the limit picked. If the "
                        "condition should test the rows the limit picked, select those rows in a subquery first, for "
                        "example Model.where(id: relation.limit(1).select(:id)).where(...), then run the query on "
                        "data where the first row does not pass the condition."),
}

def engine_hunks(diff: str) -> list:
    hunks: list = []
    for line in (diff or "").splitlines():
        head = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if head:
            hunks.append((int(head.group(1)), [], []))
            continue
        if not hunks or line.startswith(("+++", "---", "\\")):
            continue
        if line.startswith("+"):
            hunks[-1][1].append((len(hunks[-1][2]), line[1:]))
            hunks[-1][2].append(line[1:])
        elif line.startswith(" "):
            hunks[-1][2].append(line[1:])
    return hunks

RELATION_LIMITING = ("limit", "offset")
RELATION_FILTERING = ("where", "rewhere")
RELATION_VALUES = frozenset((
    "pick", "pluck", "first", "last", "take", "find", "find_by", "count", "sum", "minimum", "maximum", "average",
    "calculate", "exists?", "ids", "to_a", "each", "map", "delete_all", "update_all", "destroy_all", "load",
    "size", "length", "any?", "empty?", "none?", "find_each", "in_batches", "first!", "take!", "last!"))
RELATION_CALL = re.compile(r"\.\s*([a-z_][a-z0-9_]*[?!]?)")
RELATION_ASSIGN = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*=(?!=)\s*")
RELATION_CLEARED = re.compile(r"\s*\(\s*nil\s*\)")

def ruby_statements(lines: list, added: set) -> list:
    out: list = []
    text, first, touched, depth = "", 0, False, 0
    for offset, raw in enumerate(lines):
        code = "" if raw.strip().startswith("#") else raw.split(" #")[0].rstrip()
        stripped = code.strip()
        if not stripped:
            if text and depth <= 0:
                out.append((text, first, touched))
                text, touched, depth = "", False, 0
            continue
        if text and (depth > 0 or stripped.startswith(".") or text.endswith(("\\", "."))):
            text += " " + stripped
        else:
            if text:
                out.append((text, first, touched))
            text, first, touched, depth = stripped, offset, False, 0
        touched = touched or offset in added
        depth += sum(stripped.count(c) for c in "([{") - sum(stripped.count(c) for c in ")]}")
    if text:
        out.append((text, first, touched))
    return out

def relation_calls(text: str) -> list:
    calls: list = []
    depth, index, quote = 0, 0, ""
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in "'\"":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == ".":
            found = RELATION_CALL.match(text, index)
            if found:
                name = found.group(1)
                if not (name == "not" and calls and calls[-1][1] == "where" and calls[-1][0] == depth):
                    calls.append((depth, name, found.end()))
                index = found.end()
                continue
        index += 1
    return calls

def filtered_after_limit(text: str) -> str:
    calls = relation_calls(text)
    for position, (depth, name, end) in enumerate(calls):
        if name not in RELATION_LIMITING or RELATION_CLEARED.match(text, end):
            continue
        for later_depth, later, later_end in calls[position + 1:]:
            if later_depth < depth:
                break
            if later_depth > depth:
                continue
            if later in RELATION_VALUES:
                break
            if later in RELATION_FILTERING:
                return later
    return ""

def still_limited(text: str) -> bool:
    limited = False
    for depth, name, end in relation_calls(text):
        if depth != 0:
            continue
        if name in RELATION_LIMITING and not RELATION_CLEARED.match(text, end):
            limited = True
        elif name in RELATION_VALUES:
            limited = False
    return limited

def relation_limit_findings(diff: str) -> list:
    found: list = []
    for start, added, lines in engine_hunks(diff):
        offsets = {offset for offset, _ in added}
        limited: set = set()
        for text, first, touched in ruby_statements(lines, offsets):
            assigned = RELATION_ASSIGN.match(text)
            value = text[assigned.end():] if assigned else text
            if touched:
                filter_name = filtered_after_limit(text)
                if filter_name:
                    found.append(("ar_limit_filter", filter_name, start + first))
                else:
                    for name in sorted(limited):
                        if re.search(r"(^|[\s(=,\[])%s\s*\.\s*(where|rewhere)\b" % re.escape(name), value):
                            found.append(("ar_limit_filter", name + ".where", start + first))
                            break
            if assigned:
                if still_limited(value):
                    limited.add(assigned.group(1))
                else:
                    limited.discard(assigned.group(1))
    return found

def argument_groups(text: str, index: int) -> int:
    groups = 0
    while index < len(text) and text[index] == "(":
        depth, cursor = 0, index
        while cursor < len(text):
            if text[cursor] == "(":
                depth += 1
            elif text[cursor] == ")":
                depth -= 1
                if depth == 0:
                    break
            cursor += 1
        if depth:
            return groups
        groups += 1
        index = cursor + 1
        while index < len(text) and text[index] in " \t":
            index += 1
    return groups

class ClickHouseNames:
    def __init__(self, rows: list, combinators: list) -> None:
        self.exact: dict = {}
        self.folded: set = set()
        for name, aggregate, insensitive in rows:
            self.exact[name] = bool(aggregate)
            if insensitive:
                self.folded.add(name.lower())
        self.combinators = sorted({c for c in combinators if c}, key=len, reverse=True)
        self.from_bundle = False

    def __bool__(self) -> bool:
        return bool(self.exact)

    def aggregate(self, name: str) -> bool:
        return self.exact.get(name, False)

    @classmethod
    def bundled(cls) -> "ClickHouseNames":
        names = cls([(n, True, False) for n in CH_BUNDLED_AGGREGATES]
                    + [(n, False, False) for n in CH_BUNDLED_FUNCTIONS], CH_BUNDLED_COMBINATORS)
        names.from_bundle = True
        return names

    def base_of(self, name: str) -> str:
        current, changed = name, True
        while changed:
            changed = False
            for suffix in self.combinators:
                if current.endswith(suffix) and len(current) > len(suffix) and current not in self.exact:
                    current, changed = current[: -len(suffix)], True
                    break
        return current

    def known(self, name: str) -> bool:
        if name in self.exact or name.lower() in self.folded:
            return True
        pending, seen = [name], set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            for suffix in self.combinators:
                if current.endswith(suffix) and len(current) > len(suffix):
                    base = current[: -len(suffix)]
                    if self.exact.get(base):
                        return True
                    pending.append(base)
        return False

def clickhouse_call_findings(diff: str, names: "ClickHouseNames") -> list:
    found: list = []
    if not names:
        return found
    for start, added, _ in engine_hunks(diff):
        for offset, text in added:
            if CODE_COMMENT.match(text):
                continue
            for match in CALL_NAME.finditer(text):
                name = match.group(1)
                if not CH_FAMILY.match(name):
                    continue
                if not names.known(name):
                    base = names.base_of(name)
                    if not names.from_bundle or (base.endswith("Weighted") and names.aggregate(base[: -len("Weighted")])):
                        found.append(("ch_missing", name, start + offset))
                elif names.aggregate(name) or name.endswith(("If", "State", "Merge", "OrNull")):
                    if argument_groups(text, match.end() - 1) >= 3:
                        found.append(("ch_lists", name, start + offset))
    return found

def order_terms(written: str) -> list:
    inner = written.strip().strip("[]()")
    terms = []
    for part in inner.split(","):
        term = part.strip().strip("'\"").lstrip("-")
        term = re.sub(r"^F\(\s*['\"]([^'\"]+)['\"]\s*\)(?:\.(?:asc|desc)\(\))?$", r"\1", term)
        if term:
            terms.append(term)
    return terms

def distinct_order_mismatch(text: str) -> bool:
    for pattern in (DJANGO_DISTINCT_AGG, DJANGO_ORDER_FIRST, DJANGO_DISTINCT_TAIL):
        for match in pattern.finditer(text):
            argument = match.group(1).strip().strip("'\"")
            terms = order_terms(match.group(2))
            if terms and any(term != argument for term in terms):
                return True
    for match in SQL_DISTINCT_AGG.finditer(text):
        argument = " ".join(match.group(1).split()).lower()
        terms = [" ".join(t.split()).lower() for t in re.split(r",", match.group(2))]
        terms = [re.sub(r"\s+(?:asc|desc)$", "", t) for t in terms]
        if any(term and term != argument for term in terms):
            return True
    return False

INTEGER_ARGUMENT_CALL = re.compile(
    r"\b(range|timeSlots|repeat|leftPad|rightPad|arraySlice|bitShiftLeft|bitShiftRight|toFixedString)\s*\(")


# --- governance/kit.py ---
class Finished(Exception):
    pass

def submission_faults(tree: Tree, statement: str) -> list[str]:
    """Cheap checks independent of the optional baseline-suite machinery."""
    patch = tree.diff(10.0)
    if not patch.strip():
        return ["The working tree has no changes."]
    code, out = run_git_command(["diff", "--check", tree.base, "--"], tree.root, 5.0)
    faults = [clip_output(out, 1500)] if code else []
    code, out = run_git_command(["diff", "--name-only", "-z", tree.base, "--"], tree.root, 5.0)
    if code:
        return faults + ["Could not enumerate changed files."]
    scope = scope_targets(statement, tree.root)
    rules = contract_rules(statement)
    for path in (p for p in out.split("\0") if p):
        if scope and not scope_allows(path, scope):
            faults.append("%s is outside the task's explicit file scope." % path)
        full = tree.absolute(path)
        if not path.endswith(".py") or not os.path.isfile(full):
            continue
        raw = open(full, "rb").read()
        try:
            compile(raw, path, "exec")
        except (SyntaxError, ValueError) as error:
            faults.append("%s: %s" % (path, error))
            continue
        # Compare original bytes without Git's text/newline conversion.
        code, _ = run_git_command(["cat-file", "-e", "%s:%s" % (tree.base, path)], tree.root, 5.0)
        if code:
            if rules["method"]:
                faults.append("New file %s is outside a method-only change." % path)
            continue
        before = subprocess.run([GIT_COMMAND, "show", "%s:%s" % (tree.base, path)],
                                cwd=tree.root, capture_output=True, timeout=5.0, check=True).stdout
        try:
            old_ast, new_ast = ast.parse(before), ast.parse(raw)
        except SyntaxError:
            continue  # A task may ask to repair a pre-existing syntax error.
        if rules["imports"]:
            def imports(source, module):
                lines = source.splitlines(keepends=True)
                return [b"".join(lines[n.lineno - 1:n.end_lineno])
                        for n in ast.walk(module) if isinstance(n, (ast.Import, ast.ImportFrom))]
            if imports(before, old_ast) != imports(raw, new_ast):
                faults.append("%s: the task freezes imports, but they changed." % path)
        if rules["method"] and rules["targets"]:
            def outside(source, module):
                lines = source.splitlines(keepends=True)
                matches = [n for n in ast.walk(module)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and n.name in rules["targets"]]
                # Ambiguous names are reported to the model by the existing
                # domain checks; do not invent an exact scope here.
                if len(matches) != len(rules["targets"]):
                    return None
                for n in sorted(matches, key=lambda n: n.lineno, reverse=True):
                    start = min([n.lineno] + [d.lineno for d in n.decorator_list])
                    lines[start - 1:n.end_lineno] = [b"<allowed-definition>\n"]
                return b"".join(lines)
            left, right = outside(before, old_ast), outside(raw, new_ast)
            if left is not None and right is not None and left != right:
                faults.append("%s: bytes outside the permitted definition changed." % path)
        faults.extend(contract_faults(path, before.decode("utf-8-sig"),
                                      raw.decode("utf-8-sig"), statement))
    return faults[:6]

class Kit:
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 warden: Warden | None = None, label: str = "",
                 findings: "FindingMap | None" = None,
                 database: "Database | None" = None) -> None:
        self.tree = tree
        self.database = database
        self.pool = pool
        self.allowance = allowance
        self.warden = warden
        self.findings = findings
        self.seen: dict[str, int] = {}
        self.edit_all = Beacon("editall")
        self.bg = Beacon("bgshell")
        self.conform = Beacon("conform")
        self.fence = Beacon("fence")
        self.label = label
        self.conform_state = "armed" if SUBMIT_CONFORM else "off"
        self.conform_edits = 0
        self.engine = Beacon("engine")
        self.engine_noted: set = set()
        self.engine_asked = False
        self.bundled_names: "ClickHouseNames | None" = None
        self.unbound = Beacon("names")
        self.names_noted: set = set()
        self.names_asked = False
        self.contract = Beacon("contract")
        self.contract_noted: set = set()

    def note_findings(self, command: str, out: str) -> None:
        if self.findings is None:
            return
        try:
            self.findings.observe(command, out)
        except BaseException:
            self.findings.beacon.skipped("the output could not be read")

    def note_read(self, what: str) -> None:
        log_message("[READ]%s %s" % (" " + self.label if self.label else "", what))

    def run(self, name: str, args: dict) -> str:
        if name not in {s["function"]["name"] for s in TOOL_SCHEMAS}:
            raise ToolFault("no tool named %s" % name)
        handler = getattr(self, "do_" + name, None)
        if handler is None:
            raise ToolFault("no tool named %s" % name)
        return handler(args)

    def guard_repeat(self, key: str) -> None:
        self.seen[key] = self.seen.get(key, 0) + 1
        if self.seen[key] > REPEAT_READ_CEILING:
            raise ToolFault(
                "this exact call was already answered %d times and nothing has changed "
                "since. Scroll up and use the earlier result." % (self.seen[key] - 1)
            )

    def do_read_file(self, args: dict) -> str:
        path = str(args.get("path") or "")
        start = args.get("start")
        count = args.get("count")
        self.guard_repeat("read:%s:%s:%s" % (path, start, count))
        text = self.tree.read(path)
        lines = text.splitlines()
        first = max(1, int(start or 1))
        wanted = int(count) if count and int(count) > 0 else 0
        asked = min(len(lines), first + wanted - 1) if wanted else len(lines)
        rows, used, last = [], 0, first - 1
        for n in range(first, asked + 1):
            row = "%6d\t%s" % (n, lines[n - 1])
            if rows and used + len(row) + 1 > READ_OUTPUT_CAP:
                break
            if not rows:
                row = clip_output(row, READ_OUTPUT_CAP, "line")
            rows.append(row); used += len(row) + 1; last = n
        if not rows:
            served = ("%s is empty" % path if not lines
                      else "%s has %d line(s); start=%d is past the end"
                      % (path, len(lines), first))
            self.note_read("read_file %s:%d- of %d -> %dc"
                           % (path, first, len(lines), len(served)))
            return served
        while True:
            head = "%s lines %d-%d of %d" % (path, first, last, len(lines))
            if last < asked:
                head += " -- pass start=%d to read on" % (last + 1)
            if len(head) + 1 + used <= READ_OUTPUT_CAP:
                break
            if len(rows) > 1:
                used -= len(rows.pop()) + 1
                last -= 1
                continue
            rows[0] = clip_output(rows[0], max(0, READ_OUTPUT_CAP - len(head) - 1), "line")
            used = len(rows[0]) + 1
            break
        served = head + "\n" + "\n".join(rows)
        self.note_read("read_file %s:%d-%d of %d -> %dc"
                       % (path, first, last, len(lines), len(served)))
        return served

    def do_outline(self, args: dict) -> str:
        path = str(args.get("path") or "")
        self.guard_repeat("outline:%s" % path)
        text = self.tree.read(path)
        try:
            rows = outline_source(text)
        except SyntaxError as bad:
            raise ToolFault("%s does not parse as Python around line %s, so it has "
                            "no index; read it instead" % (path, bad.lineno))
        if not rows:
            raise ToolFault("%s defines nothing, so an index of it would be empty; "
                            "read it instead" % path)
        served = clip_output("%s, %d lines, %d definitions\n" % (path, len(text.splitlines()),
                                                          len(rows))
                      + "\n".join(rows), SEARCH_OUTPUT_CAP, "outline")
        self.note_read("outline %s %d defs -> %dc" % (path, len(rows), len(served)))
        return served

    def do_search_text(self, args: dict) -> str:
        pattern = str(args.get("pattern") or "")
        where = str(args.get("path") or ".")
        mode = str(args.get("mode") or "content")
        include = args.get("include")
        self.guard_repeat("grep:%s:%s:%s:%s" % (pattern, where, mode, include))
        cmd = ["grep", "-rEn", "--binary-files=without-match"]
        if mode == "files":
            cmd.append("-l")
        elif mode == "count":
            cmd.append("-c")
        for skip in (".git", "node_modules", ".venv", "__pycache__"):
            cmd.append("--exclude-dir=" + skip)
        if include:
            cmd.append("--include=" + str(include))
        if SEARCH_LIMIT and mode == "content":
            around = args.get("context")
            if around:
                cmd.append("-C%d" % max(0, min(20, int(around))))
        cmd += ["--", pattern, where]
        try:
            done = subprocess.run(
                cmd, cwd=self.tree.root, capture_output=True, text=True, timeout=60, errors="replace"
            )
        except subprocess.TimeoutExpired:
            raise ToolFault("search timed out; narrow the pattern or the path")
        out = done.stdout or ""
        if not out.strip():
            self.note_read("search_text %r %s -> no matches" % (pattern, mode))
            return "no matches for %r under %s" % (pattern, where)
        if SEARCH_LIMIT:
            rows = out.splitlines()
            head = int(args.get("head_limit") or SEARCH_HEAD_LIMIT)
            if len(rows) > head:
                out = "\n".join(rows[:head]) + (
                    "\n... %d more matching lines; narrow the pattern or the path\n"
                    % (len(rows) - head))
        served = clip_output(out, SEARCH_OUTPUT_CAP, "matches")
        self.note_read("search_text %r %s -> %dc" % (pattern, mode, len(served)))
        return served

    def do_find_files(self, args: dict) -> str:
        import fnmatch
        pattern = str(args.get("pattern") or "*")
        self.guard_repeat("glob:%s" % pattern)
        code, out = run_git_command(["ls-files"], self.tree.root, 30)
        if code != 0:
            raise ToolFault("could not list tracked files")
        hits = [p for p in out.splitlines() if fnmatch.fnmatch(p, pattern)]
        if not hits:
            normalise_text = pattern if pattern.startswith("*") else "*" + pattern
            hits = [p for p in out.splitlines() if fnmatch.fnmatch(p, normalise_text)]
        if not hits:
            return "no tracked file matches %s" % pattern
        return clip_output("\n".join(hits[:400]), SEARCH_OUTPUT_CAP, "paths")

    def do_edit(self, args: dict) -> str:
        path = str(args.get("path") or "")
        old = str(args.get("old") or "")
        new = str(args.get("new") or "")
        every = bool(args.get("replace_all")) and REPLACE_ALL
        if not old:
            raise ToolFault("old must not be empty; use create_file to write a whole file")
        text = self.tree.read(path)
        hits = text.count(old)
        if hits == 0:
            raise ToolFault("that exact text is not in %s; read the file again and copy it verbatim" % path)
        if hits > 1 and not every:
            raise ToolFault(
                "that text occurs %d times in %s. Either extend it until it is unique, "
                "or pass replace_all=true if all %d should change the same way." % (hits, path, hits)
            )
        if every and hits > 1:
            self.edit_all.fired("%s x%d" % (path, hits))
            before = self.edit_all.artefact("before", text)
        else:
            before = ""
        updated = text.replace(old, new) if every else text.replace(old, new, 1)
        self.tree.write(path, updated)
        self.seen.clear()
        self.allowance.edits += 1
        if before:
            self.edit_all.outcome(before, updated)
        note = self.compile_check(path)
        if self.warden is not None:
            note += self.warden.edit_note(path)
        note += self.engine_note(path)
        note += self.name_note(path)
        note += self.contract_note(path)
        return "edited %s (%d occurrence%s)%s" % (path, hits if every else 1, "" if hits == 1 else "s", note)

    def do_create_file(self, args: dict) -> str:
        path = str(args.get("path") or "")
        self.tree.write(path, str(args.get("content") or ""))
        self.seen.clear()
        self.allowance.edits += 1
        note = self.compile_check(path)
        if self.warden is not None:
            note += self.warden.edit_note(path)
        note += self.engine_note(path)
        note += self.name_note(path)
        note += self.contract_note(path)
        return "wrote %s%s" % (path, note)

    def contract_note(self, path: str) -> str:
        if (not CONTRACT_EDIT_NOTES or self.warden is None or not path
                or ENVELOPE_JUNK.search(path) or self.allowance.clock_left() < HINT_EDIT_MIN_SEC):
            return ""
        warden = self.warden
        if hasattr(warden, "reread_scope"):
            warden.reread_scope()
        scope_list = getattr(warden, "scope_list", None) or []
        if not hasattr(warden, "original") or not hasattr(warden, "reach_faults"):
            return ""
        faults: list = []
        try:
            if scope_list and not scope_allows(path, scope_list):
                faults.append("The task confines the change to %s, and this edit changes %s. Everything outside "
                              "that scope must be exactly as it was when you finish: put %s back and make the "
                              "change inside the stated scope." % (", ".join(p for _, p in scope_list[:4]),
                                                                    path, path))
            elif path.endswith(".py") and not TEST_PATH.search(path):
                before = warden.original(path)
                if before is not None:
                    after = self.tree.read(path)
                    faults.extend(contract_faults(path, before, after, warden.statement, getattr(warden, "read", None)))
                    faults.extend(warden.reach_faults(path, before, after))
                    faults.extend(scope_edit_notes(path, before, after, warden.statement, getattr(warden, "read", None)))
        except Exception as error:
            self.contract.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        fresh = []
        for fault in faults:
            key = contract_key(fault)
            if key not in self.contract_noted:
                self.contract_noted.add(key)
                fresh.append(fault)
        if not fresh:
            return ""
        self.contract.fired("on edit: %d stated limit(s) broken in %s" % (len(fresh), path))
        return "\n\nNote on the change just made (shown once): " + " ".join(fresh[:3])

    def compile_check(self, path: str) -> str:
        suffix = os.path.splitext(path)[1].lower()
        argv = SYNTAX_CHECKS.get(suffix)
        if not argv or not shutil.which(argv[0]):
            return ""
        full = self.tree.absolute(path)
        if any("{path}" in part for part in argv):
            argv = [part.replace("{path}", json.dumps(full)) for part in argv]
        else:
            argv = argv + [full]
        room = min(20.0, self.allowance.clock_left() - 5.0)
        if room < 3.0:
            return ""
        try:
            done = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=room,
            )
        except subprocess.TimeoutExpired:
            return ""
        if done.returncode == 0:
            return ""
        markers = SYNTAX_MARKERS.get(suffix)
        if markers and not any(m in (done.stderr or "") + (done.stdout or "") for m in markers):
            return ""
        return "\n\nWARNING: the file no longer parses:\n" + clip_output(done.stderr or "", 1200, "error")

    def do_bash(self, args: dict) -> str:
        command = str(args.get("command") or "")
        self.seen.clear()  # Shells may edit files or generate fresh check output.
        if not command.strip():
            raise ToolFault("command must not be empty")
        outward = NETWORK_COMMAND.search(command) if NETWORK_FENCE else None
        if outward:
            self.fence.fired("refused %r" % outward.group(1))
            raise ToolFault(
                "%s is not available here. Everything this task needs is "
                "already in the tree: the repository, its history, and its "
                "tests. Nothing outside it is reachable, and the change you "
                "are asked to make is not published anywhere -- work from the "
                "code in front of you." % outward.group(1)
            )
        written = shell_database_write(command)
        if written:
            self.fence.fired("kept the database: %s" % written)
            raise ToolFault(DATABASE_KEPT % written)
        blocked = HISTORY_GIT.search(command)
        if blocked:
            raise ToolFault(
                "git %s is not available here. Your changes are collected from the working "
                "tree as it stands, so moving or discarding them loses the work. Read-only "
                "git (status, diff, log, grep, show, ls-files) is fine." % blocked.group(1)
            )
        want_bg = bool(args.get("background")) and ASYNC_SHELL
        asked = float(args.get("timeout") or 120)
        room = self.allowance.clock_left() - WALL_RESERVE_SEC
        if room < 5.0:
            raise ToolFault(
                "not enough of the run left to wait on a command; make the "
                "change you already have evidence for, or submit")
        budget = max(5.0, min(asked, SHELL_BUDGET_CEILING_SEC, room))
        if want_bg:
            job = self.pool.start(command)
            self.bg.fired("started %s: %s" % (job.name, command[:120]))
            return "started in the background as %s; collect it with bash_poll" % job.name
        job = self.pool.start(command)
        done, out = job.wait(budget)
        if done:
            self.pool.jobs.pop(job.name, None)
            report_shell(job, out)
            self.note_findings(command, out)
            status = job.process.returncode
            job.stop()
            return "exit_code=%s\n%s" % (status, clip_output(out, SHELL_OUTPUT_CAP, "shell output"))
        self.bg.fired("kept %s alive past %.0fs: %s" % (job.name, budget, command[:120]))
        return (
            clip_output(out, SHELL_OUTPUT_CAP, "partial output")
            + "\n\n[still running after %.0fs, moved to the background as %s; "
            "keep working and collect it later with bash_poll]" % (budget, job.name)
        )

    def do_bash_poll(self, args: dict) -> str:
        job = self.pool.get(str(args.get("job") or ""))
        room = self.allowance.clock_left() - WALL_RESERVE_SEC
        if not job.finished() and room > 1.0:
            job.wait(min(BACKGROUND_POLL_WAIT_SEC, room))
        out = job.drain()
        if not out.endswith(STILL_RUNNING):
            self.pool.jobs.pop(job.name, None)
            report_shell(job, out)
            self.note_findings(job.command, out)
            status = job.process.returncode
            job.stop()
            return "exit_code=%s\n%s" % (status, clip_output(out, SHELL_OUTPUT_CAP, "shell output"))
        return clip_output(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)"

    def do_sql(self, args: dict) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ToolFault("query must not be empty")
        if self.database is None:
            raise ToolFault("no database connection is known; use bash with psql or clickhouse-client and the repository's own configuration")
        conn = self.database.pick(args.get("database"))
        if conn is None:
            raise ToolFault("no database answered a probe; read the configuration files listed at the start and connect with bash")
        explain = bool(args.get("explain"))
        budget = max(5.0, min(90.0, self.allowance.clock_left() - WALL_RESERVE_SEC))
        if conn.engine == "postgresql":
            control = transaction_control(query)
            if control:
                raise ToolFault("%s is not needed here: every call already runs in one transaction "
                                "that is rolled back when it ends, so nothing is ever committed. "
                                "Send the statements on their own." % control)
            inner = query.strip()
            if explain and not inner.upper().startswith("EXPLAIN"):
                inner = "EXPLAIN (ANALYZE, BUFFERS, VERBOSE) %s" % inner.rstrip(";")
            body = "BEGIN;\n%s\n;\nROLLBACK;\n" % inner
            if conn.tool == "psql" or shutil.which("psql"):
                argv = ["psql", conn.url, "-X", "-v", "ON_ERROR_STOP=1", "-P", "pager=off", "-f", "-"]
                try:
                    done = subprocess.run(argv, input=body, cwd=self.tree.root, capture_output=True, text=True, errors="replace",
                                          timeout=budget, env={**os.environ, "PGCONNECT_TIMEOUT": "5"})
                    code, out = done.returncode, (done.stdout or "") + (done.stderr or "")
                except subprocess.TimeoutExpired:
                    code, out = 124, "timed out after %.0fs" % budget
            else:
                snippet = ("import sys\ntry:\n    import psycopg as pg\nexcept ImportError:\n    import psycopg2 as pg\n"
                           "c = pg.connect(sys.argv[1]); c.autocommit = False\ncur = c.cursor()\n"
                           "for stmt in [s for s in sys.stdin.read().split(';') if s.strip()]:\n"
                           "    cur.execute(stmt)\n"
                           "    if cur.description:\n        print(' | '.join(d[0] for d in cur.description))\n"
                           "        for row in cur.fetchall(): print(' | '.join(str(v) for v in row))\n"
                           "    else: print('[%s rows affected]' % cur.rowcount)\n"
                           "c.rollback()\n")
                try:
                    done = subprocess.run([sys.executable, "-c", snippet, conn.url], input=body, cwd=self.tree.root, capture_output=True,
                                          text=True, errors="replace", timeout=budget)
                    code, out = done.returncode, (done.stdout or "") + (done.stderr or "")
                except subprocess.TimeoutExpired:
                    code, out = 124, "timed out after %.0fs" % budget
        else:
            verb = clickhouse_write(query)
            if verb:
                raise ToolFault(DATABASE_KEPT % verb)
            body = query.rstrip().rstrip(";")
            if explain and not body.lstrip().upper().startswith("EXPLAIN"):
                body = "EXPLAIN indexes = 1 " + body
            if conn.tool == "clickhouse-client":
                argv = ["clickhouse-client", "--host", conn.host, "--user", conn.user or "default", "--multiquery", "--format", "PrettyCompact"]
                if conn.password:
                    argv += ["--password", conn.password]
                if conn.database:
                    argv += ["--database", conn.database]
                try:
                    done = subprocess.run(argv, input=body, cwd=self.tree.root, capture_output=True, text=True, errors="replace", timeout=budget)
                    code, out = done.returncode, (done.stdout or "") + (done.stderr or "")
                except subprocess.TimeoutExpired:
                    code, out = 124, "timed out after %.0fs" % budget
            else:
                url = "http://%s:%s/" % (conn.host, conn.port or "8123")
                request = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
                request.add_header("X-ClickHouse-User", conn.user or "default")
                request.add_header("X-ClickHouse-Key", conn.password or "")
                if conn.database:
                    request.add_header("X-ClickHouse-Database", conn.database)
                try:
                    with urllib.request.urlopen(request, timeout=budget) as response:
                        code, out = 0, response.read().decode("utf-8", "replace")
                except urllib.error.HTTPError as error:
                    code, out = error.code, error.read().decode("utf-8", "replace")[:4000]
                except Exception as error:
                    code, out = 1, "%s: %s" % (type(error).__name__, error)
        log_message("[SQL] %s rc=%s %dc :: %s" % (conn.label, code, len(out), compact_text(query)[:100]))
        return "[%s via %s, exit %s]\n%s" % (conn.label, conn.tool or "?", code, clip_output(out, SQL_OUTPUT_CAP, "rows") or "(no output)")

    def engines(self) -> set:
        statement = self.warden.statement if self.warden is not None else ""
        found = set()
        if re.search(r"clickhouse", statement or "", re.I):
            found.add("clickhouse")
        if re.search(r"postgres", statement or "", re.I):
            found.add("postgresql")
        if not found and self.database is not None:
            found = {c.engine for c in self.database.usable()}
            if not found and self.database.engine_hint:
                found.add(self.database.engine_hint)
            if not found:
                found = {c.engine for c in self.database.connections if configured_server(c)}
        return found

    def engine_diff(self, path: str) -> str:
        base = self.tree.base or "HEAD"
        code, diff = run_git_command(["diff", "-U%d" % ENGINE_FACT_CONTEXT, base, "--", path], self.tree.root,
                         max(2.0, min(20.0, self.allowance.clock_left() - 10.0)))
        if code == 0 and diff.strip():
            return diff
        known, _ = run_git_command(["cat-file", "-e", "%s:%s" % (base, path)], self.tree.root, 10)
        if known == 0:
            return ""
        try:
            lines = self.tree.read(path).splitlines()
        except ToolFault:
            return ""
        return "@@ -0,0 +1,%d @@\n" % len(lines) + "\n".join("+" + line for line in lines)

    def engine_findings(self, paths: list) -> list:
        engines = self.engines()
        names = None
        if "clickhouse" in engines:
            names = self.database.clickhouse_names() if self.database is not None else None
            if not names:
                if self.bundled_names is None:
                    self.bundled_names = ClickHouseNames.bundled()
                names = self.bundled_names
        found: list = []
        for path in paths:
            if ENVELOPE_JUNK.search(path or "") or TEST_PATH.search(path or ""):
                continue
            diff = self.engine_diff(path)
            if not diff:
                continue
            if names:
                found.extend((kind, name, line, path) for kind, name, line in clickhouse_call_findings(diff, names))
            if "clickhouse" in engines:
                try:
                    source = self.tree.read(path)
                except ToolFault:
                    source = ""
                found.extend((kind, name, line, path) for kind, name, line in engine_fact_findings(diff, "clickhouse", source))
            if "postgresql" in engines or not engines:
                found.extend((kind, name, line, path) for kind, name, line in engine_fact_findings(diff, "postgresql"))
            if path.endswith(".rb"):
                found.extend((kind, name, line, path) for kind, name, line in relation_limit_findings(diff))
                found.extend((kind, name, line, path) for kind, name, line in relation_bind_findings(diff))
            if path.endswith((".ex", ".exs")):
                found.extend((kind, name, line, path) for kind, name, line in fragment_arity_findings(diff))
        return found

    @staticmethod
    def engine_text(found: list) -> list:
        said, out = set(), []
        for kind, name, line, path in found:
            if kind in said:
                continue
            said.add(kind)
            out.append(ENGINE_NOTES[kind] % name)
        return out

    def engine_note(self, path: str) -> str:
        if not ENGINE_FACTS or self.allowance.clock_left() < HINT_EDIT_MIN_SEC:
            return ""
        try:
            found = [f for f in self.engine_findings([path]) if (f[0], f[1]) not in self.engine_noted]
        except Exception as error:
            self.engine.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.engine_noted.update((kind, name) for kind, name, _, _ in found)
        self.engine.fired("on edit: " + ", ".join("%s %s at %s:%d" % (k, n, p, l) for k, n, l, p in found[:4]))
        return "\n\nNote on the change just made (shown once): " + " ".join(self.engine_text(found))

    def engine_faults(self) -> str:
        if not ENGINE_FACTS or self.engine_asked:
            return ""
        if self.allowance.clock_left() < ENGINE_FACT_MIN_SEC:
            self.engine.skipped("too little of the run left to act on it")
            return ""
        paths = list(self.tree.written)
        try:
            if self.warden is not None and self.allowance.clock_left() > 60.0:
                paths = self.warden.changed_paths() or paths
            found = self.engine_findings(paths)
        except Exception as error:
            self.engine.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.engine_asked = True
        self.engine.fired("held hand-in: " + ", ".join("%s %s at %s:%d" % (k, n, p, l) for k, n, l, p in found[:4]))
        return (ENGINE_HEAD + "\n\n" + "\n\n".join("- " + note for note in self.engine_text(found))
                + "\n\n" + HINT_TAIL)

    def name_findings(self, paths: list) -> list:
        found: list = []
        for path in [p for p in paths if (p or "").endswith(".py")][:NAME_CHECK_MAX_FILES]:
            if ENVELOPE_JUNK.search(path) or TEST_PATH.search(path):
                continue
            diff = self.engine_diff(path)
            lines = added_line_numbers(diff)
            if not lines:
                continue
            try:
                source = self.tree.read(path)
            except ToolFault:
                continue
            found.extend((name, line, why, path)
                         for name, line, why in unbound_names(self.tree.root, path, source, lines))
        return found

    def name_note(self, path: str) -> str:
        if (not NAME_CHECK or not (path or "").endswith(".py")
                or self.allowance.clock_left() < HINT_EDIT_MIN_SEC):
            return ""
        try:
            found = [f for f in self.name_findings([path]) if (f[3], f[0]) not in self.names_noted]
        except Exception as error:
            self.unbound.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.names_noted.update((f[3], f[0]) for f in found)
        self.unbound.fired("on edit: " + ", ".join("%s at %s:%d" % (n, p, l) for n, l, _, p in found[:4]))
        return ("\n\nNote on the change just made (shown once): "
                + " ".join(NAME_NOTE % (n, p, l, why) for n, l, why, p in found[:3]))

    def name_faults(self) -> str:
        if not NAME_CHECK or self.names_asked:
            return ""
        if self.allowance.clock_left() < ENGINE_FACT_MIN_SEC:
            self.unbound.skipped("too little of the run left to act on it")
            return ""
        paths = list(self.tree.written)
        try:
            if self.warden is not None and self.allowance.clock_left() > 60.0:
                paths = self.warden.changed_paths() or paths
            found = self.name_findings(paths)
        except Exception as error:
            self.unbound.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.names_asked = True
        self.unbound.fired("held hand-in: " + ", ".join("%s at %s:%d" % (n, p, l) for n, l, _, p in found[:4]))
        return (NAME_HEAD + "\n\n" + "\n\n".join("- " + NAME_NOTE % (n, p, l, why) for n, l, why, p in found[:3])
                + "\n\n" + HINT_TAIL)

    def do_submit(self, args: dict) -> str:
        pending = [job.name for job in self.pool.jobs.values() if not job.finished()]
        if pending:
            return "Collect the running checks before submit: " + ", ".join(pending)
        faults = submission_faults(self.tree, self.warden.statement if self.warden else "")
        if faults:
            return "Not submitted. Repair these concrete patch failures:\n" + "\n".join(faults[:4])
        held = self.engine_faults() or self.name_faults()
        if held:
            return held
        faults = self.warden.verdict() if self.warden else []
        if not faults:
            if self.warden is None or not self.warden.stood_down:
                note = self.conform_note()
                if note:
                    return note
            raise Finished(str(args.get("summary") or ""))
        if faults[0].startswith(HINT_HEAD):
            return faults[0]
        return ("Not handed in. The task states conditions this run can "
                "check itself, and they are not met yet:\n\n"
                + "\n\n".join(faults[:3])
                + "\n\nThere is budget left. Fix this and call submit again.")

    def conform_note(self) -> str | None:
        if self.conform_state == "asked":
            self.conform_state = "done"
            self.conform.fired("resubmitted after %d further edit(s)"
                               % (self.allowance.edits - self.conform_edits))
            return None
        if self.conform_state != "armed":
            return None
        if self.allowance.clock_left() < CONFORM_MIN_WALL_SEC:
            self.conform_state = "done"
            self.conform.skipped("too little of the run left to act on the answer")
            return None
        self.conform_state = "asked"
        self.conform_edits = self.allowance.edits
        self.conform.fired("hand-in paused to re-read the statement's requirements")
        return ("Not handed in yet - one check before it goes, and it happens only "
                "once. Re-read the problem statement and collect every specific "
                "detail it requires: orderings, boundaries, defaults, exact values, "
                "which failures are tolerated. For each one, point at the code that "
                "satisfies it as the tree now stands - a line of your diff, or code "
                "that was already right and needed no change. Fix any requirement "
                "nothing satisfies; a detail the statement spells out holds to the "
                "letter. Then confirm your diff changed nothing else's meaning: a "
                "block you moved still does exactly what it did. When both hold, "
                "call submit again.")


# --- governance/contracts.py ---
def patch_shape(patch: str) -> str:
    files = hunks = 0
    added: list = []
    removed: list = []
    path_is_inside = False
    for line in (patch or "").split("\n"):
        if line.startswith("diff --git "):
            files += 1
            path_is_inside = False
        elif line.startswith("@@ "):
            hunks += 1
            path_is_inside = True
        elif path_is_inside and line.startswith("+"):
            added.append(line[1:].strip())
        elif path_is_inside and line.startswith("-"):
            removed.append(line[1:].strip())
    pool: dict = {}
    for line in added:
        pool[line] = pool.get(line, 0) + 1
    carried = dropped = 0
    for line in removed:
        if not line or DIFF_TRIVIAL.match(line):
            continue
        if pool.get(line):
            pool[line] -= 1
            carried += 1
        else:
            dropped += 1
    return ("files=%d hunks=%d +%d -%d carried=%d dropped=%d"
            % (files, hunks, len(added), len(removed), carried, dropped))

LINE_SCAN_CAP = 400
FOLD_SHAPES = (
    ("membership-test-gone",
     re.compile(r"\b(?:if|elif|while|assert|and|or|not)\b[^\n]*\bin\b")),
    ("none-vs-falsy", re.compile(r"\bis\s+(?:not\s+)?None\b|[!=]=\s*None\b")),
    ("absent-vs-star", re.compile(r"""["']\*["']""")),
    ("ordering", re.compile(r"\bsorted\(|\.sort\(|\breversed\(|OrderedDict")),
    ("spelling", re.compile(r"\.encode\(|\.decode\(|\bbytes\(|\bint\([^)]*,\s*\d+\)")),
    ("swallowed-failure",
     re.compile(r"\braise\b|\bexcept\s+\w|\bassert\b|\.error\(|\.warning\(")),
)

def fold_report(patch: str) -> str:
    hunks = 0
    dropped: dict = {}
    removed: list = []
    added: list = []

    def close() -> None:
        for name, shape in FOLD_SHAPES:
            if any(shape.search(line) for line in removed) and not any(
                    shape.search(line) for line in added):
                dropped[name] = dropped.get(name, 0) + 1
    path_is_inside = False
    for line in (patch or "").split("\n"):
        if line.startswith("diff --git ") or line.startswith("@@ "):
            if path_is_inside:
                close()
            removed, added = [], []
            path_is_inside = line.startswith("@@ ")
            hunks += line.startswith("@@ ")
        elif path_is_inside and line.startswith("+"):
            added.append(line[1:LINE_SCAN_CAP])
        elif path_is_inside and line.startswith("-"):
            removed.append(line[1:LINE_SCAN_CAP])
    if path_is_inside:
        close()
    return "hunks=%d dropped: %s" % (
        hunks, " ".join("%s=%d" % kv for kv in sorted(dropped.items())) or "none")

def visible_definitions(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []

    def walk(node: ast.AST, prefix: str, path_is_inside: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async" if isinstance(child, ast.AsyncFunctionDef) else "def"
                if not path_is_inside:
                    found.append("%s %s%s" % (kind, prefix, child.name))
                walk(child, prefix + child.name + ".", True)
            elif isinstance(child, ast.ClassDef):
                if not path_is_inside:
                    found.append("class %s%s" % (prefix, child.name))
                walk(child, prefix + child.name + ".", path_is_inside)
            else:
                walk(child, prefix, path_is_inside)
    walk(tree, "", False)
    return sorted(found)

def outline_source(source: str) -> list[str]:
    rows: list[tuple[int, int, int, str]] = []

    def walk(node: ast.AST, depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = ("class" if isinstance(child, ast.ClassDef)
                        else "async def" if isinstance(child, ast.AsyncFunctionDef)
                        else "def")
                rows.append((child.lineno, getattr(child, "end_lineno", child.lineno),
                             depth, "%s %s" % (kind, child.name)))
                walk(child, depth + 1)
            else:
                walk(child, depth)
    walk(ast.parse(source), 0)
    rows.sort()
    return ["%5d-%-5d %s%s" % (start, end, "  " * depth, name)
            for start, end, depth, name in rows]

def python_functions(text: str) -> tuple[dict, dict, dict]:
    lines = text.splitlines(keepends=True)
    owner: dict = {}
    heads: dict = {}
    first: dict = {}

    def visit(node, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            name = (prefix + "." + child.name).lstrip(".") if named else prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top = min([line.lineno for line in child.decorator_list] + [child.lineno])
                body = child.body[0].lineno if child.body else child.lineno + 1
                heads[name] = "".join(lines[top - 1:body - 1])
                for line in range(top, (child.end_lineno or top) + 1):
                    owner[line] = name
                first[name] = ast.dump(child.body[0]) if child.body else ""
            visit(child, name)
    visit(ast.parse(text), "")
    return owner, heads, first

def changed_line_numbers(before: str, after: str) -> tuple[set, set]:
    import difflib
    old, new = before.splitlines(), after.splitlines()
    was, now = set(), set()
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        was.update(range(i1 + 1, i2 + 1))
        now.update(range(j1 + 1, j2 + 1))
    return was, now

def statement_refused_nodes(statement: str) -> set:
    text = " ".join((statement or "").split())
    refused = set()
    categories = (
        (r"loops?", ("For", "AsyncFor", "While")),
        (r"comprehensions?", ("ListComp", "SetComp", "DictComp", "GeneratorExp")),
        (r"lambdas?", ("Lambda",)),
        (r"exception handling", ("Try", "TryStar", "Raise")),
        (r"context managers?", ("With", "AsyncWith")),
    )
    item = r"(?:Python\s+)?(?:" + "|".join(label for label, _ in categories) + ")"
    separator = r"(?:\s*,\s*(?:(?:or|and)\s+)?|\s+(?:or|and)\s+)"
    lead = (r"(?:(?:^|[.!?;:])\s*(?:[-*]\s+|\d+[.)]\s+)?|\b(?:write|implement|express|keep)\b[^.!?;:]*?\s+|,\s*)"
            r"(?:no\s+|without\s+|avoid(?:ing)?\s+|(?:(?:it|the method|the function|the change|you)\s+)?"
            r"(?:must not|should not|may not|cannot|can't|do not|don't|never)\s+"
            r"(?:use|contain|include|have|add|introduce|write)\s+)")
    tail = r"(?:\s+(?:inside|in|within)\s+[^.!?;:]{1,60})?\s*(?=[.!?;:]|$)"
    for match in re.finditer(lead + "(" + item + "(?:" + separator + item + r")*)\b" + tail, text, re.I):
        for label, kinds in categories:
            if re.search(r"\b(?:" + label + r")\b", match[1], re.I):
                refused.update(kinds)
    return refused

BOUNDED_METHOD_NODES = ("AsyncFunctionDef", "Await", "ClassDef", "Delete", "Global", "Lambda",
                        "Match", "Nonlocal", "While", "Yield", "YieldFrom")
DYNAMIC_NAMES = frozenset(("__import__", "breakpoint", "compile", "eval", "exec", "getattr",
                           "setattr", "delattr", "globals", "locals", "vars", "importlib"))
PROCESS_NAMES = frozenset(("subprocess", "multiprocessing", "pty", "system", "popen", "fork",
                           "execv", "execve", "execvp", "spawn", "spawnl", "spawnv", "kill"))
FILESYSTEM_NAMES = frozenset(("open", "shutil", "tempfile", "remove", "unlink", "rename", "replace",
                              "makedirs", "mkdir", "rmdir", "chmod", "write_text", "write_bytes",
                              "rmtree", "copyfile", "copy2"))
NETWORK_NAMES = frozenset(("socket", "requests", "urllib", "httpx", "aiohttp", "smtplib", "ftplib",
                           "urlopen", "http"))
RAW_SQL_NAMES = frozenset(("RawSQL", "raw", "execute", "executemany", "cursor", "connections"))
DB_WRITE_NAMES = frozenset(("bulk_create", "bulk_update", "get_or_create", "update_or_create", "save"))
METHOD_BYTE_CAP = 5000
METHOD_NODE_CAP = 400
BOUNDED_NAME = r"`(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*\(\)`"
BOUNDED_LIST = BOUNDED_NAME + r"(?:\s*(?:,\s*(?:and\s+|or\s+)?|and\s+|or\s+)" + BOUNDED_NAME + r")*"
BOUNDED_PHRASES = (
    r"\b(?:change|edit|modify|touch|rewrite)\s+only\s+(" + BOUNDED_LIST + r")",
    r"\bonly\s+(" + BOUNDED_LIST + r")\s+(?:may|should|can|is to|needs to)\s+"
    r"(?:change|be changed|be edited|be modified|be touched)",
    r"\b(?:limit|confine|restrict)\w*\b(?:[^.]|\.(?!\s))*?\b(?:changes?|edits?|modifications?|work)\s+to\s+"
    r"(?:`[^`]+`\s*(?:,|:|\bin\b|\binside\b|\bwithin\b)\s*)?(" + BOUNDED_LIST + r")",
)

def bounded_targets(text: str) -> list:
    found: list = []

    def add(chunk: str) -> None:
        for _, short in re.findall(r"`((?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*))\(\)`", chunk):
            if short not in found:
                found.append(short)
    for scope in SCOPE_PHRASE.finditer(text):
        for match in re.finditer(r"\bspecifically\s+(" + BOUNDED_LIST + r")", scope.group(1), re.I):
            add(match.group(1))
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for phrase in BOUNDED_PHRASES:
            for match in re.finditer(phrase, sentence, re.I):
                add(match.group(1))
    return found

def contract_rules(statement: str, read: "ScopeRead | None" = None) -> dict:
    text = " ".join((statement or "").split())
    rules: dict = {}
    targets = bounded_targets(text)
    rules["method"] = bool(targets) or bool(re.search(
        r"\b(?:only|just)\s+(?:that|this|the|one|a single)\s+(?:method|function)\b|"
        r"\brest of (?:the|its|that) (?:file|module) unchanged\b|"
        r"\b(?:change|edit|modify)\s+only\s+(?:that|this|the)\s+(?:method|function)\b", text, re.I))
    rules["targets"] = targets
    rules["target"] = targets[0] if targets else ""
    rules["signature"] = bool(re.search(r"\bkeep (?:its|the|that) (?:method |function )?signature\b|"
                                        r"\bsignature (?:must )?(?:remain|stay|be kept)\b", text, re.I))
    rules["imports"] = bool(re.search(
        r"only names the file already imports|including imports|"
        r"\bimports? (?:must |should )?(?:remain|stay|be kept) (?:unchanged|as (?:they|it) (?:are|is))|"
        r"\bdo not (?:add|change|modify|touch)(?: any| new| the)? imports?\b", text, re.I))
    effects = " ".join(m.group(1).lower() for m in re.finditer(
        r"\bdo not (?:add|introduce)\s+([^.]*?)\s+side[- ]effects?", text, re.I))
    rules["dynamic"] = "dynamic" in effects
    rules["process"] = "process" in effects or "repository" in effects
    rules["filesystem"] = "filesystem" in effects or "file system" in effects
    rules["network"] = "network" in effects
    rules["raw_sql"] = "raw sql" in effects or bool(re.search(r"\bdo not (?:add|use|write) raw sql\b", text, re.I))
    rules["writes"] = "database write" in effects or bool(re.search(r"\bdo not (?:add|introduce|perform) (?:any )?database writes\b", text, re.I))
    rules["refused"] = statement_refused_nodes(statement)
    rules["scope"] = []
    if read is not None and read.backed:
        if read.trusted:
            rules["scope"] = list(read.functions)
        if read.unchanged_outside and (read.functions or read.single_unit):
            rules["method"] = True
            for _, short in read.functions:
                if short not in rules["targets"]:
                    rules["targets"].append(short)
            rules["target"] = rules["targets"][0] if rules["targets"] else ""
        for label, _, kinds in SCOPE_BANNED_KINDS:
            if label in read.banned:
                rules["refused"].update(kinds)
    rules["active"] = any(v for k, v in rules.items() if k not in ("target", "targets", "refused", "scope")) or bool(rules["refused"])
    return rules

def _receiver_text(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""

def contract_faults(path: str, before: str, after: str, statement: str,
                    read: "ScopeRead | None" = None) -> list[str]:
    if not path.endswith(".py"):
        return []
    rules = contract_rules(statement, read)
    if not rules["active"]:
        return []
    try:
        compile(before, path, "exec")
    except SyntaxError:
        return []
    try:
        tree = ast.parse(after)
    except SyntaxError as error:
        return ["%s does not parse: %s (line %s). It parsed before this run touched it, "
                "so the edit introduced that." % (path, error.msg, error.lineno)]
    faults: list[str] = []
    was, now = changed_line_numbers(before, after)
    if not was and not now:
        return []
    owner, heads, _ = python_functions(after)
    was_owner, was_heads, _ = python_functions(before)
    changed_nodes = [n for n in ast.walk(tree) if getattr(n, "lineno", 0) in now]
    method_names: list = []
    if rules["method"]:
        scope = rules.get("scope") or []
        in_class_now = scope_class_lines(after, scope) if scope else set()
        in_class_was = scope_class_lines(before, scope) if scope else set()
        owners = {owner.get(n.lineno) for n in changed_nodes if owner.get(n.lineno) or n.lineno not in in_class_now}
        owners |= {was_owner.get(line) for line in was if was_owner.get(line) or line not in in_class_was}
        if None in owners:
            faults.append("The task bounds the change to one method, and this run added or "
                          "removed a line of %s outside any function body. The import block "
                          "counts, whether a name was added to it or one the method no longer "
                          "uses was deleted: everything outside the bounded method must stay "
                          "byte-identical, so put it back and reach other query classes through "
                          "a module the file already imports." % path)
        named = sorted(o for o in owners if o)
        targets = rules["targets"]
        bound = ", ".join("%s()" % t for t in targets) if targets else "one method"
        shorts = [o.rsplit(".", 1)[-1] for o in named]
        covered = bool(scope) and all(scope_covers(o, scope) for o in named)
        if len(named) > 1 and not covered and not (targets and set(shorts) <= set(targets) and len(set(shorts)) == len(shorts)):
            faults.append("The task bounds the change to %s, and this run changed "
                          "%d definitions in %s: %s. Put the whole change inside what the "
                          "task names; a helper method or a nested function counts as a "
                          "separate definition." % (bound, len(named), path, ", ".join(named)))
        else:
            method_names = named
        for method_name in method_names:
            short = method_name.rsplit(".", 1)[-1]
            if targets and short not in targets and not (scope and scope_covers(method_name, scope)):
                faults.append("The task bounds the change to %s, and this run changed %s() in %s."
                              % (bound, short, path))
            if rules["signature"] and heads.get(method_name) != was_heads.get(method_name):
                faults.append("The task says to keep the method signature; the def line or decorators "
                              "of %s in %s changed. Restore the header exactly and keep the change "
                              "in the body." % (short, path))
    if rules["imports"]:
        for node in changed_nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                faults.append("The task says to use only names the file already imports; line %d of %s "
                              "adds an import. Remove it and use what the file already has."
                              % (node.lineno, path))
                break
    seen_effects: set = set()
    for node in changed_nodes:
        label = ""
        name = node.id if isinstance(node, ast.Name) else (node.attr if isinstance(node, ast.Attribute) else "")
        if not name:
            continue
        if rules["dynamic"] and (name in DYNAMIC_NAMES or (isinstance(node, ast.Attribute) and "__" in name)):
            label = "dynamic-code"
        elif rules["process"] and name in PROCESS_NAMES:
            label = "process"
        elif rules["filesystem"] and name in FILESYSTEM_NAMES:
            label = "filesystem"
        elif rules["network"] and name in NETWORK_NAMES:
            label = "network"
        elif rules["raw_sql"] and name in RAW_SQL_NAMES:
            label = "raw SQL"
        elif rules["writes"] and isinstance(node, ast.Attribute) and (
                name in DB_WRITE_NAMES or (name in ("create", "delete", "update") and
                                           re.search(r"objects|_default_manager|\.using\(", _receiver_text(node.value)))):
            label = "database write"
        if label and (label, name) not in seen_effects:
            seen_effects.add((label, name))
            faults.append("The task says not to add %s side effects, and line %d of %s introduces `%s`. "
                          "Express the change without it." % (label, node.lineno, path, name))
    refused: dict = {}
    for node in changed_nodes:
        kind = type(node).__name__
        if kind in rules["refused"] and (not method_names or owner.get(node.lineno) in method_names):
            refused.setdefault(kind, node.lineno)
    if refused:
        faults.append("The task rules out these constructs inside the change, and this run introduces %s in %s. "
                      "Express the change with the constructs the task allows."
                      % (", ".join("%s at line %d" % (CONSTRUCT_WORDS.get(k, k), line)
                                   for k, line in sorted(refused.items(), key=lambda kv: kv[1])), path))
    return faults[:4]

SCOPE_READ_MIN_CLOCK_SEC = 600.0
SCOPE_READ_TRIES = 3
SCOPE_READ_MAX_SEC = 150.0
SCOPE_READ_STATEMENT_CHARS = 24_000
SCOPE_LIMIT_WORDS = re.compile(
    r"\b(?:only|limit(?:s|ed)?|confine[sd]?|restrict(?:s|ed)?|unchanged|untouched|exactly|do not|don't|"
    r"must not|should not|may not|never|no|not|nothing|nowhere|solely|exclusively|avoid|forbid\w*|prohibit\w*|outside|except|"
    r"leave|keep|stay|remain|without)\b", re.I)
SCOPE_OUTSIDE_WORDS = re.compile(
    r"\b(?:unchanged|untouched|exactly as|as it is|as they are|everything else|rest of|nothing else|nowhere else|no other|"
    r"other (?:code|functions?|methods?|files?|definitions?|queries))\b", re.I)
SCOPE_BANNED_KINDS = (
    ("loops", re.compile(r"\bloops?\b", re.I), ("For", "AsyncFor", "While")),
    ("comprehensions", re.compile(r"\bcomprehensions?\b", re.I), ("ListComp", "SetComp", "DictComp", "GeneratorExp")),
    ("lambdas", re.compile(r"\blambdas?\b", re.I), ("Lambda",)),
    ("exception handling", re.compile(r"\bexceptions?\b|\btry\b", re.I), ("Try", "TryStar", "Raise")),
    ("context managers", re.compile(r"\bcontext managers?\b", re.I), ("With", "AsyncWith")),
)
CONSTRUCT_WORDS = {
    "For": "a for loop", "AsyncFor": "an async for loop", "While": "a while loop",
    "ListComp": "a list comprehension", "SetComp": "a set comprehension", "DictComp": "a dict comprehension",
    "GeneratorExp": "a generator expression", "Lambda": "a lambda", "Try": "a try block", "TryStar": "a try block",
    "Raise": "a raise statement", "With": "a with block", "AsyncWith": "an async with block",
    "ClassDef": "a class definition", "Delete": "a del statement", "Global": "a global statement",
    "Nonlocal": "a nonlocal statement", "Yield": "a yield", "YieldFrom": "a yield from", "Await": "an await",
    "Match": "a match statement", "AsyncFunctionDef": "an async function",
}
SCOPE_READ_BRIEF = 'Extract only explicit scope constraints from the software task below. Return exactly one JSON object and no surrounding prose.\nThe object must contain these keys:\n{"limited": false, "files": [], "functions": [], "unchanged_outside": false, "imports_fixed": false, "banned": [], "quotes": []}\n- limited: true only if the task itself restricts editable files, functions, methods or queries.\n- files: repository paths the task explicitly permits changing, copied exactly.\n- functions: classes, functions, methods or queries the task explicitly names as the change boundary, copied exactly.\n- unchanged_outside: true only if the task explicitly says the rest of the file or other code must remain unchanged.\n- imports_fixed: true only if the task explicitly forbids adding or changing imports.\n- banned: prohibited constructs, using only: loops, comprehensions, lambdas, exception handling, context managers.\n- quotes: every sentence that explicitly states one of these restrictions, copied character for character.\nDo not infer a restriction from the suspected defect, repository conventions or surrounding code.'
_SCOPE_READS: dict = {}

class ScopeRead:
    def __init__(self) -> None:
        self.limited = False
        self.files: list = []
        self.functions: list = []
        self.unchanged_outside = False
        self.imports_fixed = False
        self.banned: set = set()
        self.single_unit = False
        self.quotes = 0
        self.verified = 0
        self.state = "not read"

    @property
    def trusted(self) -> bool:
        return self.limited and self.verified > 0 and bool(self.files or self.functions)

    @property
    def backed(self) -> bool:
        return self.limited and self.verified > 0

    def describe(self) -> str:
        return ("limited=%s files=%d functions=%d unchanged_outside=%s imports_fixed=%s banned=%d quotes=%d verified=%d"
                % (self.limited, len(self.files), len(self.functions), self.unchanged_outside,
                   self.imports_fixed, len(self.banned), self.quotes, self.verified))

def squash(text) -> str:
    return " ".join(str(text or "").replace("`", "").replace("**", "").split()).lower()

def scope_read_path(token, root: str, listing: list):
    path = str(token or "").strip().strip("`'\"").rstrip(",;:.")
    if path.startswith("./"):
        path = path[2:]
    path = (repo_relative(path, root) or "").rstrip("/")
    if not path or ".." in path.split("/") or TEST_PATH.search(path):
        return None
    full = os.path.join(root, path)
    if os.path.isfile(full):
        return ("file", path)
    if os.path.isdir(full) and "/" in path:
        return ("dir", path)
    tails = [p for p in listing if p == path or p.endswith("/" + path)]
    if len(tails) == 1:
        return ("file", tails[0])
    return None

def read_scope_reply(statement: str, content: str, root: str, listing: list) -> ScopeRead:
    read = ScopeRead()
    match = re.search(r"\{.*\}", content or "", re.S)
    if not match:
        read.state = "no object in the reply"
        return read
    try:
        data = json.loads(match.group(0))
    except ValueError:
        read.state = "the reply did not parse"
        return read
    if not isinstance(data, dict):
        read.state = "the reply was not an object"
        return read
    flat = squash(statement)
    quotes = [q for q in (data.get("quotes") or []) if isinstance(q, str) and squash(q)]
    read.quotes = len(quotes)
    good = [q for q in quotes if squash(q).rstrip(".") in flat and SCOPE_LIMIT_WORDS.search(q)]
    read.verified = len(good)
    said = " ".join(squash(q) for q in good)
    read.limited = bool(data.get("limited")) and bool(good)
    for item in data.get("files") or []:
        if not isinstance(item, str) or squash(item).strip("./") not in said:
            continue
        found = scope_read_path(item, root, listing)
        if found and found not in read.files:
            read.files.append(found)
    if read.files:
        for quote in good:
            for token in re.findall(r"`([^`\s]+)`|(?<![\w/.])((?:[\w-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6})(?![\w/])", quote):
                found = scope_read_path(token[0] or token[1], root, listing)
                if found and found not in read.files:
                    read.files.append(found)
    for item in data.get("functions") or []:
        if not isinstance(item, str):
            continue
        name = re.sub(r"\(.*$", "", item.strip().strip("`")).strip()
        name = re.sub(r"^(?:def|func|function|method)\s+", "", name)
        name = re.sub(r"/\d+$", "", name)
        if not re.fullmatch(r"[A-Za-z_]\w*(?:(?:\.|::|#)[A-Za-z_]\w*)*", name):
            continue
        segments = re.split(r"\.|::|#", name)
        if segments[-1].lower() not in said:
            continue
        entry = (".".join(segments), segments[-1])
        if entry not in read.functions:
            read.functions.append(entry)
    read.unchanged_outside = bool(data.get("unchanged_outside")) and any(SCOPE_OUTSIDE_WORDS.search(q) for q in good)
    read.single_unit = any(re.search(r"\bonly\b", q, re.I) and re.search(r"\b(?:method|function)\b", q, re.I) for q in good)
    read.imports_fixed = bool(data.get("imports_fixed")) and any(re.search(r"\bimport", q, re.I) for q in good)
    asked = {squash(b) for b in (data.get("banned") or []) if isinstance(b, str)}
    for label, pattern, _ in SCOPE_BANNED_KINDS:
        if label in asked and any(pattern.search(q) for q in good):
            read.banned.add(label)
    read.state = "read"
    return read

def read_scope(statement: str, tree: "Tree", allowance: "Allowance") -> ScopeRead:
    key = hashlib.sha256((statement or "").encode("utf-8", "replace")).hexdigest()
    if key in _SCOPE_READS:
        return _SCOPE_READS[key]
    beacon = Beacon("scoperead")
    read = ScopeRead()
    if not SCOPE_READ:
        beacon.skipped("not switched on for this run")
        return read
    if not (statement or "").strip():
        beacon.skipped("no statement")
        return read
    if allowance.clock_left() < SCOPE_READ_MIN_CLOCK_SEC:
        beacon.skipped("%.0fs of clock is too little to spend a call on the statement's limits" % allowance.clock_left())
        _SCOPE_READS[key] = read
        return read
    code, out = run_git_command(["ls-files"], tree.root, 30)
    listing = out.splitlines() if code == 0 else []
    messages = [{"role": "system", "content": SCOPE_READ_BRIEF},
                {"role": "user", "content": clip_output(statement, SCOPE_READ_STATEMENT_CHARS, "task")}]
    started = time.monotonic()
    reply, failure = None, ""
    for _ in range(SCOPE_READ_TRIES):
        try:
            reply = Seat(allowance, patient=False).ask(messages, None)
            break
        except Exception as error:
            failure = type(error).__name__
            if time.monotonic() - started > SCOPE_READ_MAX_SEC or allowance.clock_left() < SCOPE_READ_MIN_CLOCK_SEC:
                break
            time.sleep(2.0)
    if reply is None:
        read.state = "the call failed: %s" % failure
        beacon.skipped(read.state)
        return read
    read = read_scope_reply(statement, str(reply.get("content") or ""), tree.root, listing)
    _SCOPE_READS[key] = read
    beacon.fired("%s: %s" % (read.state, read.describe()))
    return read

def scope_covers(qualified: str, functions: list) -> bool:
    parts = qualified.split(".")
    for name, _ in functions:
        segments = name.split(".")
        if parts[-1] == segments[-1]:
            if len(segments) == 1 or len(parts) == 1:
                return True
            if parts[-2] == segments[-2] or not segments[-2][:1].isupper():
                return True
        if segments[-1] in parts[:-1]:
            return True
    return False

def scope_class_lines(text: str, functions: list) -> set:
    named = {name.split(".")[-1] for name, _ in functions}
    lines: set = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in named:
            lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return lines

def scope_edit_notes(path: str, before: str, after: str, statement: str, read: "ScopeRead | None") -> list:
    if read is None or not read.backed or not read.unchanged_outside or not path.endswith(".py"):
        return []
    try:
        old_tree, new_tree = ast.parse(before), ast.parse(after)
    except SyntaxError:
        return []
    was, now = changed_line_numbers(before, after)
    if not was and not now:
        return []

    def module_imports(tree) -> set:
        names: set = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                names.update("%s.%s" % (node.module or "", alias.name) for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        return names
    out: list = []
    owner, _, _ = python_functions(after)
    dropped = sorted(module_imports(old_tree) - module_imports(new_tree))
    local = sorted({owner[node.lineno].rsplit(".", 1)[-1] for node in ast.walk(new_tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno in now and owner.get(node.lineno)})
    if dropped or local:
        parts = []
        if dropped:
            parts.append("removes the file's import of %s" % ", ".join(dropped[:4]))
        if local:
            parts.append("adds an import inside %s" % ", ".join("%s()" % name for name in local[:4]))
        out.append("The task says the code outside the change stays as it is, and this change %s in %s. The file's "
                   "imports are part of what stays: keep every import the file had, use the names it already "
                   "imports, and when a new name is needed add it to the existing import line at the top of the "
                   "file rather than inside a function body." % (" and ".join(parts), path))
    if not read.functions and not read.single_unit:
        old_owner, old_heads, _ = python_functions(before)
        touched = {old_owner.get(line) for line in was} | {owner.get(line) for line in now}
        rewritten = sorted(name for name in touched if name and name in old_heads)
        if len(rewritten) >= 2:
            flat = squash(statement)
            unnamed = [name for name in rewritten
                       if not re.search(r"(?<![\w])%s(?![\w])" % re.escape(name.rsplit(".", 1)[-1].lower()), flat)]
            if unnamed:
                out.append("This change rewrites %d existing functions in %s: %s. The task says everything outside "
                           "the change stays as it is, and it does not name %s. When the task is about one of them, "
                           "put the other(s) back exactly as they were and keep the change inside the one it is about."
                           % (len(rewritten), path, ", ".join("%s()" % n for n in rewritten[:5]),
                              ", ".join("%s()" % n for n in unnamed[:4])))
    return out

def scope_reach(before: str, after: str, functions: list, statement: str) -> list:
    try:
        old_owner, old_heads, _ = python_functions(before)
        new_owner, _, _ = python_functions(after)
    except SyntaxError:
        return []
    was, now = changed_line_numbers(before, after)
    touched = {old_owner.get(line) for line in was} | {new_owner.get(line) for line in now}
    flat = squash(statement)
    out: list = []
    for name in sorted(n for n in touched if n and n in old_heads):
        short = name.rsplit(".", 1)[-1]
        if scope_covers(name, functions):
            continue
        if re.search(r"(?<![\w])%s(?![\w])" % re.escape(short.lower()), flat):
            continue
        out.append(name)
    return out

def function_spans(text: str) -> dict:
    spans: dict = {}

    def visit(node, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            name = (prefix + "." + child.name).lstrip(".") if named else prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top = min([d.lineno for d in child.decorator_list] + [child.lineno])
                spans[name] = (top, child.end_lineno or child.lineno)
            visit(child, name)
    visit(ast.parse(text), "")
    return spans

def put_back_functions(before: str, after: str, names: list) -> str:
    old, new = function_spans(before), function_spans(after)
    chosen = [n for n in names if n in old and n in new and not any(n.startswith(m + ".") for m in names if m != n)]
    lines = after.splitlines(keepends=True)
    old_lines = before.splitlines(keepends=True)
    for name in sorted(chosen, key=lambda n: -new[n][0]):
        start, end = new[name]
        old_start, old_end = old[name]
        piece = list(old_lines[old_start - 1:old_end])
        if piece and not piece[-1].endswith("\n") and end < len(lines):
            piece[-1] += "\n"
        lines[start - 1:end] = piece
    text = "".join(lines)
    compile(text, "<put back>", "exec")
    return text

def put_back_out_of_scope(warden: "Warden | None") -> None:
    if not SCOPE_PUT_BACK or warden is None:
        return
    beacon = Beacon("putback")
    read = getattr(warden, "read", None)
    try:
        paths = warden.changed_paths()
    except Exception as error:
        beacon.skipped("the changed paths could not be listed: %s" % type(error).__name__)
        return
    files: list = []
    functions: list = []
    plan: list = []
    kept = 0
    for path in paths:
        if ENVELOPE_JUNK.search(path):
            continue
        before = warden.original(path)
        if before is None:
            kept += 1
            continue
        try:
            if warden.scope_list and not scope_allows(path, warden.scope_list):
                plan.append((path, before))
                files.append(path)
                continue
            if read is None or not read.trusted or not read.functions or not path.endswith(".py"):
                kept += 1
                continue
            after = warden.tree.read(path)
            names = scope_reach(before, after, read.functions, warden.statement)
            if not names:
                kept += 1
                continue
            text = put_back_functions(before, after, names)
            plan.append((path, text))
            functions.extend(names)
            if text != before:
                kept += 1
        except Exception as error:
            kept += 1
            beacon.skipped("%s could not be put back: %s" % (path, type(error).__name__))
    if not plan:
        return
    if not kept:
        beacon.skipped("putting back %d file(s) and %d function(s) would leave no change at all; "
                       "the change goes out as written" % (len(files), len(functions)))
        return
    for path, text in plan:
        try:
            warden.tree.write(path, text)
        except Exception as error:
            beacon.skipped("%s could not be put back: %s" % (path, type(error).__name__))
    beacon.fired("put back %d file(s) outside the stated scope and %d function(s) the statement does not name"
                 % (len(files), len(functions)))

def contract_key(fault: str) -> str:
    return re.sub(r"\d+", "N", fault or "")[:100]

GO_BUILD_MAX_SEC = 150.0
GO_COMPILE_ERROR = re.compile(r"^\S+\.go:\d+:\d+: ", re.M)

def go_module_of(root: str, path: str):
    here = os.path.dirname(os.path.join(root, path))
    root = os.path.abspath(root)
    while True:
        if os.path.isfile(os.path.join(here, "go.mod")):
            return here
        if os.path.abspath(here) == root or os.path.dirname(here) == here:
            return None
        here = os.path.dirname(here)


# --- governance/warden.py ---

def go_build_output(root: str, paths: list, budget: float):
    go = shutil.which("go") or ("/usr/local/go/bin/go" if os.path.exists("/usr/local/go/bin/go") else "")
    if not go:
        return None, "no go toolchain"
    groups: dict = {}
    for path in paths:
        module = go_module_of(root, path)
        if module is None:
            continue
        rel = os.path.relpath(os.path.dirname(os.path.join(root, path)), module)
        groups.setdefault(module, set()).add("." if rel == "." else "./" + rel)
    if not groups:
        return None, "no go.mod above the changed files"
    env = dict(os.environ)
    env["GOFLAGS"] = (env.get("GOFLAGS", "") + " -p=2").strip()
    env.update({"GOMAXPROCS": "2", "GOPROXY": "off", "GOTOOLCHAIN": "local"})
    started = time.time()
    for module, packages in sorted(groups.items()):
        for package in sorted(packages):
            left = budget - (time.time() - started)
            if left < 5.0:
                return None, "ran out of time"
            try:
                done = subprocess.run([go, "build", "-o", os.devnull, package], cwd=module, capture_output=True,
                                      text=True, errors="replace", timeout=left, env=env)
            except subprocess.TimeoutExpired:
                return None, "go build ran past %.0fs" % left
            output = (done.stdout or "") + (done.stderr or "")
            if done.returncode != 0:
                if GO_COMPILE_ERROR.search(output):
                    return False, output
                return None, "go build failed without a compile error: %s" % compact_text(output)[:160]
    return True, ""

class Warden:
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 statement: str = "", read: "ScopeRead | None" = None) -> None:
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.declared = declared_file(statement, tree.root)
        self.statement = statement
        self.ledger = Beacon("ledger")
        self.read_back_calls: int | None = None
        self.read_backs = 0
        self.records: list = []
        self.beacon = Beacon("warden")
        self.job: Shell | None = None
        self.started = time.time()
        self.before: tuple[set, int] | None = None
        self.refusals = 0
        self.hinted = False
        self.noted: set = set()
        self.hints = Beacon("hints")
        self.stood_down = False
        self.where: str | None = None
        self.tier = 0
        self.scope: list[str] = []
        self.armed_after: float | None = None
        self.bounded_count = True
        self.shims: list = []
        self.shim_dir = ""
        self.stood_in = 0
        self.stated = [line for kind, line in stated_checks(statement)] if STATED_CHECKS else []
        self.mode = "stated" if self.stated else "pytest"
        self.site = "worktree"
        self.retried_live = False
        self.before_rc: int | None = None
        self.before_tail = ""
        self.before_secs = 0.0
        self.read = read
        self.rereads = 0
        self.scope_noted: set = set()
        self.build = Beacon("gobuild")
        self.scope_list = scope_targets(statement, tree.root) if SCOPE_GATE else []
        if SCOPE_GATE and read is not None and read.trusted:
            for item in read.files:
                if item not in self.scope_list:
                    self.scope_list.append(item)
        if self.scope_list:
            log_message("[SCOPE] the statement confines the change to: %s"
                % ", ".join(p for _, p in self.scope_list))

    def reread_scope(self) -> bool:
        read = self.read
        if read is None or not str(read.state).startswith("the call failed") or self.rereads >= 1:
            return False
        if self.allowance.clock_left() < SCOPE_READ_MIN_CLOCK_SEC:
            return False
        self.rereads += 1
        try:
            fresh = read_scope(self.statement, self.tree, self.allowance)
        except Exception as error:
            log_message("[SCOPEREAD] skipped: %s" % type(error).__name__)
            return False
        self.read = fresh
        if SCOPE_GATE and fresh.trusted:
            for item in fresh.files:
                if item not in self.scope_list:
                    self.scope_list.append(item)
        return fresh.state == "read"

    def stated_command(self, root: str | None = None) -> str:
        root = root or self.tree.root
        lints = [line for kind, line in stated_checks(self.statement) if kind == "lint"]
        tests = [line for kind, line in stated_checks(self.statement) if kind == "test"]
        chain = " && ".join("( %s )" % line for line in lints + tests)
        return ('cd %s && export PYTHONDONTWRITEBYTECODE=1 GOFLAGS="${GOFLAGS:-} -p=2" GOMAXPROCS=2 && %s'
                % (shlex.quote(root), chain))

    def arm(self) -> None:
        if self.mode != "stated":
            return self.arm_pytest()
        if not SUBMISSION_WARDEN:
            self.beacon.skipped("not switched on for this run")
            return
        self.beacon.reached(0, self.allowance.spent, self.allowance.clock_left())
        room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
        if room < STATED_HOLD_MIN_ROOM_SEC:
            self.beacon.skipped(
                "not starting the task's own checks: %.0fs of room is too little to "
                "wait for them or to act on what they say, and a check nothing reads "
                "is just something else competing with this run" % room)
            return
        try:
            self.where = self.pristine()
            self.site = "worktree" if self.where else "live"
            log_message("[WARDEN] baseline: %d stated check(s) at the %s tree: %s"
                % (len(self.stated), self.site, " && ".join(self.stated)[:300]))
            self.job = self.pool.start(self.stated_command(self.where or self.tree.root))
        except Exception as error:
            self.beacon.skipped("could not start the stated baseline: %s" % error)

    def collect(self) -> None:
        if self.mode != "stated":
            return self.collect_pytest()
        if self.job is None or self.before is not None:
            return
        if not self.job.finished():
            if time.time() - self.job.started > STATED_BASELINE_SEC:
                self.job.stop()
                self.pool.jobs.pop(self.job.name, None)
                self.job = None
                self.beacon.skipped("the stated checks did not finish in the "
                                    "time this rung allows")
            return
        elapsed = time.time() - self.job.started
        rc = self.job.process.returncode
        done, out = self.job.wait(0.5)
        self.pool.jobs.pop(self.job.name, None)
        self.job = None
        names, count = failed_names(out), passed_count(out)
        if (rc != 0 and self.site == "worktree" and not self.retried_live
                and elapsed < STATED_FAST_FAIL_SEC and not names and count == 0):
            self.retried_live = True
            self.site = "live"
            self.beacon.fired("the stated checks ended at once in the separate "
                              "checkout (rc=%s); reading the live tree instead" % rc)
            try:
                self.job = self.pool.start(self.stated_command(self.tree.root))
            except Exception as error:
                self.beacon.skipped("could not restart the stated baseline: %s" % error)
            return
        self.before = (names, count)
        self.before_rc = rc
        self.before_tail = compact_text(clip_output(out or "", STATED_TAIL_CHARS * 2, "output"))[-STATED_TAIL_CHARS:]
        self.before_secs = elapsed
        self.armed_after = time.time() - self.started
        log_message("[WARDEN] the stated checks at the start: rc=%s, %d failing, %d passing "
            "(%s tree, %.0fs)" % (rc, len(names), count, self.site, elapsed))

    def suite_faults(self) -> list[str]:
        if self.mode != "stated":
            return self.suite_faults_pytest()
        if self.before is None:
            return []
        room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
        if room < 30.0:
            return []
        job = self.pool.start(self.stated_command())
        done, out = job.wait(min(STATED_RECHECK_SEC, room))
        self.pool.jobs.pop(job.name, None)
        if not done:
            job.stop()
            self.beacon.skipped("the stated checks did not finish in the time left")
            return []
        rc = job.process.returncode
        names, count = failed_names(out), passed_count(out)
        fresh = sorted(names - self.before[0])
        stale = sorted(names & self.before[0])
        log_message("[WARDEN] the stated checks now: rc=%s, %d failing (%d new, %d still), %d passing"
            % (rc, len(names), len(fresh), len(stale), count))
        ran_at_start = bool(self.before[0]) or self.before[1] > 0
        if rc != 0 and not fresh and not (ran_at_start or names or count) and self.before_rc != 0:
            self.beacon.skipped("the task's own check exits %s without running a test, as it "
                                "did at the start; nothing here says the answer broke it" % rc)
            return []
        if rc != 0 and not fresh:
            tail = compact_text(clip_output(out or "", STATED_TAIL_CHARS * 2, "output"))[-STATED_TAIL_CHARS:]
            named = ("on %s%s" % (", ".join(stale[:6]),
                                  " and %d more" % (len(stale) - 6) if len(stale) > 6 else "")
                     if stale else
                     "and it named no failing test, so read the output: a command in the chain "
                     "exited before the tests ran, a linter or a compile step most often")
            return ["The task's own check command does not pass (exit %s) %s. The task says to run "
                    "it before finishing and expects it to pass, so this answer "
                    "is not finished. Read what the output reports and fix the behaviour it names; "
                    "do not touch the check. Output tail: %s" % (rc, named, tail)]
        if (self.before_rc == 0 and rc != 0) or fresh:
            tail = compact_text(clip_output(out or "", STATED_TAIL_CHARS * 2, "output"))[-STATED_TAIL_CHARS:]
            named = (", ".join(fresh[:6]) + ". " if fresh else "")
            return ["The task's own check command was passing when this run started "
                    "and does not pass now (exit %s). %sThe task requires it to keep "
                    "passing, so this answer does not satisfy it as it stands. Fix the "
                    "behaviour rather than the check. Output tail: %s" % (rc, named, tail)]
        return []

    def opening_reading(self) -> str:
        if self.mode != "stated" or self.before is None:
            return ""
        names, count = self.before
        command = " && ".join(self.stated)[:300]
        if names:
            listed = sorted(names)
            shown = ", ".join(listed[:12]) + (" and %d more" % (len(listed) - 12) if len(listed) > 12 else "")
            return ("The task's own check was run on the unchanged tree before you started "
                    "(%s): exit %s, %d failing, %d passing, %.0fs. Failing now: %s. Those "
                    "failures describe behaviour the change has to produce, and the same command "
                    "has to pass before you finish. Output tail: %s"
                    % (command, self.before_rc, len(names), count, self.before_secs, shown,
                       self.before_tail))
        if self.before_rc == 0 and count > 0:
            return ("The task's own check was run on the unchanged tree before you started "
                    "(%s): it passes, %d test(s), %.0fs. It has to keep passing after the change."
                    % (command, count, self.before_secs))
        return ""

    def suite_command(self, root: str | None = None) -> str:
        root = root or self.tree.root
        path = os.pathsep.join(package_roots(root) + ([self.shim_dir] if self.shim_dir else []))
        where = " ".join(shlex.quote(rel) for rel in self.scope)
        pyc = tempfile.mkdtemp(prefix="pyc")
        if path_is_inside(pyc, self.tree.root):
            shutil.rmtree(pyc, ignore_errors=True)
            cache = "PYTHONDONTWRITEBYTECODE=1"
        else:
            cache = "PYTHONPYCACHEPREFIX=%s" % pyc
        return (
            "cd %s && PYTHONPATH=%s PYTHONHASHSEED=0 %s %s -m pytest -q "
            "--no-header --tb=line -rfE -p no:cacheprovider -o addopts= "
            "--continue-on-collection-errors -W ignore::DeprecationWarning%s%s"
            % (root, path, cache,
               sys.executable or "python3", SUITE_TIERS[self.tier],
               (" " + where) if where else "")
        )

    def pristine(self) -> str | None:
        where = os.path.join(tempfile.mkdtemp(prefix="start"), "tree")
        if path_is_inside(where, self.tree.root):
            shutil.rmtree(os.path.dirname(where), ignore_errors=True)
            self.beacon.skipped("the only place for a separate checkout is "
                                "inside the tree being handed in")
            return None
        code, out = run_git_command(["worktree", "add", "--detach", where, self.tree.base or "HEAD"],
                        self.tree.root, 60)
        if code != 0:
            self.beacon.skipped("no separate checkout to read: %s" % out.strip()[:120])
            return None
        return where

    def arm_pytest(self) -> None:
        if not SUBMISSION_WARDEN:
            self.beacon.skipped("not switched on for this run")
            return
        self.beacon.reached(0, self.allowance.spent, self.allowance.clock_left())
        try:
            self.where = self.pristine()
            self.scope = suite_scope(self.tree.root, self.declared) if SUITE_SCOPE else []
            log_message("[WARDEN] baseline scope: %s"
                % (", ".join(self.scope) if self.scope else "the whole repository"))
            if not self.scope:
                if not SUITE_SCOPE:
                    log_message("[WARDEN] wide baseline: not switched on for this run")
                elif self.declared is None:
                    log_message("[WARDEN] the statement gave: %s"
                        % declared_trace(self.statement, self.tree.root))
                else:
                    log_message("[WARDEN] wide baseline: nothing matched")
            self.job = self.pool.start(self.suite_command(self.where))
        except Exception as error:
            self.beacon.skipped("could not start the baseline reading: %s" % error)

    def escalate(self) -> bool:
        if self.where is None:
            return False
        top = len(SUITE_TIERS) - 1 if SUITE_IMPORTLIB else len(SUITE_TIERS) - 2
        if self.tier >= top:
            if self.tier < len(SUITE_TIERS) - 1:
                self.beacon.skipped("this rung is not switched on for this run")
            return False
        if self.allowance.clock_left() < RUNG_MIN_WALL_SEC:
            self.beacon.skipped("too little of the run left for a second reading")
            return False
        self.tier += 1
        self.beacon.fired("nothing in the project's suite passed; asking again, "
                          "rung %d of %d"
                          % (self.tier + 1, len(SUITE_TIERS)))
        try:
            self.job = self.pool.start(self.suite_command(self.where))
        except Exception as error:
            self.beacon.skipped("could not start the second reading: %s" % error)
            return False
        return True

    def stand_in(self, out: str) -> bool:
        if not SUITE_SHIM or self.where is None:
            if not SUITE_SHIM:
                self.beacon.skipped("standing in is not switched on for this run")
            return False
        wanted = [n for n in missing_modules(out) if n not in self.shims]
        records = [n for n in missing_dists(out) if n not in self.records]
        room_left = max(0, SUITE_SHIM_LIMIT - len(self.shims) - len(self.records))
        if (wanted or records) and not room_left:
            self.beacon.skipped("%d stand-in(s) over %d attempt(s) and the "
                                "reading still names more"
                                % (len(self.shims + self.records), self.stood_in))
            return False
        records_first = len(self.records) <= len(self.shims)
        first, second = ((records, wanted) if records_first
                         else (wanted, records))
        share: list = []
        for step in range(max(len(first), len(second))):
            if step < len(first):
                share.append((records_first, first[step]))
            if step < len(second):
                share.append((not records_first, second[step]))
        share = share[:room_left]
        records = [name for is_record, name in share if is_record]
        wanted = [name for is_record, name in share if not is_record]
        if not wanted and not records:
            return False
        if self.allowance.clock_left() < STANDIN_MIN_WALL_SEC:
            self.beacon.skipped("too little of the run left to read the suite again")
            return False
        if not self.shim_dir:
            try:
                room = tempfile.mkdtemp(prefix="standin")
            except OSError as error:
                self.beacon.skipped("nowhere to write a stand-in: %s" % error)
                self.shim_dir = ""
                return False
            if path_is_inside(room, self.tree.root):
                shutil.rmtree(room, ignore_errors=True)
                self.beacon.skipped("the only place to write a stand-in is inside "
                                    "the tree being handed in")
                self.shim_dir = ""
                return False
            self.shim_dir = room
        made = write_shims(wanted, self.shim_dir)
        kept = write_dist_records(records, self.shim_dir)
        if not made and not kept:
            self.beacon.skipped("could not write a stand-in for %s"
                                % compact_text(", ".join(wanted + records))[:80])
            return False
        told = []
        if made:
            told.append("does not carry " + compact_text(", ".join(made))[:90])
        if kept:
            told.append("has no installed record of " + compact_text(", ".join(kept))[:90])
        self.beacon.fired("the image %s; standing in for it and reading again"
                          % " and ".join(told))
        self.tier = 0
        try:
            self.job = self.pool.start(self.suite_command(self.where))
        except Exception as error:
            self.beacon.skipped("could not start the reading again: %s" % error)
            return False
        self.stood_in += 1
        self.shims.extend(made)
        self.records.extend(kept)
        return True

    def hold(self) -> None:
        if self.mode != "stated" or self.job is None or self.before is not None:
            return
        room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
        if room < STATED_HOLD_MIN_ROOM_SEC:
            self.beacon.skipped("no hold for the stated checks: %.0fs of room" % room)
            return
        started = time.time()
        deadline = started + min(STATED_HOLD_SEC, room - STATED_HOLD_MIN_ROOM_SEC / 2.0)
        while self.job is not None and self.before is None:
            left = deadline - time.time()
            if left < 1.0:
                break
            self.job.wait(min(20.0, left))
            self.collect()
        log_message("[WARDEN] held %.0fs before starting; the task's own checks are %s"
            % (time.time() - started,
               "read" if self.before is not None else "still running"))

    def settle(self) -> None:
        for _ in range((1 + SUITE_SHIM_LIMIT) * len(SUITE_TIERS)):
            self.collect()
            if self.before is not None or self.job is None:
                return
            room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
            window = min(SUITE_SETTLE_SEC, room)
            if window < 5.0:
                break
            self.job.wait(window)
            if not self.job.finished() and self.mode != "stated":
                break
        self.collect()

    def collect_pytest(self) -> None:
        if self.job is None or self.before is not None:
            return
        if not self.job.finished():
            if time.time() - self.job.started > SUITE_BASELINE_SEC:
                self.job.stop()
                self.pool.jobs.pop(self.job.name, None)
                self.job = None
                self.beacon.skipped("the project's tests did not finish in the "
                                    "time this rung allows")
            return
        done, out = self.job.wait(0.5)
        self.pool.jobs.pop(self.job.name, None)
        self.job = None
        reading = self.read_suite(out)
        if not reading[1] and self.escalate():
            return
        if not reading[1] and self.stand_in(out):
            return
        if not reading[1]:
            self.beacon.skipped("the project's tests produced no usable "
                                "baseline at tier %d: %s -- %s"
                                % (self.tier + 1, self.tally(out), self.reason(out)))
            return
        propped = len(self.shims) + len(self.records)
        self.bounded_count = True
        if propped:
            green = reading[1] / float(reading[1] + len(reading[0]) or 1)
            if green < SUITE_SHIM_MIN_GREEN:
                self.bounded_count = False
                self.beacon.fired(
                    "read over %d stand-in(s) and only %.0f%% of it passes; the "
                    "count is not evidence here, the names still are"
                    % (propped, 100 * green))
        self.before = reading
        self.armed_after = time.time() - self.started
        log_message("[WARDEN] the project's tests at the start: %d failing, %d passing "
            "(tier %d, scope %s, %.0fs)"
            % (len(self.before[0]), self.before[1], self.tier + 1,
               ",".join(self.scope) or "repository", self.armed_after))

    @staticmethod
    def tally(out: str) -> str:
        found = SUITE_TALLY.findall(out or "")
        return found[-1].strip() if found else "no tally"

    @staticmethod
    def reason(out: str) -> str:
        faults = SUITE_FAULT.findall(out or "")
        if faults:
            kinds = len({name for name, _ in faults})
            said = ("%s%s" % faults[0]).strip()[:140]
            return said if kinds == 1 else "%s (+%d other kinds)" % (said, kinds - 1)
        found = SUITE_REASON.findall(out or "")
        return found[0].strip()[:160] if found else "no reason given"

    @staticmethod
    def read_suite(out: str) -> tuple[set, int]:
        counts = PASSED_COUNT.findall(out or "")
        return set(FAILED_TEST.findall(out or "")), int(counts[-1]) if counts else 0

    def suite_faults_pytest(self) -> list[str]:
        if self.before is None:
            return []
        room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
        if room < 30.0:
            return []
        job = self.pool.start(self.suite_command())
        done, out = job.wait(min(SUITE_RECHECK_SEC, room))
        self.pool.jobs.pop(job.name, None)
        if not done:
            job.stop()
            self.beacon.skipped("the project's tests did not finish in the time left")
            return []
        broke, passing = self.read_suite(out)
        fresh = self.confirm(sorted(broke - self.before[0]))
        if fresh:
            log_message("[WARDEN] the refusal %s the question"
                % ("carries" if WARDEN_ASK else "does not carry"))
            return ["The project's own tests were passing when this run started "
                    "and are failing now: %s. The task requires the project's tests to "
                    "keep passing, so this answer does not satisfy it as it "
                    "stands. Fix the behaviour rather than the test.%s"
                    % (", ".join(fresh[:6]), WARDEN_QUESTION if WARDEN_ASK else "")]
        if not passing:
            if not broke and SUITE_FAULT.search(out or ""):
                return ["The project's suite produced a reading at the start "
                        "of this run (%d passing) and produces none now: %s. "
                        "A suite that no longer even starts proves nothing "
                        "about behaviour; make the project import cleanly "
                        "again." % (self.before[1], self.reason(out))]
            self.beacon.skipped("the re-reading produced no usable count: %s -- %s"
                                % (self.tally(out), self.reason(out)))
            return []
        if self.bounded_count and passing < self.before[1]:
            return ["The project's suite reported %d passing tests at the start "
                    "of this run and %d now. A suite that got smaller is not "
                    "evidence that behaviour was kept: a skipped or deselected "
                    "test proves nothing." % (self.before[1], passing)]
        return []

    def confirm(self, names: list[str]) -> list[str]:
        if not names:
            return []
        room = self.allowance.clock_left() - WARDEN_RELEASE_SEC
        if room < 20.0:
            return names
        asked = names[:CONFIRM_MAX]
        job = self.pool.start("%s %s" % (self.suite_command(),
                                         " ".join(shlex.quote(n) for n in asked)))
        done, out = job.wait(min(SUITE_RECHECK_SEC, room))
        self.pool.jobs.pop(job.name, None)
        if not done:
            job.stop()
            return asked
        again, count = self.read_suite(out)
        if not again and not count:
            return asked
        settled = [n for n in asked if n in again]
        if len(settled) != len(asked):
            self.beacon.fired("%d of %d only failed once and were let go"
                              % (len(asked) - len(settled), len(asked)))
        return settled

    def changed_paths(self) -> list[str]:
        code, out = run_git_command(["diff", "--name-only", self.tree.base or "HEAD"],
                        self.tree.root, 30)
        paths = [p for p in out.splitlines() if p.strip()] if code == 0 else []
        return paths + sorted((self.tree._untracked() or set())
                              - self.tree.untracked_at_start)

    def original(self, path: str) -> str | None:
        code, out = run_git_command(["show", "%s:%s" % (self.tree.base, path)], self.tree.root, 30)
        return out if code == 0 else None

    def reach_faults(self, path: str, before: str, after: str) -> list[str]:
        read = self.read
        if read is None or not read.trusted or not read.functions or not path.endswith(".py"):
            return []
        names = scope_reach(before, after, read.functions, self.statement)
        if not names:
            return []
        allowed = ", ".join("%s()" % name for name, _ in read.functions[:4])
        return ["The task confines the change to %s, and this run also rewrote %s in %s, which the task does not "
                "name. A change outside what the task names can void the whole answer however right the named "
                "code is: put %s back exactly as it was and keep the change inside %s."
                % (allowed, ", ".join("%s()" % n for n in names[:4]), path,
                   "it" if len(names) == 1 else "them", allowed)]

    def go_build_faults(self) -> list[str]:
        if not GO_BUILD_CHECK:
            return []
        paths = [p for p in self.changed_paths() if p.endswith(".go") and not TEST_PATH.search(p)
                 and not ENVELOPE_JUNK.search(p)]
        if not paths:
            return []
        room = min(GO_BUILD_MAX_SEC, self.allowance.clock_left() - WARDEN_RELEASE_SEC)
        if room < 30.0:
            self.build.skipped("%.0fs is too little to build the changed Go packages" % room)
            return []
        built, output = go_build_output(self.tree.root, paths, room)
        if built is None:
            self.build.skipped(output)
            return []
        if built:
            self.build.fired("the changed Go packages build")
            return []
        self.build.fired("the changed Go packages do not build")
        return ["The Go code this run changed does not build:\n%s\nFix the build before handing in: code that "
                "does not compile fails before any behaviour is looked at." % clip_output(output, 1500, "build output")]

    def change_faults(self) -> list[str]:
        faults: list[str] = []
        for path in self.changed_paths():
            if ENVELOPE_JUNK.search(path):
                continue
            if TEST_PATH.search(path):
                faults.append(
                    "This run edited %s. The task is to change the code under "
                    "repair, not the tests that check it; editing a test file "
                    "or a conftest reads as tampering. Put it back exactly as "
                    "it was and make the source satisfy the test instead." % path)
                continue
            if self.scope_list and not scope_allows(path, self.scope_list):
                faults.append(
                    "The task confines the change to %s, and this run also changed "
                    "%s. Everything outside the stated scope must be byte-identical "
                    "when you finish: restore %s exactly as it was and express the "
                    "change inside the stated scope." % (
                        ", ".join(p for _, p in self.scope_list), path, path))
                continue
            faults.extend(self.file_faults(path))
        if not faults:
            faults.extend(self.go_build_faults())
        return faults

    def file_faults(self, path: str) -> list[str]:
        before = self.original(path)
        if before is None:
            if importable(path) and contract_rules(self.statement).get("method"):
                return ["The task bounds the change to one method of an existing file, and this "
                        "run added %s. Remove the new file and put the change inside the bounded "
                        "method." % path]
            return []
        if not importable(path):
            return []
        carried = visible_definitions(before)
        try:
            after = self.tree.read(path)
        except ToolFault:
            if not carried:
                return []
            return ["This run deleted %s, and callers of %s lose it with the "
                    "file. Keep the file and the names in it." % (path, carried[0])]
        out: list[str] = []
        gone = sorted((collections.Counter(carried)
                       - collections.Counter(visible_definitions(after))).elements())
        if carried and gone:
            out.append(
                "These definitions were in %s when the run started and are not "
                "there now: %s. A refactor may not drop a name callers can "
                "use, and renaming or moving a method out of its class reads "
                "as dropping it. Keep the original name and delegate from it."
                % (path, ", ".join(gone[:6])))
        try:
            out.extend(contract_faults(path, before, after, self.statement, self.read))
            out.extend(self.reach_faults(path, before, after))
        except Exception as error:
            self.beacon.skipped("the contract of %s could not be read: %s"
                                % (path, type(error).__name__))
        added = len(NOQA_DIRECTIVE.findall(after)) - len(NOQA_DIRECTIVE.findall(before))
        if added > 0:
            out.append(
                "This run added %d suppression comment(s) to %s. Silencing "
                "the check is the one answer the task rules out; the count "
                "may not go up." % (added, path))
        return out

    def ledger_faults(self) -> list[str]:
        if not LEDGER_READBACK:
            self.ledger.skipped("not switched on for this run")
            return []
        items = stated_requirements(self.statement)
        if len(items) < LEDGER_MIN:
            self.ledger.skipped("%d item(s), below the floor" % len(items))
            return []
        if self.read_back_calls is not None:
            if self.allowance.calls > self.read_back_calls:
                return []
        if self.allowance.clock_left() < CONFORM_MIN_WALL_SEC:
            self.ledger.skipped("too little of the run left to act on it")
            return []
        if self.read_backs >= LEDGER_MAX_ASKS:
            self.ledger.skipped("asked %d time(s) already" % self.read_backs)
            return []
        held = [read_back(items)]
        if self.read_back_calls is not None:
            self.read_backs += 1
            self.ledger.fired("again; nothing was answered in between")
            return held
        self.read_backs += 1
        self.read_back_calls = self.allowance.calls
        self.ledger.fired("%d item(s), %d of the kind that asks for an edit"
                          % (len(items),
                             sum(1 for i in items if wants_an_edit(i))))
        return held

    def text_of(self, path: str) -> str:
        try:
            return self.tree.read(path)[:WARDEN_READ_CAP_CHARS]
        except Exception:
            return ""

    def edit_note(self, path: str) -> str:
        if not SHAPE_HINTS or ENVELOPE_JUNK.search(path or "") or TEST_PATH.search(path or ""):
            return ""
        if self.allowance.clock_left() < HINT_EDIT_MIN_SEC:
            return ""
        code, diff = run_git_command(["diff", "-U%d" % HINT_CONTEXT_LINES, self.tree.base or "HEAD", "--", path],
                         self.tree.root, max(2.0, min(20.0, self.allowance.clock_left() - 10.0)))
        if code != 0 or not diff:
            return ""
        fresh: list = []
        for kind, line in shape_findings(diff, self.text_of(path)):
            if kind not in self.noted and kind not in [k for k, _ in fresh]:
                fresh.append((kind, "%s:%d" % (path, line)))
        if not fresh:
            return ""
        self.noted.update(kind for kind, _ in fresh)
        self.hints.fired("on edit: " + ", ".join("%s at %s" % item for item in fresh))
        return ("\n\nNote on the change just made (shown once): "
                + " ".join(SHAPE_NOTES[kind] % where for kind, where in fresh))

    def scope_notes(self) -> list[str]:
        out: list[str] = []
        read = self.read
        if read is None or not read.backed or not read.unchanged_outside:
            return out
        for path in self.changed_paths():
            if not path.endswith(".py") or ENVELOPE_JUNK.search(path) or TEST_PATH.search(path):
                continue
            before = self.original(path)
            if before is None:
                continue
            try:
                after = self.tree.read(path)
            except ToolFault:
                continue
            try:
                notes = scope_edit_notes(path, before, after, self.statement, read)
            except Exception as error:
                self.hints.skipped("the change to %s could not be read: %s" % (path, type(error).__name__))
                continue
            for note in notes:
                key = contract_key(note)
                if key not in self.scope_noted:
                    self.scope_noted.add(key)
                    out.append(note)
        return out

    def shape_hints(self) -> list[str]:
        if not SHAPE_HINTS or self.hinted:
            return []
        short = getattr(self.allowance, "wall", DEFAULT_WALL_SEC) <= SHORT_WALL_SEC
        if self.allowance.clock_left() < (HINT_MIN_SEC_SHORT if short else HINT_MIN_SEC):
            self.hints.skipped("too little of the run left to act on a hint")
            return []
        found: list = []
        for path in self.changed_paths():
            if ENVELOPE_JUNK.search(path) or TEST_PATH.search(path):
                continue
            code, diff = run_git_command(["diff", "-U%d" % HINT_CONTEXT_LINES, self.tree.base or "HEAD", "--", path],
                             self.tree.root, max(2.0, min(30.0, self.allowance.clock_left() - 5.0)))
            if code != 0 or not diff:
                continue
            for kind, line in shape_findings(diff, self.text_of(path)):
                if kind not in [k for k, _ in found]:
                    found.append((kind, "%s:%d" % (path, line)))
        extra = self.scope_notes()
        if not found and not extra:
            self.hints.skipped("no recurring shape in the changed code")
            return []
        self.hinted = True
        self.hints.fired(", ".join(["%s at %s%s" % (kind, where, " (noted at the edit, still there)"
                                                    if kind in self.noted else "") for kind, where in found]
                                   + (["%d scope note(s)" % len(extra)] if extra else [])))
        return [HINT_HEAD + "\n\n" + "\n\n".join(["- " + (HINT_STILL if kind in self.noted else "")
                                                   + SHAPE_NOTES[kind] % where for kind, where in found]
                                                  + ["- " + note for note in extra])
                + "\n\n" + HINT_TAIL]

    def verdict(self) -> list[str]:
        if not SUBMISSION_WARDEN:
            return []
        self.settle()
        if self.before is None and self.job is not None:
            self.beacon.skipped("the project's tests were still running when "
                                "the answer was ready")
        if self.refusals >= WARDEN_REFUSALS_MAX:
            self.stood_down = True
            self.beacon.skipped("already sent the run back %d times" % self.refusals)
            return self.shape_hints()
        if self.allowance.clock_left() < WARDEN_RELEASE_SEC:
            self.stood_down = True
            self.beacon.skipped("too little of the run left to act on a refusal")
            return self.shape_hints()
        self.reread_scope()
        faults = self.change_faults() or self.suite_faults()
        said, mine = (faults[0][:120] if faults else ""), True
        if not faults:
            faults = self.shape_hints()
            if faults:
                said, mine = "a recurring shape in the changed code", False
        if not faults:
            faults = self.ledger_faults()
            if faults:
                said, mine = ("the list, %d item(s)" % len(
                    stated_requirements(self.statement)), False)
        if faults and mine:
            self.refusals += 1
            self.beacon.fired("refused hand-in #%d: %s" % (self.refusals, said))
        elif faults:
            self.beacon.fired("held hand-in: %s" % said)
        return faults


# --- workflow/postprocessing.py ---
def answer_shape(patch: str) -> tuple:
    files, added, removed = set(), [], []
    for line in (patch or "").splitlines():
        if line.startswith("diff --git "):
            files.add(line.split(" b/", 1)[-1].strip())
        elif line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        elif line.startswith("+"):
            if line[1:].strip():
                added.append(line[1:].rstrip())
        elif line.startswith("-"):
            if line[1:].strip():
                removed.append(line[1:].rstrip())
    return frozenset(files), tuple(added), tuple(removed)

def envelope_trim(patch: str) -> str:
    sections = split_by_file(patch)
    if len(sections) < 2:
        return patch
    kept, dropped = [], []
    for section in sections:
        head = section.split("\n", 1)[0]
        path = head[len("diff --git "):].split(" b/", 1)[-1].strip().strip('"')
        if ENVELOPE_JUNK.search(path):
            dropped.append(path)
        else:
            kept.append(section)
    if not dropped or not kept:
        return patch
    log_message("[ENVELOPE] dropped %d of %d section(s): %s"
        % (len(dropped), len(sections), ", ".join(dropped[:5])))
    return "".join(kept)

def same_answer(first: str, second: str) -> bool:
    return answer_shape(first) == answer_shape(second)

def second_pass_room_needed(first_took: float) -> float:
    return max(SECOND_PASS_MIN_CLOCK_SEC,
               first_took * SECOND_PASS_ROOM_FACTOR + SECOND_PASS_PICK_RESERVE_SEC)

def second_pass_affordable(allowance: "Allowance", first: str,
                           first_took: float = 0.0) -> str:
    if not SECOND_PASS:
        return "not switched on for this run"
    if not (first or "").strip():
        return "the first derivation produced nothing to compare against"
    needed = second_pass_room_needed(first_took)
    if allowance.clock_left() < needed:
        return ("%.0fs left does not cover another derivation: the first took %.0fs, "
                "so %.0fs is wanted" % (allowance.clock_left(), first_took, needed))
    if allowance.money_left() < SECOND_PASS_MIN_MONEY_USD:
        return "$%.3f left is too little for another derivation" % allowance.money_left()
    return ""

DERIVE_STATE: dict = {}

def derive(statement: str, tree: "Tree", root: str, allowance: "Allowance",
           findings: "FindingMap | None", label: str) -> str:
    DERIVE_STATE.pop("warden", None)
    pool = ShellPool(root)
    earlier_edits, allowance.edits = allowance.edits, 0
    try:
        run_agent_workflow(statement, tree, pool, allowance, findings)
    except Spent as stop:
        log_message("[RUN] %s derivation out of allowance: %s" % (label, stop))
    except BaseException as error:
        import traceback
        traceback.print_exc()
        log_message("[RUN] %s derivation crashed: %s: %s" % (label, type(error).__name__, error))
    allowance.edits += earlier_edits
    pool.close()
    try:
        put_back_out_of_scope(DERIVE_STATE.get("warden"))
    except BaseException as error:
        log_message("[PUTBACK] skipped: %s" % type(error).__name__)
    patch = ""
    try:
        patch = tree.diff(max(5.0, min(60.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:
        import traceback
        traceback.print_exc()
    try:
        tree.restore(max(5.0, min(60.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:
        pass
    return patch

DIFF_FILE_HEAD = re.compile(r"^diff --git a/(\S+) b/(\S+)")
DIFF_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@ ?(.*)$")
OUTLINE_NAMES_MAX = 8

def diff_outline(patch: str, root: str) -> dict:
    outline: dict = {}
    for block in re.split(r"(?=^diff --git )", patch or "", flags=re.M):
        head = DIFF_FILE_HEAD.match(block)
        if not head:
            continue
        path = head.group(2)
        touched: set = set()
        contexts: list = []
        old = 0
        for line in block.splitlines():
            hunk = DIFF_HUNK_HEAD.match(line)
            if hunk:
                old = int(hunk.group(1))
                context = hunk.group(2).strip()[:80]
                if context and context not in contexts:
                    contexts.append(context)
                continue
            if not old or line.startswith("\\"):
                continue
            if line.startswith("-"):
                touched.add(old)
                old += 1
            elif line.startswith("+"):
                touched.add(max(1, old - 1))
            else:
                old += 1
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            outline[path] = ["(new file)"]
            continue
        names: list = []
        if path.endswith(".py"):
            try:
                with open(full, errors="replace") as handle:
                    owner, _, _ = python_functions(handle.read())
                for number in sorted(touched):
                    name = owner.get(number) or "(module level)"
                    if name not in names:
                        names.append(name)
            except (SyntaxError, ValueError, OSError, RecursionError):
                names = []
        outline[path] = names or contexts or ["(no enclosing definition shown)"]
    return outline

def outline_report(statement: str, first: dict, second: dict) -> str:
    text = statement or ""

    def mentioned(name: str) -> bool:
        short = name.rsplit(".", 1)[-1]
        if re.fullmatch(r"[A-Za-z_]\w*", short) is None:
            return False
        word = r"(?<![\w])%s(?![\w])" % re.escape(short)
        if re.search(r"`[^`\n]*%s[^`\n]*`" % word, text) or re.search(word + r"\s*\(", text):
            return True
        distinctive = "_" in short.strip("_") or re.search(r"[a-z][A-Z]", short) is not None
        return distinctive and re.search(word, text, re.I) is not None

    def places(outline: dict) -> str:
        parts = []
        for path, names in outline.items():
            shown = [name + ("*" if mentioned(name) else "") for name in names[:OUTLINE_NAMES_MAX]]
            parts.append("%s: %s" % (path, ", ".join(shown)))
        return "; ".join(parts) or "nothing"
    lines = ["WHERE EACH ATTEMPT CHANGES CODE (worked out from the diffs; * marks a name the task mentions)",
             "FIRST changes %s" % places(first), "SECOND changes %s" % places(second)]
    for label, mine, theirs in (("FIRST", first, second), ("SECOND", second, first)):
        extra = []
        for path, names in mine.items():
            if path not in theirs:
                extra.append("%s (a file the other attempt leaves alone)" % path)
                continue
            more = [name for name in names if name not in theirs[path]]
            if more:
                extra.append("%s: %s" % (path, ", ".join(more[:OUTLINE_NAMES_MAX])))
        if extra:
            lines.append("Only %s changes %s." % (label, "; ".join(extra)))
    return "\n".join(lines)

PICK_BRIEF = 'Two independent attempts implement the same task. Compare their diffs against the task statement and choose the one that satisfies the statement literally.\n\nCheck exact values, ordering, boundaries, cardinality, tolerated failures, imports, scope limits and behavior the task says to preserve. An extra edit that the task does not require counts against that attempt when it changes unrelated behavior. Use the repository evidence supplied with the attempts and do not judge by style alone.\n\nFinish with exactly one final line: VERDICT: FIRST or VERDICT: SECOND.'

def read_pick(reply: str) -> str:
    found = re.findall(r"VERDICT:\s*(FIRST|SECOND)\b", reply or "", re.I)
    return found[-1].upper() if found else ""

def reconcile(statement: str, first: str, second: str, allowance: "Allowance",
              beacon: "Beacon") -> str:
    if not (second or "").strip():
        beacon.fired("the second derivation produced nothing; the first stands")
        return first
    if not (first or "").strip():
        beacon.fired("the first derivation produced nothing; the second stands")
        return second
    if same_answer(first, second):
        beacon.fired("both derivations agree; handed in as they are")
        return first
    a, b = answer_shape(first), answer_shape(second)
    log_message("[SECOND] the derivations differ: files %s vs %s, %d vs %d added line(s)"
        % (sorted(a[0]), sorted(b[0]), len(a[1]), len(b[1])))
    if allowance.clock_left() < WALL_RESERVE_SEC * 2 or allowance.money_left() <= 0:
        beacon.fired("no room to decide; the first stands")
        return first
    seat = Seat(allowance, patient=False)
    report = ""
    try:
        root = os.getcwd()
        report = outline_report(statement, diff_outline(first, root), diff_outline(second, root))
        log_message("[SECOND] " + report.replace("\n", " | ")[:1200])
    except Exception as error:
        log_message("[SECOND] no outline: %s" % type(error).__name__)
    messages = [{"role": "system", "content": PICK_BRIEF},
                {"role": "user", "content": "TASK\n\n%s\n\n%sFIRST\n\n%s\n\nSECOND\n\n%s" % (
                    statement, (report + "\n\n") if report else "",
                    clip_output(first, PICK_MAX_PATCH_CHARS), clip_output(second, PICK_MAX_PATCH_CHARS))}]
    try:
        reply = seat.ask(messages, None)
    except Exception as error:
        beacon.fired("the pick could not be asked (%s); the first stands" % type(error).__name__)
        return first
    verdict = read_pick(str((reply or {}).get("content") or ""))
    if verdict == "SECOND":
        beacon.fired("picked the second derivation")
        return second
    beacon.fired("picked the first derivation" if verdict == "FIRST" else "no verdict read; the first stands")
    return first

TRIAL_BRIEF = "Two independent attempts changed the same task in different ways. You cannot edit the repository, but you may propose a small executable check. Provide the files needed for the check and one command; the runtime will execute it against the current tree, the first attempt and the second attempt and report exit status plus output tails.\n\nDerive the check from the task contract, not from either patch. Use concrete data and the named function, method, query or command. It should fail on the current tree and pass on a correct attempt, or verify a behavior that both attempts must preserve. Reach the code through names both attempts retain; do not test implementation style or a helper added by only one attempt. Follow the repository's own test setup and inspect an adjacent test first. If an all-three failure is environmental rather than task-related, repair the check and retry. Finish once the attempts are distinguished or no meaningful check remains.\n\nYour read budget is %d characters and your remaining check budget is %d runs; report resource use after each turn."
TRIAL_PRESS = 'No check has distinguished the attempts yet, and %d run(s) remain. Execute a check for an untested task requirement, such as a boundary, ordering or exact value, or repair a check that failed on all three attempts for an unrelated import, fixture or path problem.'
TRIAL_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline")
TRIAL_EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_check",
            "description": "Run one executable check on the code as it stands, on the first attempt and on the second. "
                           "Its files are added for the run only and removed afterwards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement_quote": {"type": "string", "description": "The requirement this check tests, copied exactly from the task."},
                    "files": {
                        "type": "array",
                        "description": "New files that make up the check: paths that do not exist in the repository and that neither attempt writes.",
                        "items": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                  "required": ["path", "content"]},
                    },
                    "command": {"type": "string", "description": "The command that runs the check from the repository root; exit status 0 means it passed."},
                },
                "required": ["requirement_quote", "files", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Stop: a check has told the attempts apart, or no check can.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
STRUCTURAL_FAILURE = re.compile(
    r"\b(?:ImportError|ModuleNotFoundError|AttributeError|NameError|NoMethodError|uninitialized constant|"
    r"undefined method|undefined local variable|cannot import name|has no attribute|is not defined|"
    r"undefined: |UndefinedFunction|Unknown function|UNKNOWN_FUNCTION|UNKNOWN_IDENTIFIER|does not exist)\b")

def trial_tools() -> list[dict]:
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in TRIAL_TOOL_NAMES] + TRIAL_EXTRA_TOOLS

def patch_paths(patch: str) -> set:
    return {head.group(2) for head in re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M)}

def trial_files(args: dict, tree: Tree, first: str, second: str) -> tuple:
    raw = args.get("files")
    if not isinstance(raw, list) or not raw:
        return [], "files has to list at least one file"
    if len(raw) > TRIAL_FILES_MAX:
        return [], "a check has at most %d files" % TRIAL_FILES_MAX
    written = patch_paths(first) | patch_paths(second)
    files, total = [], 0
    for item in raw:
        if not isinstance(item, dict):
            return [], "each file needs a path and a content"
        path = str(item.get("path") or "").strip().strip("`'\"").lstrip("./")
        content = str(item.get("content") or "")
        if not path or path.startswith(".git/") or path == ".git":
            return [], "a check file needs a path inside the repository"
        try:
            full = tree.absolute(path)
        except ToolFault as fault:
            return [], str(fault)
        if os.path.lexists(full):
            return [], "%s already exists; a check only adds new files" % path
        if path in written:
            return [], "%s is written by an attempt; a check only adds files neither attempt writes" % path
        total += len(content)
        files.append((path, content))
    if total > TRIAL_FILE_CHARS:
        return [], "the check's files come to %d characters, more than %d" % (total, TRIAL_FILE_CHARS)
    return files, ""

def trial_command(command: str) -> str:
    if not command.strip():
        return "command must not be empty"
    outward = NETWORK_COMMAND.search(command) if NETWORK_FENCE else None
    if outward:
        return "%s is not available here" % outward.group(1)
    if shell_database_write(command):
        return "the live database is left as it was found"
    blocked = HISTORY_GIT.search(command)
    if blocked:
        return "git %s is not available here" % blocked.group(1)
    return ""

def trial_side(tree: Tree, patch: str, files: list, command: str, budget: float) -> dict:
    record = {"applied": True, "exit": None, "timed_out": False, "seconds": 0.0, "tail": ""}
    tree.restore(max(5.0, min(60.0, budget / 3)))
    if (patch or "").strip():
        handle, path = tempfile.mkstemp(prefix="ridges-trial-", suffix=".diff")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(patch)
            code, out = run_git_command(["apply", "--whitespace=nowarn", path], tree.root, max(5.0, min(30.0, budget / 3)))
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if code != 0:
            record["applied"] = False
            record["tail"] = (out or "").strip()[-300:]
            return record
    for name, content in files:
        full = tree.absolute(name)
        os.makedirs(os.path.dirname(full) or tree.root, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    started = time.monotonic()
    job = Shell(command, tree.root)
    try:
        done, out = job.wait(max(1.0, budget))
        record["seconds"] = time.monotonic() - started
        if done:
            record["exit"] = job.process.returncode
        else:
            record["timed_out"] = True
        record["tail"] = (out or "")[-TRIAL_OUTPUT_CHARS:]
    finally:
        job.stop()
    return record

def ran_to_end(side) -> bool:
    return bool(side) and side["applied"] and not side["timed_out"] and side["exit"] is not None

def trial_split(sides: dict) -> str:
    first, second = sides.get("first"), sides.get("second")
    if not (ran_to_end(first) and ran_to_end(second)):
        return ""
    passed = [label for label, side in (("FIRST", first), ("SECOND", second)) if side["exit"] == 0]
    if len(passed) != 1:
        return ""
    loser = second if passed[0] == "FIRST" else first
    if STRUCTURAL_FAILURE.search(loser["tail"] or ""):
        return ""
    return passed[0]

def trial_recheck(sides: dict) -> str:
    split = trial_split(sides)
    if not split or not sides.get("base") or ran_to_end(sides["base"]):
        return ""
    return "second" if split == "FIRST" else "first"

def trial_winner(sides: dict) -> str:
    split = trial_split(sides)
    if not split or not sides.get("base"):
        return ""
    if ran_to_end(sides["base"]):
        return split
    again = sides.get("again")
    if not ran_to_end(again) or again.get("of") != ("second" if split == "FIRST" else "first"):
        return ""
    if again["exit"] == 0 or STRUCTURAL_FAILURE.search(again["tail"] or ""):
        return ""
    return split

def trial_press_on(runs: list, pressed: bool, deadline: float, spent: float, ceiling: float) -> bool:
    if pressed or len(runs) >= TRIAL_RUNS_MAX or any(trial_winner(run["sides"]) for run in runs):
        return False
    return deadline - time.monotonic() >= TRIAL_SIDE_MIN_SEC * 3 and spent < ceiling

def trial_report(runs: list) -> str:
    if not runs:
        return ""
    lines = ["CHECKS RUN BY THE RUNTIME (the same command on the code as it stands and on each attempt; exit 0 = passed; a check tests only what it was written to test, so weigh it against the task)"]
    for number, run in enumerate(runs, 1):
        lines.append("check %d, for: %s\ncommand: %s" % (number, compact_text(run["requirement"])[:300], compact_text(run["command"])[:300]))
        for name, content in run["files"]:
            lines.append("file %s:\n%s" % (name, clip_output(content, TRIAL_EVIDENCE_FILE_CHARS, "check file")))
        for label, key in (("code as it stands", "base"), ("FIRST", "first"), ("SECOND", "second"), ("", "again")):
            side = run["sides"].get(key)
            if key == "again":
                if side is None:
                    continue
                label = "%s once more" % ("FIRST" if side.get("of") == "first" else "SECOND")
            if side is None:
                lines.append("  %s: not run" % label)
            elif not side["applied"]:
                lines.append("  %s: the attempt did not apply" % label)
            elif side["timed_out"]:
                lines.append("  %s: still running after %.0fs" % (label, side["seconds"]))
            else:
                lines.append("  %s: exit %s after %.0fs; output ends:\n%s" % (
                    label, side["exit"], side["seconds"], clip_output(side["tail"], TRIAL_EVIDENCE_TAIL_CHARS, "output")))
    return "\n".join(lines)

def run_trial(statement: str, tree: Tree, allowance: Allowance, beacon: Beacon, first: str, second: str) -> tuple:
    beacon.reached(0, allowance.spent, allowance.clock_left())
    if not TRIAL:
        beacon.skipped("not switched on for this run")
        return "", ""
    if allowance.clock_left() < TRIAL_MIN_CLOCK_SEC or allowance.money_left() < TRIAL_MIN_MONEY_USD:
        beacon.skipped("too little of the run left to run checks")
        return "", ""
    deadline = time.monotonic() + min(TRIAL_MAX_SEC, allowance.clock_left() - TRIAL_FINISH_RESERVE_SEC)
    spent_at_entry, calls_at_entry = allowance.spent, allowance.calls
    ceiling = spent_at_entry + TRIAL_MAX_USD
    pool = ShellPool(tree.root)
    kit = Kit(tree, pool, allowance, label="TRIAL")
    seat = Seat(allowance, models=[TRIAL_MODEL], patient=False)
    allowed = {schema["function"]["name"] for schema in trial_tools()}
    cards = [card for card in DERIVE_STATE.get("cards") or [] if card][:2]
    opening = ("Task:\n" + clip_output(statement, SCOUT_STATEMENT_CHARS, "task")
               + "".join("\n\n" + card for card in cards)
               + "\n\nFIRST attempt:\n" + clip_output(first, TRIAL_PATCH_CHARS, "first attempt")
               + "\n\nSECOND attempt:\n" + clip_output(second, TRIAL_PATCH_CHARS, "second attempt"))
    messages = [{"role": "system", "content": TRIAL_BRIEF % (TRIAL_READ_BUDGET, TRIAL_RUNS_MAX)},
                {"role": "user", "content": opening}]
    runs: list = []
    read, stop, step, pressed = 0, "turns", 0, False
    try:
        for step in range(1, TRIAL_TURN_CAP + 1):
            if read >= TRIAL_READ_BUDGET:
                stop = "budget"
                break
            if allowance.spent >= ceiling:
                stop = "spend"
                break
            if deadline - time.monotonic() < TRIAL_SIDE_MIN_SEC * 3:
                stop = "clock"
                break
            reply = seat.ask(messages, trial_tools())
            raw = reply.get("tool_calls")
            calls = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
            entry = {"role": "assistant", "content": str(reply.get("content") or "")}
            if calls:
                entry["tool_calls"] = recorded_calls(calls)
            messages.append(entry)
            if not calls:
                if trial_press_on(runs, pressed, deadline, allowance.spent, ceiling):
                    pressed = True
                    messages.append({"role": "user", "content": TRIAL_PRESS % (TRIAL_RUNS_MAX - len(runs))})
                    continue
                stop = "silent"
                break
            finished = False
            for index, call in enumerate(calls):
                function = call.get("function")
                if not isinstance(function, dict):
                    function = {}
                name = str(function.get("name") or "")
                try:
                    args = json.loads(function.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments were not an object")
                except Exception as error:
                    result = "could not read the arguments: %s" % error
                else:
                    if finished:
                        result = "the checking has ended; this call was not run"
                    elif name == "done" and trial_press_on(runs, pressed, deadline, allowance.spent, ceiling):
                        pressed = True
                        result = TRIAL_PRESS % (TRIAL_RUNS_MAX - len(runs))
                    elif name == "done":
                        result, finished, stop = "checking ended", True, "done"
                    elif name == "run_check":
                        result = trial_run(statement, tree, args, first, second, runs, deadline)
                    elif name not in allowed:
                        result = "error: %s is not available while checking" % name
                    else:
                        try:
                            result = kit.run(name, args)
                        except (ToolFault, Finished) as fault:
                            result = "error: %s" % fault
                        except Exception as error:
                            result = "error: %s: %s" % (type(error).__name__, error)
                served = clip_output(str(result), READ_OUTPUT_CAP)
                read += len(served)
                messages.append({"role": "tool", "tool_call_id": call_ident(call, index), "content": served})
            if finished:
                break
            messages.append({"role": "user", "content": "Reading budget: %d used, %d left. Check runs: %d used, %d left."
                             % (read, max(0, TRIAL_READ_BUDGET - read), len(runs), max(0, TRIAL_RUNS_MAX - len(runs)))})
    except Exception as error:
        stop = "error"
        log_message("[TRIAL] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    finally:
        pool.close()
        try:
            tree.restore(max(5.0, min(60.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
        except Exception as error:
            log_message("[TRIAL] the tree could not be put back: %s" % type(error).__name__)
    winners = {trial_winner(run["sides"]) for run in runs} - {""}
    verdict = winners.pop() if len(winners) == 1 else ""
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    beacon.fired("stopped=%s steps=%d checks=%d pressed=%s separating=%s verdict=%s" % (
        stop, step, len(runs), "yes" if pressed else "no",
        ",".join(trial_winner(run["sides"]) or "-" for run in runs) or "none", verdict or "none"))
    beacon.bill()
    return verdict, trial_report(runs)

def trial_run(statement: str, tree: Tree, args: dict, first: str, second: str, runs: list, deadline: float) -> str:
    if len(runs) >= TRIAL_RUNS_MAX:
        return "no check runs left"
    requirement = str(args.get("requirement_quote") or "").strip()
    if not quoted_from(requirement, statement) or len(requirement) < SCOUT_QUOTE_CHARS[0]:
        return "check not run: requirement_quote is not copied from the task"
    files, why = trial_files(args, tree, first, second)
    if why:
        return "check not run: " + why
    command = str(args.get("command") or "")
    why = trial_command(command)
    if why:
        return "check not run: " + why
    sides: dict = {}
    run = {"requirement": requirement, "files": files, "command": command, "sides": sides}
    runs.append(run)
    try:
        for index, (key, patch) in enumerate((("base", ""), ("first", first), ("second", second))):
            left = deadline - time.monotonic()
            if left < TRIAL_SIDE_MIN_SEC:
                break
            sides[key] = trial_side(tree, patch, files, command, min(TRIAL_COMMAND_SEC, left / (3 - index)))
        again = trial_recheck(sides)
        left = deadline - time.monotonic()
        if again and left >= TRIAL_SIDE_MIN_SEC:
            sides["again"] = trial_side(tree, first if again == "first" else second, files, command,
                                        min(TRIAL_COMMAND_SEC, left))
            sides["again"]["of"] = again
    finally:
        tree.restore(max(5.0, min(60.0, deadline - time.monotonic())))
    log_message("[TRIAL] check %d: %s" % (len(runs), "; ".join(
        "%s exit=%s%s" % (key, side["exit"], "" if side["applied"] else " (did not apply)") for key, side in sides.items())))
    return trial_report([run]).split("\n", 1)[1] if sides else "the check could not be run in the time left"

def settle(statement: str, tree: Tree, allowance: Allowance, beacon: Beacon, first: str, second: str) -> str:
    if not (first or "").strip() or not (second or "").strip() or same_answer(first, second):
        return reconcile(statement, first, second, allowance, beacon)
    verdict, evidence = "", ""
    try:
        verdict, evidence = run_trial(statement, tree, allowance, Beacon("trial"), first, second)
    except Exception as error:
        log_message("[TRIAL] skipped: %s: %s" % (type(error).__name__, str(error)[:160]))
    if verdict == "FIRST":
        beacon.fired("a check passed on the first attempt and failed on the second; the first stands")
        return first
    if verdict == "SECOND":
        beacon.fired("a check passed on the second attempt and failed on the first; the second stands")
        return second
    return pick_with_checks(statement, first, second, allowance, beacon, evidence)


# --- workflow/orchestration.py ---
def repo_sketch(tree: Tree) -> str:
    parts = []
    code, listing = run_git_command(["ls-files"], tree.root, 30)
    files = listing.splitlines() if code == 0 else []
    tops: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for path in files:
        tops[path.split("/", 1)[0]] = tops.get(path.split("/", 1)[0], 0) + 1
        ext = os.path.splitext(path)[1] or "(none)"
        kinds[ext] = kinds.get(ext, 0) + 1
    parts.append("%d tracked files." % len(files))
    parts.append(
        "Top level: " + ", ".join("%s (%d)" % (k, v) for k, v in sorted(tops.items(), key=lambda kv: -kv[1])[:12])
    )
    parts.append(
        "Extensions: " + ", ".join("%s (%d)" % (k, v) for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])[:8])
    )
    for marker in ("pyproject.toml", "setup.cfg", "tox.ini", "Makefile"):
        if os.path.isfile(os.path.join(tree.root, marker)):
            parts.append("Present: " + marker)
    return "\n".join(parts)

def candidate_files(tree: Tree, statement: str, beacon: Beacon) -> list[str]:
    quoted = {m.lower() for m in QUOTED_RE.findall(statement)}
    terms = {w.lower() for w in WORD_RE.findall(statement)} - COMMON_WORDS
    terms |= quoted
    terms = {t for t in terms if len(t) > 3}
    if not terms:
        beacon.skipped("the problem statement carried no usable identifier")
        return []
    scores: dict[str, float] = {}
    looked = 0
    deadline = time.monotonic() + PRELOCATE_BUDGET_SEC
    for term in sorted(terms)[:40]:
        left = deadline - time.monotonic()
        if looked >= 30 or left <= 1.0:
            break
        try:
            done = subprocess.run(
                ["git", "grep", "-lFi", "--", term],
                cwd=tree.root,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=min(PRELOCATE_TERM_SEC, left),
            )
        except (subprocess.TimeoutExpired, OSError):
            looked += 1
            continue
        looked += 1
        hits = [p for p in (done.stdout or "").splitlines() if p]
        if not hits or len(hits) > 60:
            continue
        weight = (1.0 / len(hits)) * (3.0 if term in quoted else 1.0)
        for path in hits:
            penalty = 0.25 if ("test" in path.lower() or path.startswith("docs/")) else 1.0
            scores[path] = scores.get(path, 0.0) + weight * penalty
    ranked = [p for p, _ in sorted(scores.items(), key=lambda kv: -kv[1])][:12]
    beacon.fired("%d terms over %d files -> %d candidates" % (len(terms), len(scores), len(ranked)))
    return ranked

BRIEF = "You are the implementation agent for a production database-query task in the checked-out repository. Use the available file and shell tools. The working tree is the deliverable: keep the correct edit in place and call submit only after validation.\n\nHonor the repository's existing abstractions, imports and conventions. Add no dependency, avoid unrelated rewrites, do not weaken tests, and do not encode task examples as special cases. Treat every explicit file, function, import, behavior and construct restriction as a hard boundary.\n\nUse each turn efficiently. Put independent tool calls in one reply. Start slow commands in the background and collect them later; continue useful repository reading while they run.\n\nUNDERSTAND THE TASK\n1. Locate the exact target file and definition. Read its imports, callers, model or schema, and nearby repository-native query patterns before editing. If the task names a file or method boundary, do not edit outside it.\n2. Translate the requested behavior into a small table covering empty input, NULLs, duplicate relationships, unrelated rows, filters, ordering, cardinality and projected fields. Do not add requirements the task does not state.\n3. Identify the actual database engine and query layer from repository evidence. Keep queries lazy and composable unless materialization or a write is explicitly required.\n\nREPEATED DEFECTS\nWhen the same rule is broken in multiple places, first obtain the complete set with one repeatable search, lint or compile command and record its count. Apply mechanical fixes consistently, run the same command again, and finish only when the remaining hits are understood.\n\nIMPLEMENT AND CHECK\nMake the smallest complete patch. Inspect for row multiplication, eager evaluation, per-row queries, incompatible engine constructs and migration-state mismatches. Map each task requirement to a changed expression, an intentionally preserved line, or repository evidence. After editing, reread the complete enclosing query or transaction and compare the map with the diff. Preserve filters, ordering, locks, pagination, no-op behavior, imports and signatures unless the task changes them.\n\nRun a cheap syntax or query-construction check first, then the narrow relevant tests. If a test cannot run, use the cheapest available parser, query rendering or focused repository check and keep the limitation in mind.\n\nBEFORE SUBMITTING\nReview every diff hunk. Confirm the patch stays within scope, preserves required laziness and multiplicity, uses compatible imports and signatures, and leaves unrelated behavior unchanged. Then call submit with a one-line summary."

def without_sweep(brief: str) -> str:
    start = brief.find("WHEN THE SAME DEFECT")
    end = brief.find("IMPLEMENT AND VALIDATE")
    return brief[:start] + brief[end:] if 0 <= start < end else brief

RESTRUCTURE = 'WHEN THE TASK REQUESTS A RESTRUCTURE\n\nChange only the behavior named by the task. Preserve every other observable behavior, including failure handling, defaults, ordering, short-circuiting, exception boundaries and exact values.\n\n1. Move existing code instead of recreating it from memory. A moved block should retain its text except for mechanical changes required by its new location, such as qualification or parameters.\n2. Preserve distinctions between branches. Do not merge cases merely because they look similar, and implement every explicit boundary, ordering and tolerated-failure rule literally.\n3. Inspect the final diff hunk by hunk. Each changed line must be a requested behavior change, a move, or an unavoidable mechanical consequence of a move.'
FOLD_JOIN = "merge branches merely because they look similar."
FOLD_PAIRS = """ A condition you rewrite must still tell
   apart everything the original told apart. These are the pairs that get folded
   together, each of which has broken a working module:
   - a key absent from a mapping, and a key present with a falsy value:
     `d.get(k)` is not `k in d`, and dropping keys the caller did not mention is
     not the same as keeping them.
   - `None` meaning not-given, and a value that is empty, zero or False:
     `if x is None` is not `if not x`. If `None` cleared something and omitting
     it left it alone, that stays true.
   - an empty selection and a selection of everything. Replacing nothing is not
     replacing all.
   - an absent pattern and one that matches everything. `None` is not `*`.
   - a path that stops one level short of a target, and one that reaches it.
   - which of two shapes an ambiguous name is read as.
   - the order results come back in.
   - the spelling a value carries: one base against another, bytes against text.
   - a failure that was visible to the caller, and one that is swallowed. If a
     path raised, logged, or ended a session before, it still does; a `try` you
     widen or an error you turn into a default is a behaviour you removed."""
INVARIANTS = 'KEEP DATABASE INVARIANTS INTACT\n\nChange the narrowest decision point that fixes the task. Preserve existing names, operators, defaults, guards, branches and exception boundaries. Keep transaction boundaries, query laziness, ordering, cardinality, NULL semantics, and the distinction between entity rows and relationship rows unless the task explicitly changes one.'
DATABASE_QUERY_ENGINEERING = "DATABASE QUERY IMPLEMENTATION GUIDANCE\n\nBefore editing a production query, identify five contracts: allowed source scope, exact result semantics, laziness and composability, database-work complexity, and the actual engine or query-layer rules. Treat explicit task restrictions on imports and constructs as implementation requirements.\n\n1. Read the complete target definition, its imports, and the nearest caller, model, schema or migration. Use repository-native APIs and compatibility patterns. If only one method may change, keep the whole patch inside it.\n2. Check empty inputs, NULLs, duplicate joins, unrelated rows, filtering, ordering, slicing, projections and transaction boundaries. Preserve cardinality and keep construction lazy unless a write is required.\n3. Judge complexity from the final query shape. Avoid Python row iteration, materializing only to filter, and probe-then-per-row-query designs. Prefer a composable set-based expression supported by the repository.\n4. For a correlated ORM subquery, build the complete scalar shape before testing it: correlate, remove irrelevant ordering, group at the intended grain, annotate the aggregate, select one column and limit to one row where required. Do not pass an unresolved outer reference to an API that needs an immediate Python boolean; use the repository's NULL-safe query expressions and inspect rendered SQL.\n5. Match the actual PostgreSQL, ClickHouse, ORM, query-builder, manager, filterset or migration behavior. For indexes, match production predicates, operator classes, column order and migration state.\n6. Before hand-in, inspect scope, query count, schema state, multiplicity, imports and untouched behavior. Run a cheap compile/render check and then the narrow relevant tests. Treat a hung database check as evidence that the current check or query shape needs revision.\n7. When imports are fixed, reach additional query constructs through already imported modules and do not add helpers, constants, local imports or unrelated formatting.\n8. Treat the live database as read-only. Use rollback-safe PostgreSQL scenarios; on ClickHouse use inline values(...) or numbers(n) and never alter persistent data or schema.\n\nRECURRING SHAPES\n- Limits and retention require a total order with a unique final tie-breaker, including per-owner limits.\n- Pagination must apply the named order everywhere, clamp limits before offsets, fetch one extra row for has-more, and reject malformed values.\n- Select access and history boundaries before choosing latest or first rows; match all identifying key columns.\n- Parenthesize dynamic predicates before combining them with scope filters.\n- Apply filters at the correct stage relative to windows and preserve the intended partition.\n- Aggregate child rows at their native grain before comparing or joining upward.\n- Express alternative access paths as separate correlated EXISTS conditions or a union of keys to avoid join multiplication.\n- Lock rows in deterministic key order; deduplicate and sort upsert or batch-update input, reread inside the lock, and update only owned columns.\n- Treat bitmasks with bitwise tests, set and clear operations; never compare or overwrite the whole value.\n- Perform case-insensitive matching in the database using its established operator, function or collation.\n- Keep annotation helpers lazy, composable and in the caller's order.\n- Add only the smallest index set serving the real predicates and order.\n- For ClickHouse FINAL, argMax or LIMIT BY, ensure filtering and deduplication happen at the intended stage; data-skipping indexes must match the indexed expression and supported function."

def compose_brief() -> str:
    text = BRIEF if SWEEP_WORKFLOW else without_sweep(BRIEF)
    joins = spliced = 0
    marker = "BEFORE YOU SUBMIT"
    if MOVE_VERBATIM:
        section = RESTRUCTURE
        joins = section.count(FOLD_JOIN)
        if FOLD_ANCHORS and joins == 1:
            section = section.replace(FOLD_JOIN, FOLD_JOIN + FOLD_PAIRS, 1)
            spliced = 1
        text = (text.replace(marker, section + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + section)
    if INVARIANT_BRIEF:
        text = (text.replace(marker, INVARIANTS + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + INVARIANTS)
    text = (text.replace(marker, DATABASE_QUERY_ENGINEERING + "\n\n" + marker, 1)
            if marker in text else text + "\n\n" + DATABASE_QUERY_ENGINEERING)
    log_message("[FOLD] anchors=%d verbatim=%d joins=%d spliced=%d"
        % (FOLD_ANCHORS, MOVE_VERBATIM, joins, spliced))
    return text

DECLARED_SCOPE_CHARS = 16_000
SCOPE_PHRASE = re.compile(
    r"\b(?:you may (?:only )?edit(?: only)?|may edit only|edit only|"
    r"(?:limit|confine|restrict)(?:ed)? (?:your |the |all |production |the production )?(?:changes|edits|modifications|work) to|"
    r"(?:changes|edits) (?:must |should )?(?:stay|remain|be kept) (?:within|under|inside)|"
    r"(?:production )?(?:changes|edits) (?:are |must be |should be )?(?:limited|confined|restricted) to|"
    r"only (?:modify|change|edit|touch))\b((?:[^.]|\.(?!\s))*)", re.I)
BACKTICK_PATH = re.compile(r"`([^`\s]+\.[A-Za-z0-9]{1,6}(?:\.[A-Za-z0-9]{1,4})?)`")

def scope_paths(statement: str, root: str) -> list[str]:
    found: list[str] = []
    for phrase in SCOPE_PHRASE.finditer(statement or ""):
        for token in BACKTICK_PATH.findall(phrase.group(1)):
            path = repo_relative(token, root)
            if not path or TEST_PATH.search(path) or path in found:
                continue
            if os.path.isfile(os.path.join(root, path)):
                found.append(path)
    return found

def declared_scope_excerpt(statement: str, tree: Tree) -> str:
    named = scope_paths(statement, tree.root)
    path = named[0] if named else declared_file(statement, tree.root)
    if path is None:
        return ""
    try:
        source = tree.read(path)
    except ToolFault:
        return ""
    lines = source.count("\n") + (0 if source.endswith("\n") else 1)
    rendered = ("DECLARED SOURCE SCOPE (current code, not a proposed answer)\n"
                "FILE %s (%d lines)\n\n%s" % (path, lines, source))
    return clip_output(rendered, DECLARED_SCOPE_CHARS, "declared source file")

def opening_message(statement: str, tree: Tree, hints: list[str],
                    database: "Database | None" = None, warden: "Warden | None" = None) -> str:
    blocks = ["Problem to fix:\n\n" + statement.strip(), "\nRepository at a glance:\n" + repo_sketch(tree)]
    if hints:
        blocks.append(
            "\nFiles whose contents overlap the rare terms in the problem, most overlap first. "
            "This is a starting point produced by text matching, not an answer:\n"
            + "\n".join("  " + p for p in hints)
        )
    if database is not None:
        try:
            blocks.append("\nDatabase access:\n" + database.brief())
        except Exception as error:
            log_message("[DB] the brief could not be written: %s" % type(error).__name__)
    try:
        reading = warden.opening_reading() if warden is not None else ""
    except Exception as error:
        reading = ""
        log_message("[WARDEN] the opening reading could not be written: %s" % type(error).__name__)
    if reading:
        log_message("[WARDEN] opening reading given: %s" % reading[:160])
        blocks.append("\n" + reading)
    scope = declared_scope_excerpt(statement, tree)
    if scope:
        blocks.append(
            "\nThe task names this source scope explicitly. Its current contents are "
            "included so you can preserve its imports and surrounding code from the "
            "first turn:\n" + scope
        )
    return "\n".join(blocks)

def shrink_transcript(messages: list[dict], cap: int, beacon: Beacon) -> bool:
    total = sum(len(str(m.get("content") or "")) for m in messages)
    if total <= cap:
        return False
    beacon.fired("transcript %dB over cap %dB" % (total, cap))
    freed = 0
    for message in messages[2 : max(2, len(messages) - 12)]:
        if message.get("role") != "tool":
            continue
        body = str(message.get("content") or "")
        if len(body) <= 400:
            continue
        message["content"] = "[%d characters of earlier tool output dropped to fit the context]" % len(body)
        freed += len(body)
        total -= len(body)
        if total <= cap * 0.7:
            break
    if not freed:
        beacon.skipped("nothing bulky enough to drop")
        return False
    log_message("[TRIM] freed %dB, transcript now ~%dB" % (freed, total))
    return True

SCOUT_BRIEF = 'You are a read-ahead scout for another agent. You may inspect the repository with the supplied read-only tools, but you must not edit files, run write commands or submit.\n\nBuild a compact evidence card for the task. Establish what currently decides the result, what behavior is required, which files or definitions are relevant, and which nearby code or tests provide precedent. Use exact repository quotes for the decisive evidence. Do not speculate beyond what the task and files support.\n\nReturn a grounded handoff containing: the current result, the requested result, the deciding definition or call path, relevant files, two short exact quotes, and any uncertainty. If the task names a scope boundary, report it explicitly. Stop when the card is adequately supported.'
SCOUT_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline")
SCOUT_CARD_FIELDS = (("decided_by", "what decides the result"), ("current_result", "what the code returns now"),
                     ("case", "the case"), ("required_result", "what the task requires"),
                     ("probe", "how to show the difference"), ("change_boundary", "change boundary"))
SCOUT_EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_case",
            "description": "Record the one concrete case on which the code as it stands and the task disagree, "
                           "anchored by exact quotes from the task and from a repository file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement_quote": {"type": "string", "description": "The requirement, copied exactly from the task."},
                    "code_path": {"type": "string", "description": "Repository path of the code the case runs through; not a test."},
                    "code_quote": {"type": "string", "description": "Lines copied exactly from that file."},
                    "related_path": {"type": "string", "description": "Optional: a caller, schema or test that bears on the case."},
                    "related_quote": {"type": "string", "description": "Lines copied exactly from related_path; required with it."},
                    "decided_by": {"type": "string", "description": "Which rows, columns or objects decide the result, and where they come from."},
                    "current_result": {"type": "string", "description": "What the code returns for the case now, and why."},
                    "case": {"type": "string", "description": "Concrete minimal rows, objects or request values."},
                    "required_result": {"type": "string", "description": "What the task requires for the same case."},
                    "probe": {"type": "string", "description": "The smallest existing command or reading that shows the difference."},
                    "change_boundary": {"type": "string", "description": "What has to change, plus one neighbouring case that keeps its "
                                        "present result: its input, that result, and how to check it. Say what is not established when nothing is."},
                },
                "required": ["requirement_quote", "code_path", "code_quote", "decided_by", "current_result", "case",
                             "required_result", "probe", "change_boundary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "no_case",
            "description": "Stop: the task and the repository do not support a specific case.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

def scout_tools() -> list[dict]:
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in SCOUT_TOOL_NAMES] + SCOUT_EXTRA_TOOLS

def normalise_text(text: object) -> str:
    return " ".join(str(text or "").split())

def quoted_from(quote: str, text: str) -> bool:
    return bool(quote) and (quote in text or normalise_text(quote) in normalise_text(text))

def scout_quote(args: dict, name: str) -> str:
    return str(args.get(name) or "").strip()

def grounded_card(statement: str, tree: Tree, args: dict) -> tuple:
    low, high = SCOUT_QUOTE_CHARS
    requirement = scout_quote(args, "requirement_quote")
    if not low <= len(requirement) <= high:
        return "", "requirement_quote has to be %d to %d characters" % (low, high)
    if not quoted_from(requirement, statement):
        return "", "requirement_quote is not copied from the task"
    path = scout_quote(args, "code_path").strip("`'\"")
    quote = scout_quote(args, "code_quote")
    if not path or not quote:
        return "", "code_path and code_quote are both required"
    if TEST_PATH.search(path):
        return "", "code_path has to be production code, not a test"
    if not low <= len(quote) <= high:
        return "", "code_quote has to be %d to %d characters" % (low, high)
    try:
        source = tree.read(path)
    except ToolFault as fault:
        return "", str(fault)
    if not quoted_from(quote, source):
        return "", "code_quote is not copied from %s" % path
    related = scout_quote(args, "related_path").strip("`'\"")
    related_quote = scout_quote(args, "related_quote")
    if bool(related) != bool(related_quote):
        return "", "related_path and related_quote go together"
    if related:
        if not low <= len(related_quote) <= high:
            return "", "related_quote has to be %d to %d characters" % (low, high)
        try:
            related_source = tree.read(related)
        except ToolFault as fault:
            return "", str(fault)
        if not quoted_from(related_quote, related_source):
            return "", "related_quote is not copied from %s" % related
    fields = {name: normalise_text(args.get(name))[:1200] for name, _ in SCOUT_CARD_FIELDS}
    thin = [name for name, value in fields.items() if len(value) < low]
    if thin:
        return "", "too little in " + ", ".join(thin)
    anchors = ["- task requirement: `%s`" % compact_text(requirement)[:900],
               "- code anchor `%s`: `%s`" % (path, compact_text(quote)[:700])]
    if related:
        anchors.append("- related anchor `%s`: `%s`" % (related, compact_text(related_quote)[:700]))
    head = "Case found before any edit, anchored in this repository\n" + "\n".join(anchors)
    labels = [(name, "\n- %s: " % label) for name, label in SCOUT_CARD_FIELDS]
    card = head + "".join(label + fields[name] for name, label in labels)
    if len(card) <= SCOUT_CARD_CHARS:
        return card, ""
    room = (SCOUT_CARD_CHARS - len(head) - sum(len(label) for _, label in labels)) // len(labels)
    if room < 80:
        return "", "the anchors leave no room for the case itself"
    return head + "".join(label + clip_output(fields[name], room, name) for name, label in labels), ""

def run_scout(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance, beacon: Beacon,
              hints: list) -> str:
    beacon.reached(0, allowance.spent, allowance.clock_left())
    if not SCOUT_SEAT:
        beacon.skipped("not switched on for this run")
        return ""
    if allowance.clock_left() < SCOUT_MIN_CLOCK_SEC or allowance.money_left() < SCOUT_MIN_MONEY_USD:
        beacon.skipped("too little of the run left to read ahead")
        return ""
    spent_at_entry, calls_at_entry = allowance.spent, allowance.calls
    ceiling = spent_at_entry + SCOUT_MAX_USD
    kit = Kit(tree, pool, allowance, label="SCOUT")
    seat = Seat(allowance, models=[SCOUT_MODEL], patient=False)
    allowed = {schema["function"]["name"] for schema in scout_tools()}
    opening = ("Task:\n" + clip_output(statement, SCOUT_STATEMENT_CHARS, "task")
               + "\n\nRepository at a glance:\n" + repo_sketch(tree))
    if hints:
        opening += ("\n\nFiles whose contents overlap the rare terms in the task, most overlap first; a starting "
                    "point from text matching, not a conclusion:\n" + "\n".join("  " + p for p in hints[:12]))
    messages = [{"role": "system", "content": SCOUT_BRIEF % SCOUT_READ_BUDGET},
                {"role": "user", "content": opening}]
    card, read, stop, step = "", 0, "turns", 0
    try:
        for step in range(1, SCOUT_TURN_CAP + 1):
            if read >= SCOUT_READ_BUDGET:
                stop = "budget"
                break
            if allowance.spent >= ceiling:
                stop = "spend"
                break
            reply = seat.ask(messages, scout_tools())
            raw = reply.get("tool_calls")
            calls = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
            entry = {"role": "assistant", "content": str(reply.get("content") or "")}
            if calls:
                entry["tool_calls"] = recorded_calls(calls)
            messages.append(entry)
            if not calls:
                stop = "silent"
                break
            finished = False
            for index, call in enumerate(calls):
                function = call.get("function")
                if not isinstance(function, dict):
                    function = {}
                name = str(function.get("name") or "")
                try:
                    args = json.loads(function.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments were not an object")
                except Exception as error:
                    result = "could not read the arguments: %s" % error
                else:
                    if finished:
                        result = "the reading has ended; this call was not run"
                    elif name == "no_case":
                        result, finished, stop = "ended without a case", True, "none"
                    elif name == "set_case":
                        candidate, why = grounded_card(statement, tree, args)
                        if why:
                            result = "card not taken: " + why
                        else:
                            card, result, finished, stop = candidate, "card taken", True, "card"
                    elif name not in allowed:
                        result = "error: %s is not available while reading ahead" % name
                    else:
                        try:
                            result = kit.run(name, args)
                        except (ToolFault, Finished) as fault:
                            result = "error: %s" % fault
                        except Exception as error:
                            result = "error: %s: %s" % (type(error).__name__, error)
                served = clip_output(str(result), READ_OUTPUT_CAP)
                read += len(served)
                messages.append({"role": "tool", "tool_call_id": call_ident(call, index), "content": served})
            if finished:
                break
            messages.append({"role": "user", "content": "Reading budget: %d used, %d left. Record one grounded "
                             "card, or stop." % (read, max(0, SCOUT_READ_BUDGET - read))})
    except Exception as error:
        stop = "error"
        log_message("[SCOUT] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    beacon.fired("stopped=%s steps=%d read=%dc card=%dB" % (stop, step, read, len(card)))
    if card:
        log_message("[SCOUT] card %s" % card.replace("\n", " | ")[:SCOUT_CARD_CHARS])
    beacon.bill()
    return card

SCOUT_HANDOFF = 'Read-ahead summary for the implementation agent:\nUse only the conclusions supported by the quoted repository evidence below. Keep the stated scope boundary. Verify any uncertain point before editing, and do not treat a hypothesis as a requirement.'

def scout_handoff(card: str) -> str:
    return SCOUT_HANDOFF + card if (card or "").strip() else ""

PLAN_BRIEF = 'You are preparing an implementation plan, not editing the repository. You may use only the supplied read-only tools. Do not write files, run commands that mutate state, or submit.\n\nRead the task and relevant code, then produce a concise, ordered plan. Identify the exact definition to change, the existing abstraction and imports to reuse, the behavior and edge cases to preserve, the narrow checks to run, and any explicit scope or construct restrictions. Base each conclusion on repository evidence; distinguish facts from assumptions. Do not invent requirements or redesign unrelated code.'
PLAN_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline")
PLAN_EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_plan",
            "description": "Record the current best plan, replacing any earlier one. Call this "
                           "as soon as you have something worth handing over, and again "
                           "whenever it improves.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Files, line ranges, and what has to become true."}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done_planning",
            "description": "Stop planning and hand the note over. Call this as soon as the plan "
                           "is good enough; there is no reward for spending the whole budget.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

def plan_tools() -> list[dict]:
    return [s for s in TOOL_SCHEMAS
            if s["function"]["name"] in PLAN_TOOL_NAMES] + PLAN_EXTRA_TOOLS

def run_plan(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance,
             beacon: Beacon, turn: int) -> str:
    beacon.reached(turn, allowance.spent, allowance.clock_left())
    if not PLAN_SEAT:
        beacon.skipped("not switched on for this run")
        return ""
    spent_at_entry, calls_at_entry = allowance.spent, allowance.calls
    ceiling = spent_at_entry + allowance.soft_usd * PLAN_SPEND_SHARE
    kit = Kit(tree, pool, allowance, label="PLAN")
    seat = Seat(allowance, models=[PLAN_MODEL], patient=False)
    messages = [{"role": "system", "content": PLAN_BRIEF % PLAN_READ_BUDGET},
                {"role": "user", "content": statement}]
    note, read, stop, step = "", 0, "turns", 0
    try:
        for step in range(1, PLAN_TURN_CAP + 1):
            if read >= PLAN_READ_BUDGET:
                stop = "budget"
                break
            if allowance.spent >= ceiling or allowance.money_left() <= 0:
                stop = "spend"
                break
            reply = seat.ask(messages, plan_tools())
            raw = reply.get("tool_calls")
            calls = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
            entry = {"role": "assistant", "content": str(reply.get("content") or "")}
            if calls:
                entry["tool_calls"] = recorded_calls(calls)
            messages.append(entry)
            if not calls:
                stop = "silent"
                break
            finished = False
            for index, call in enumerate(calls):
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    function = {}
                name = str(function.get("name") or "")
                try:
                    args = json.loads(function.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments were not an object")
                except Exception as error:
                    result = "could not read the arguments: %s" % error
                else:
                    if name == "done_planning":
                        finished = True
                        result = "planning ended"
                    elif name == "set_plan":
                        note = str(args.get("text") or "")[:PLAN_NOTE_CHARS]
                        result = "plan recorded, %d characters" % len(note)
                    else:
                        try:
                            result = kit.run(name, args)
                        except (ToolFault, Finished) as fault:
                            result = "error: %s" % fault
                        except Exception as error:
                            result = "error: %s: %s" % (type(error).__name__, error)
                served = clip_output(str(result), READ_OUTPUT_CAP)
                read += len(served)
                messages.append({"role": "tool", "tool_call_id": call_ident(call, index),
                                 "content": served})
            if finished:
                stop = "done"
                break
            messages.append({"role": "user", "content": "Reading budget: %d used, %d left."
                             % (read, max(0, PLAN_READ_BUDGET - read))})
    except Exception as error:
        stop = "error"
        log_message("[PLAN] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    beacon.fired("stopped=%s steps=%d read=%dc note=%dB" % (stop, step, read, len(note)))
    empty = beacon.artefact("before", "")
    beacon.outcome(empty, note.strip())
    if note.strip():
        log_message("[PLAN] note %s" % note.strip().replace("\n", " | ")[:PLAN_NOTE_CHARS])
    beacon.bill()
    return note.strip()

def should_press(allowance: Allowance, turn: int, pressed: int) -> bool:
    if allowance.edits or pressed >= EDIT_PRESSES_MAX:
        return False
    return turn > FIRST_EDIT_DEADLINE_TURN

def execute_batch(calls: list, kit: Kit, messages: list, allowance: Allowance) -> None:
    """Run edits/checks before submit, and answer every advertised tool call."""
    def name(call):
        function = call.get("function")
        return function.get("name", "") if isinstance(function, dict) else ""
    order = [i for i, c in enumerate(calls) if name(c) != "submit"]
    order += [i for i, c in enumerate(calls) if name(c) == "submit"]
    results = {}
    submitted = False
    for index in order:
        call = calls[index]
        tool_name = name(call)
        if submitted and tool_name == "submit":
            results[index] = "Deferred: read the previous submit result before retrying."
            continue
        if allowance.halt_reason():
            results[index] = "Not executed: run allowance exhausted."
            continue
        submitted |= tool_name == "submit"
        try:
            args = json.loads(call.get("function", {}).get("arguments") or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            result = kit.run(tool_name, args)
        except Finished:
            raise
        except Exception as error:
            result = "error: %s: %s" % (type(error).__name__, error)
        results[index] = clip_output(str(result), READ_OUTPUT_CAP)
    for index, call in enumerate(calls):
        messages.append({"role": "tool", "tool_call_id": call_ident(call, index),
                         "content": results.get(index, "Not executed.")})

def run_agent_workflow(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance,
          findings: "FindingMap | None" = None) -> None:
    seat = Seat(allowance)
    read = None
    try:
        read = read_scope(statement, tree, allowance)
    except Exception as error:
        log_message("[SCOPEREAD] skipped: %s" % type(error).__name__)
    warden = Warden(tree, pool, allowance, statement, read)
    DERIVE_STATE["warden"] = warden
    warden.arm()
    database = None
    adaptive_probe = (
        ADAPTIVE_DB_CONTEXT
        and adaptive_context_needed(statement)
        and allowance.clock_left() >= max(300.0, PRELOCATE_BUDGET_SEC * 5)
        and allowance.money_left() >= 0.08
    )
    if DB_PROBE or adaptive_probe:
        try:
            code, listing = run_git_command(["ls-files"], tree.root, 30)
            database = Database(tree, listing.splitlines() if code == 0 else [],
                                detect_engine_hint(statement), allowance)
            database.discover()
            if adaptive_probe and not DB_PROBE:
                log_message("[DB] adaptive database context enabled for a database-shaped task")
        except Exception as error:
            log_message("[DB] skipped: %s: %s" % (type(error).__name__, str(error)[:160]))
            database = None
    else:
        log_message("[DB] skipped: not switched on for this run")
    try:
        warden.hold()
    except Exception as error:
        log_message("[WARDEN] skipped the hold: %s: %s" % (type(error).__name__, str(error)[:160]))
    kit = Kit(tree, pool, allowance, warden, findings=findings, database=database)
    locate = Beacon("prelocate")
    trim = Beacon("trim")
    sweep = Beacon("sweep")
    plan = Beacon("plan")
    scout = Beacon("scout")
    locate.reached(0, allowance.spent, allowance.clock_left())
    if PRELOCATE:
        hints = candidate_files(tree, statement, locate)
    else:
        locate.skipped("not switched on for this run")
        hints = []
    card = ""
    try:
        card = run_scout(statement, tree, pool, allowance, scout, hints)
        if card:
            DERIVE_STATE.setdefault("cards", []).append(card)
    except Exception as error:
        log_message("[SCOUT] skipped: %s: %s" % (type(error).__name__, str(error)[:160]))
    sweep.reached(0, allowance.spent, allowance.clock_left())
    if SWEEP_WORKFLOW:
        sweep.fired("clause present")
    else:
        sweep.skipped("not switched on for this run")
    verbatim = Beacon("verbatim")
    verbatim.reached(0, allowance.spent, allowance.clock_left())
    if MOVE_VERBATIM:
        verbatim.fired("clause present")
    else:
        verbatim.skipped("not switched on for this run")
    kit.conform.reached(0, allowance.spent, allowance.clock_left())
    if not SUBMIT_CONFORM:
        kit.conform.skipped("not switched on for this run")
    if findings is not None:
        findings.beacon.reached(0, allowance.spent, allowance.clock_left())
    else:
        Beacon("findings").skipped("not switched on for this run")
    messages: list[dict] = [
        {"role": "system", "content": compose_brief()},
        {"role": "user", "content": opening_message(statement, tree, hints, database, warden) + scout_handoff(card)},
    ]
    cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
    log_message("[LOOP] transcript cap set for %s" % seat.current())
    blanks = 0
    pressed = 0
    wrapped_up = False
    for turn in range(1, TURN_CEILING + 1):
        warden.collect()
        halt = allowance.halt_reason()
        if halt:
            log_message("[LOOP] stopping on %s at turn %d" % (halt, turn))
            return
        if should_press(allowance, turn, pressed):
            pressed += 1
            log_message("[LOOP] %d turns and %.0f%% of the clock without an edit; pressing for one (#%d)"
                % (turn - 1, 100.0 * allowance.elapsed() / max(1.0, allowance.total()), pressed))
            press = (
                "No edit yet. Identify the production result grain and the smallest "
                "evidence-backed change, then implement it inside the permitted scope. "
                "Do not guess merely to create a diff. Reserve time for a focused check."
            )
            if pressed == 1:
                note = run_plan(statement, tree, pool, allowance, plan, turn)
                if note:
                    press += (
                        "\n\nA second agent read the repository and left this note. "
                        "It did not run anything and may be wrong -- check it against "
                        "the file before you act on it.\n\n" + note
                    )
            messages.append({"role": "user", "content": press})
        if TRANSCRIPT_CAP:
            shrink_transcript(messages, cap, trim)
        answering = seat.current()
        reply = seat.ask(messages, TOOL_SCHEMAS)
        if seat.current() != answering:
            cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
            log_message("[LOOP] seat changed under us; transcript cap set for %s"
                % seat.current())
        raw = reply.get("tool_calls")
        calls = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
        text = str(reply.get("content") or "")
        normalised_ids = normalise_tool_call_ids(calls, turn)
        if normalised_ids:
            log_message("[IDNORM] turn %d: normalised %d tool-call id(s)" %
                (turn, normalised_ids))
        entry = {"role": "assistant", "content": text if calls else (text or "")}
        if calls:
            entry["tool_calls"] = recorded_calls(calls)
        messages.append(entry)
        if not calls:
            blanks += 1
            if blanks >= BLANK_REPLY_CEILING:
                if seat.retire(seat.current()):
                    log_message("[LOOP] %d blank replies; changed seats" % blanks)
                    cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
                    log_message("[LOOP] transcript cap set for %s"
                        % seat.current())
                    blanks = 0
                    continue
                log_message("[LOOP] %d blank replies and no seat left" % blanks)
                return
            messages.append(
                {
                    "role": "user",
                    "content": "That reply carried no tool call. Take the next concrete step, "
                    "or call submit if the change is complete.",
                }
            )
            continue
        blanks = 0
        log_message("[LOOP] turn %d: %d tool call(s)" % (turn, len(calls)))
        try:
            execute_batch(calls, kit, messages, allowance)
        except Finished as done:
            log_message("[LOOP] submit at turn %d: %s" % (turn, str(done)[:200]))
            return
        if not wrapped_up and turn >= WRAPUP_TURN:
            wrapped_up = True
            messages.append(
                {
                    "role": "user",
                    "content": "You are near the end of the run. Finish the change you are on, "
                    "re-run the command that lists the remaining sites, and call submit.",
                }
            )
    log_message("[LOOP] hit the turn ceiling")


# --- workflow/entrypoint.py ---
def pick_with_checks(statement: str, first: str, second: str, allowance: Allowance, beacon: Beacon,
                     evidence: str) -> str:
    if not (evidence or "").strip():
        return reconcile(statement, first, second, allowance, beacon)
    if allowance.clock_left() < WALL_RESERVE_SEC * 2 or allowance.money_left() <= 0:
        beacon.fired("no room to decide; the first stands")
        return first
    seat = Seat(allowance, patient=False)
    report = ""
    try:
        root = os.getcwd()
        report = outline_report(statement, diff_outline(first, root), diff_outline(second, root))
    except Exception as error:
        log_message("[SECOND] no outline: %s" % type(error).__name__)
    messages = [{"role": "system", "content": PICK_BRIEF},
                {"role": "user", "content": "TASK\n\n%s\n\n%s%s\n\nFIRST\n\n%s\n\nSECOND\n\n%s" % (
                    statement, (report + "\n\n") if report else "", clip_output(evidence, PICK_EVIDENCE_CHARS, "checks"),
                    clip_output(first, PICK_MAX_PATCH_CHARS), clip_output(second, PICK_MAX_PATCH_CHARS))}]
    try:
        reply = seat.ask(messages, None)
    except Exception as error:
        beacon.fired("the pick could not be asked (%s); the first stands" % type(error).__name__)
        return first
    verdict = read_pick(str((reply or {}).get("content") or ""))
    if verdict == "SECOND":
        beacon.fired("picked the second derivation, with the checks shown")
        return second
    beacon.fired(("picked the first derivation" if verdict == "FIRST" else "no verdict read; the first stands")
                 + ", with the checks shown")
    return first

def agent_main(input: dict) -> str:
    """Run only in a clean task checkout; capture before restoring the baseline."""
    global _RUNTIME_DEADLINE
    statement = (input or {}).get("problem_statement")
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("problem_statement must be non-empty text")
    allowance = Allowance()
    # One deadline for all finalization operations, rather than a fresh timeout
    # for each diff/reset/apply/salvage step.
    _RUNTIME_DEADLINE = allowance.started + max(0.0, allowance.wall - 2.0)
    tree = None
    patch = ""
    try:
        code, root = run_git_command(["rev-parse", "--show-toplevel"], os.getcwd(), 5.0)
        if code:
            raise ValueError("working directory must be a task Git checkout")
        root = root.strip()
        code, status = run_git_command(["status", "--porcelain", "--untracked-files=no"], root, 5.0)
        if code or status.strip():
            raise ValueError("tracked task files must start clean; refusing to reset existing changes")
        tree = Tree(root)
        if not tree.base:
            raise ValueError("task checkout has no baseline commit")
        DERIVE_STATE.clear()
        DERIVE_STATE["cards"] = []
        _SCOPE_READS.clear()
        for key in RETRY_TALLY:
            RETRY_TALLY[key] = 0
        log_message("[RUN] build=staff!!peach_q3 budget=$%.3f clock=%.0fs"
            % (allowance.ceiling_usd, allowance.clock_left()))
        findings = FindingMap(root) if FINDING_MAP else None
        began = time.monotonic()
        patch = derive(statement, tree, root, allowance, findings, "first")
        why = second_pass_affordable(allowance, patch, time.monotonic() - began)
        if not why and tree.restored:
            # Preserve the first whole patch if the optional experiment fails.
            try:
                other = derive(statement, tree, root, allowance, findings, "second")
                if other.strip() and tree.restored:
                    patch = settle(statement, tree, allowance, Beacon("second"), patch, other)
            except Exception as error:
                log_message("[SECOND] first patch retained after %s" % type(error).__name__)
        if PATCH_ENVELOPE:
            patch = envelope_trim(patch)
        if tree.restored and patch.strip():
            checked = tree.applies(patch, 10.0)
            if checked is False:
                # Dropping arbitrary source files can break cross-file changes.
                # Never report a mechanically reduced patch as a repaired answer.
                log_message("[PATCH] rejected: whole patch does not apply")
                patch = ""
        elif not tree.restored:
            log_message("[PATCH] baseline restore unconfirmed; apply check unavailable")
        log_message("[RUN] %.1fs $%.5f %d calls patch=%dB"
            % (allowance.elapsed(), allowance.spent, allowance.calls, len(patch)))
        return patch
    finally:
        if tree is not None and not tree.restored:
            try:
                tree.restore(10.0)
            except Exception as error:
                log_message("[TREE] final cleanup failed: %s" % type(error).__name__)
        _RUNTIME_DEADLINE = None

