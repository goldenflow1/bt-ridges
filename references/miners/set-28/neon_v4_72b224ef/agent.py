from __future__ import annotations
import ast
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
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
FALLBACK_BASE_URL = "https://openrouter.ai/api/v1"
SYNTAX_CHECKS = {
    ".py": [sys.executable, "-m", "py_compile"],
    ".js": ["node", "--check"],
    ".mjs": ["node", "--check"],
    ".cjs": ["node", "--check"],
    ".ts": ["node", "--check"],
    ".rb": ["ruby", "-c"],
    ".php": ["php", "-l"],
    ".pl": ["perl", "-c"],
    ".lua": ["luac", "-p"],
    ".sh": ["bash", "-n"],
    ".bash": ["bash", "-n"],
    ".go": ["gofmt", "-e"],
    ".ex": ["elixir", "-e", "Code.string_to_quoted!(File.read!({path}))"],
    ".exs": ["elixir", "-e", "Code.string_to_quoted!(File.read!({path}))"],
}
SYNTAX_MARKERS = {
    ".ex": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
    ".exs": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
}
DRIVER_MODEL = os.getenv("RIDGES_AGENT_MODEL", "openai/gpt-6-luna")
RELIEF_MODEL = os.getenv("RIDGES_RELIEF_MODEL", "")
PLAN_MODEL = os.getenv("RIDGES_PLAN_MODEL", "openai/gpt-6-luna")
SEAT_CACHE_TERMS = {
    "xiaomi/mimo-v2.5-pro": (0.0050e-6, 262_144),
    "xiaomi/mimo-v2.5": (0.0050e-6, 262_144),
    "minimax/minimax-m2.5": (0.0500e-6, 204_800),
    "minimax/minimax-m3": (0.0750e-6, 204_800),
    "deepseek/deepseek-v4-pro": (0.0036e-6, 1_048_576),
    "deepseek/deepseek-v4-pro-0813": (0.0220e-6, 1_048_576),
    "openai/gpt-6-luna": (0.0100e-6, 1_050_000),
    "openai/gpt-5.6-luna": (0.0200e-6, 400_000),
    "~openai/gpt-luna-latest": (0.0100e-6, 1_050_000),
    "qwen/qwen3.8-2.4t-a95b": (0.2500e-6, 1_000_000),
    "@preset/qwen38-24t-lowthink": (0.2500e-6, 1_000_000),
    "openai/gpt-5.6-terra": (0.2000e-6, 400_000),
    "google/gemini-3.7-flash": (0.0375e-6, 1_048_576),
    "deepseek/deepseek-v4-flash-0731": (0.0280e-6, 1_048_576),
    "tencent/hy3": (0.0330e-6, 262_144),
}
UNKNOWN_CACHE_TERMS = (0.1000e-6, 131_072)
MODEL_PRICING = {
    "qwen/qwen3.8-2.4t-a95b": (2.000e-6, 6.000e-6),
    "@preset/qwen38-24t-lowthink": (2.000e-6, 6.000e-6),
    "xiaomi/mimo-v2.5-pro": (0.600e-6, 1.201e-6),
    "xiaomi/mimo-v2.5": (0.140e-6, 0.280e-6),
    "minimax/minimax-m2.5": (0.150e-6, 0.900e-6),
    "minimax/minimax-m3": (0.375e-6, 1.500e-6),
    "deepseek/deepseek-v4-pro-0813": (0.660e-6, 1.980e-6),
    "openai/gpt-6-luna": (0.100e-6, 0.500e-6),
    "openai/gpt-5.6-luna": (0.200e-6, 1.200e-6),
    "~openai/gpt-luna-latest": (0.100e-6, 0.500e-6),
    "openai/gpt-5.6-terra": (2.000e-6, 12.000e-6),
    "google/gemini-3.7-flash": (0.375e-6, 1.875e-6),
    "deepseek/deepseek-v4-flash-0731": (0.440e-6, 1.320e-6),
    "tencent/hy3": (0.132e-6, 0.528e-6),
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
# What the writing may not take, whatever it is doing: enough to get the diff
# out of the tree, put the tree back, and see whether the answer applies.
TAIL_RESERVE_SEC = 90.0
# The last word on time.  However the run is going, this long before the
# run's outer time limit the tree is handed back as it stands: a run stopped from
# outside hands back nothing at all.  That outer clock started before this
# process did, so the margin covers that as well as reading the diff.
HARD_STOP_MARGIN_SEC = 120.0
HARD_STOP_REPEAT_SEC = 3.0
HARD_STOP_FLOOR_SEC = 30.0
# And how long one read of a file out of the repository may take.  Asked once
# per file a change touched, from the hand-in, so a generous number here is
# multiplied by however many files there were and spent at the worst moment.
ORIGINAL_READ_SEC = 10.0
TURN_CEILING = 150
FIRST_EDIT_DEADLINE_TURN = 5
FIRST_EDIT_TIME_REMAINING_SHARE = 0.80
FIRST_EDIT_WINDOW_SHARE = 0.35
EDIT_GATE_FLOOR_SHARE = 0.45
EDIT_GATE_FLOOR_REPLIES = 6
EDIT_GATE_FLOOR_MIN_REPLIES = 3
EDIT_GATE_FLOOR_CEILING_SHARE = 0.60
READ_ONLY_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline")
PLAN_NOTE_MIN_WINDOW_SEC = 600.0
BLANK_FINISH_MIN_WALL_SEC = 90.0
PLAN_READ_BUDGET = 150_000
PLAN_TURN_CAP = 40
PLAN_SPEND_SHARE = 0.75
PLAN_NOTE_CHARS = 4_000
WRAPUP_TURN = TURN_CEILING // 5
# The wrap-up is said when this share of the run's window is left, whatever
# turn it is: a model that takes many small steps reaches any fixed turn early,
# and one that takes few large ones may never reach it in time.
WRAPUP_CLOCK_SHARE = 0.30
WRAPUP_TURN_SHARE = 0.8
# What an edit shows of itself: the lines it wrote and a few either side.
EDIT_SHOWN_CONTEXT = 3
EDIT_SHOWN_CHARS = 1_500
NEAREST_MAX_LINES = 30
EDIT_PRESSES_MAX = 3
BLANK_REPLY_CEILING = 3
REPEAT_READ_CEILING = 2
REPLY_TOKEN_CEILING = 16000
REQUEST_ATTEMPTS = 64
INFLIGHT_RETRIES = 6
INFLIGHT_BACKOFF_SECONDS = (8.0, 16.0, 30.0, 45.0, 60.0, 60.0)
SEAT_REFUSED_WAIT_SEC = 20.0
# How long one request may wait.  Drawn from how long an answer takes when one
# is coming: a seat told to think at length on a long transcript can be minutes
# about it, and cutting that off does not make the answer arrive sooner -- it
# throws away the one that was coming.  The sweep's own share of the clock is
# the real bound; this is only the wait for one request.
SEAT_CALL_TIMEOUT_SEC = 240.0
EMPTY_TIMEOUT_ROSTER_RESETS = 1
EMPTY_TIMEOUT_RESET_MIN_WALL_SEC = 180.0
CALL_CLOCK_SHARE = 0.34
SEAT_RETRY_DECAY = 0.5
SEAT_RETRY_FLOOR_SEC = 20.0
# The longest to wait between two sweeps.  Without a ceiling the wait doubles
# without bound and the seat spends its whole share asleep: eight sweeps in, a
# doubling nap is already longer than the run, so a high sweep count buys
# longer silences rather than more tries.  The ceiling is what makes the count
# mean what it says.
SEAT_RETRY_NAP_CEILING_SEC = 15.0
SHELL_BUDGET_CEILING_SEC = 180.0
BACKGROUND_POLL_WAIT_SEC = 20.0
SQL_OUTPUT_CAP = 10_000
PROBE_BUDGET_SEC = 25.0
SQL_STATEMENT_TIMEOUT_SEC = 120
READ_OUTPUT_CAP = 24_000
DECLARED_SCOPE_CHARS = 16_000
SEARCH_HEAD_LIMIT = 250
SHELL_OUTPUT_CAP = 8_000
SEARCH_OUTPUT_CAP = 8_000
TOOL_OUTPUT_READ_CAP = 128_000
TEMPERATURE = 0.0
HIGH_REASONING = (os.getenv("RIDGES_HIGH_REASONING") or "1").strip().lower() not in (
    "0", "no", "off", "false", "",
)
# max on gpt-5.6-luna: the writer's own depth matters more than a second
# reading at the end, and more than the time and money it saves to think less.
REASONING_EFFORT = (os.getenv("RIDGES_REASONING_EFFORT") or "xhigh").strip().lower()
REASONING_CONFIG = {"effort": REASONING_EFFORT, "exclude": True}
# The reader-ahead's reasoning.  Its calls are bounded at a minute, which the
# deepest settings outlast; gpt-5.6-luna at xhigh never did.
SCOUT_EFFORT = (os.getenv("RIDGES_SCOUT_REASONING") or "medium").strip().lower()
# A writer reply that outlasts its share of the clock after an edit is asked
# once more at this effort, when this much of the run is left.
EASED_EFFORT = "medium"
EASED_RETRY_MIN_SEC = 90.0

PROGRAM_SEARCH_DIRS = (
    "/opt/venv/bin", "/usr/local/bin", "/usr/local/venv/bin", "/opt/conda/bin",
    # A language toolchain is routinely unpacked into its own prefix and put on
    # PATH only by a login shell's profile. Tools here run `bash -c`, which reads
    # no profile, so the compiler is present and invisible -- and every check the
    # task names is then quietly refused for want of its own binary.
    "/usr/local/go/bin", "/usr/lib/go/bin", "/opt/go/bin", "/root/go/bin",
    "/usr/local/node/bin", "/opt/node/bin",
    "/usr/local/cargo/bin", "/root/.cargo/bin",
    "/usr/local/openjdk/bin", "/opt/java/openjdk/bin",
    "/usr/share/maven/bin", "/opt/maven/bin", "/opt/gradle/bin", "/usr/local/sbt/bin",
    "/usr/share/dotnet", "/usr/local/dotnet", "/root/.dotnet/tools",
    "/usr/local/bundle/bin", "/root/.rbenv/shims", "/usr/local/rbenv/shims",
    "/root/.local/share/coursier/bin", "/root/.mix/escripts", "/usr/local/lib/elixir/bin",
)


def widen_path() -> list[str]:
    """Put the toolchains that are installed but unlisted on the path.

    A language toolchain is routinely unpacked into its own prefix and put on
    the path only by a login shell's profile.  Everything here runs `bash -c`,
    which reads no profile, so the compiler is present and invisible.  A
    command the task names is resolved against these directories one at a
    time, so those still run; anything the run writes for itself -- a script
    that renders the statement, a test beside the code -- calls the tool by
    its own name and is told it does not exist.  Appended rather than put in
    front: a project that ships its own interpreter keeps it.
    """
    current = os.environ.get("PATH", "")
    known = set(current.split(os.pathsep))
    add = [d for d in PROGRAM_SEARCH_DIRS if d not in known and os.path.isdir(d)]
    if add:
        os.environ["PATH"] = os.pathsep.join(([current] if current else []) + add)
        say("[RUN] toolchains found off the path: %s" % ", ".join(add))
    return add

def one_line(value: object) -> str:
    return " ".join(str(value or "").split())

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

def reasoning_tokens(usage: dict) -> int:
    details = (usage or {}).get("completion_tokens_details")
    value = details.get("reasoning_tokens") if isinstance(details, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -1
    return int(value)

def flag(name: str, default: str = "1") -> bool:
    return (os.getenv(name) or default).strip().lower() not in ("0", "no", "off", "false", "")

PARALLEL_TOOLS = flag("RIDGES_PARALLEL_TOOLS")
REPLACE_ALL = flag("RIDGES_REPLACE_ALL")
ASYNC_SHELL = flag("RIDGES_ASYNC_SHELL")
PRELOCATE = flag("RIDGES_PRELOCATE")
SWEEP_WORKFLOW = flag("RIDGES_SWEEP_WORKFLOW")
TRANSCRIPT_CAP = flag("RIDGES_TRANSCRIPT_CAP")
TOOL_CALL_ID_NORMALISATION = flag("RIDGES_TOOL_CALL_ID_NORMALISATION")
INVARIANT_BRIEF = flag("RIDGES_INVARIANT_BRIEF")
SUBMISSION_WARDEN = flag("RIDGES_SUBMISSION_WARDEN")
WARDEN_ASK = flag("RIDGES_WARDEN_ASK")
LEDGER_READBACK = flag("RIDGES_LEDGER_READBACK", "0")
MOVE_VERBATIM = flag("RIDGES_MOVE_VERBATIM")
FINISH_CONFORM = flag("RIDGES_FINISH_CONFORM", "0")
PLAN_SEAT = flag("RIDGES_PLAN_SEAT", "0")
EDIT_GATE = flag("RIDGES_EDIT_GATE")
SUITE_SCOPE = flag("RIDGES_SUITE_SCOPE")
SUITE_IMPORTLIB = flag("RIDGES_SUITE_IMPORTLIB", "0")
SUITE_SHIM = flag("RIDGES_SUITE_SHIM")
NETWORK_FENCE = flag("RIDGES_NETWORK_FENCE")
SEARCH_LIMIT = flag("RIDGES_SEARCH_LIMIT", "0")
OUTLINE = flag("RIDGES_OUTLINE", "0")
FINDING_MAP = flag("RIDGES_FINDING_MAP", "0")
ELIXIR = flag("RIDGES_ELIXIR")
SCOUT_SEAT = flag("RIDGES_SCOUT_SEAT")
# A second reader at the hand-in: another model, from a clean start, with only
# the task and the change in front of it.
VERIFY = flag("RIDGES_VERIFY", "0")
VERIFY_MODEL = os.getenv("RIDGES_VERIFY_MODEL", "openai/gpt-6-luna")
VERIFY_EFFORT = (os.getenv("RIDGES_VERIFY_REASONING") or "medium").strip().lower()
VERIFY_MIN_LEFT_SEC = 420.0
VERIFY_MIN_MONEY_USD = 0.05
VERIFY_MAX_USD = float(os.getenv("RIDGES_VERIFY_MAX_USD") or 0.01)
VERIFY_TURN_CAP = 12
VERIFY_CLOCK_SEC = float(os.getenv("RIDGES_VERIFY_CLOCK_SEC") or 240.0)
# One reviewer call; the deepest reasoning can take minutes over a single reply.
VERIFY_CALL_SEC = float(os.getenv("RIDGES_VERIFY_CALL_SEC") or 60.0)
VERIFY_LINKS_MAX = 40
VERIFY_DIFF_CHARS = 24_000
VERIFY_PROBLEMS_MAX = 5
CHILD_CAP = flag("RIDGES_CHILD_CAP")
SCOUT_READ_BUDGET = 60_000
SCOUT_TURN_CAP = 10
SCOUT_CARD_CHARS = 6_000
SCOUT_MAX_USD = 0.02
SCOUT_MIN_MONEY_USD = 0.10
SCOUT_MIN_CLOCK_SEC = 500.0
SCOUT_STATEMENT_CHARS = 18_000
SCOUT_QUOTE_CHARS = (8, 1200)
CHILD_MEMORY_BYTES = 3 * 1024 * 1024 * 1024
EXECUTED = flag("RIDGES_EXECUTED")
MEMBOUND = flag("RIDGES_MEMBOUND")
SCOPE = flag("RIDGES_SCOPE")
ROLLBACK_SQL = flag("RIDGES_ROLLBACK_SQL")
EXECUTED_MIN_LEFT_SEC = 150.0
EXECUTED_TAIL_LINES = 40
EXECUTED_TAIL_CHARS = 4000
EXECUTED_KEEP = 12
MEMBOUND_SHARE = 0.70
MEMBOUND_FALLBACK_MB = 4096.0
MEMBOUND_MAX_LIMIT_MB = 65536.0
MEMBOUND_SAMPLE_SEC = 1.0
MEMBOUND_MIN_JOB_MB = 64.0
CGROUP_LIMIT_FILES = (("/sys/fs/cgroup/memory.max", "cgroup2"),
                      ("/sys/fs/cgroup/memory/memory.limit_in_bytes", "cgroup1"))
CGROUP_USAGE_FILES = (("/sys/fs/cgroup/memory.current", "cgroup2"),
                      ("/sys/fs/cgroup/memory/memory.usage_in_bytes", "cgroup1"))
PROCESS_TABLE = "/proc"
SCOPE_MAX_PATHS = 40
SCOPE_MAX_BYTES = 4 * 1024 * 1024
SCOPE_MIN_LEFT_SEC = 20.0

def num_env(name: str, default: float) -> float:
    try:
        value = float((os.getenv(name) or "").strip())
    except (TypeError, ValueError):
        return default
    return value if value == value and value not in (float("inf"), float("-inf")) else default

def say(message: str) -> None:
    try:
        print(message, flush=True)
    except (OSError, ValueError):
        pass

class Beacon:
    def __init__(self, slug: str) -> None:
        self.slug = slug.upper()
        self.calls = 0
        self.usd = 0.0

    def reached(self, step: int, spent: float, clock: float) -> None:
        say("[%s] reached step=%d spent=$%.4f clock=%.0fs" % (self.slug, step, spent, clock))

    def skipped(self, reason: str) -> None:
        say("[%s] skipped: %s" % (self.slug, reason))

    def fired(self, detail: str) -> None:
        say("[%s] fired: %s" % (self.slug, detail[:400]))

    def artefact(self, when: str, blob: str) -> str:
        import hashlib
        digest = hashlib.sha256((blob or "").encode("utf-8", "replace")).hexdigest()[:8]
        say("[%s] %s %s %dB" % (self.slug, when, digest, len(blob or "")))
        return digest

    def outcome(self, before_digest: str, after: str) -> None:
        import hashlib
        digest = hashlib.sha256((after or "").encode("utf-8", "replace")).hexdigest()[:8]
        changed = "yes" if digest != before_digest else "no"
        say("[%s] after %s %dB changed=%s" % (self.slug, digest, len(after or ""), changed))

    def bill(self) -> None:
        say("[%s] cost calls=%d usd=%.4f" % (self.slug, self.calls, self.usd))

class Spent(Exception):
    pass

class Allowance:
    def __init__(self) -> None:
        self.started = time.time()
        wall = num_env("AGENT_TIMEOUT", DEFAULT_WALL_SEC)
        self.ceiling_usd = num_env("RIDGES_MAX_COST_USD", DEFAULT_COST_LIMIT_USD)
        self.soft_usd = self.ceiling_usd * COST_SHARE
        self.run_window_sec = max(30.0, wall * WALL_SHARE - WALL_RESERVE_SEC)
        self.deadline = self.started + self.run_window_sec
        # The run's own end, kept apart from the end a phase works to.
        self.final_deadline = self.deadline
        self.suite_baseline_sec = min(
            SUITE_BASELINE_SEC, max(60.0, self.run_window_sec / 3.0)
        )
        self.suite_settle_sec = min(
            SUITE_SETTLE_SEC, max(20.0, self.run_window_sec * 0.15)
        )
        self.warden_release_sec = min(
            WARDEN_RELEASE_SEC, max(60.0, self.run_window_sec * 0.27)
        )
        post_reply_floor = (self.warden_release_sec + 30.0) / (1.0 - CALL_CLOCK_SHARE)
        self.conform_min_wall_sec = min(
            CONFORM_MIN_WALL_SEC,
            max(140.0, self.run_window_sec * 0.40, post_reply_floor),
        )
        self.rung_min_wall_sec = self.warden_release_sec + self.suite_settle_sec
        self.standin_min_wall_sec = self.conform_min_wall_sec + self.suite_settle_sec
        self.spent = 0.0
        self.calls = 0
        self.edits = 0
        self.tests_run = 0

    def hold_back(self, seconds: float) -> float:
        """Bring this phase's end forward, and say what it was.

        A phase bounded only by the run's own end takes all of it when it
        needs to, which is right where nothing follows and wrong where
        something does.
        """
        was = self.deadline
        if seconds > 0:
            self.deadline = min(was, self.final_deadline - seconds)
        return was

    def clock_left(self) -> float:
        return self.deadline - time.time()

    def money_left(self) -> float:
        return self.soft_usd - self.spent

    def elapsed(self) -> float:
        return time.time() - self.started

    def halt_reason(self) -> str:
        if self.clock_left() <= 0:
            return "wall clock"
        if self.money_left() <= 0:
            return "budget"
        return ""

    def charge(self, model: str, usage: dict) -> float:
        self.calls += 1
        quoted = usage.get("cost")
        if isinstance(quoted, (int, float)) and quoted >= 0:
            self.spent += float(quoted)
            return float(quoted)
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        details = usage.get("prompt_tokens_details") or {}
        cached = int(details.get("cached_tokens") or 0) if isinstance(details, dict) else 0
        fresh = max(0, prompt - cached)
        in_price, out_price = MODEL_PRICING.get(model, UNKNOWN_TOKEN_PRICE)
        cache_price = SEAT_CACHE_TERMS.get(model, UNKNOWN_CACHE_TERMS)[0]
        cost = fresh * in_price + cached * cache_price + completion * out_price
        self.spent += cost
        return cost

def recorded_calls(calls: list) -> list:
    kept = []
    for call in calls:
        function = dict(call.get("function") or {})
        written = function.get("arguments")
        try:
            if not isinstance(written, str) or not written.strip():
                raise ValueError("nothing was written")
            if not isinstance(json.loads(written), dict):
                raise ValueError("not an object")
        except Exception:
            function["arguments"] = "{}"
        kept.append({"id": call.get("id"), "type": "function", "function": function})
    return kept

def normalise_tool_call_ids(calls: list, turn: int) -> int:
    if not TOOL_CALL_ID_NORMALISATION:
        return 0
    changed = 0
    for index, call in enumerate(calls, 1):
        if not isinstance(call, dict):
            continue
        stable = f"call_g_t{turn}_i{index}"
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

def foreign(text: str) -> str:
    body = "" if text is None else str(text)
    return "%dB" % len(body.encode("utf-8", "replace")) if body else "empty"

class SeatRefused(Exception):
    pass

class SeatTimedOut(SeatRefused):
    pass

def read_within(response, deadline: float) -> bytes:
    """A reply's whole body, or TimeoutError once `deadline` (monotonic) passes.

    A socket's timeout counts only silence.  An endpoint that sends a few bytes
    of whitespace every few seconds while the model works is never silent, so a
    call bounded by that alone lasts as long as the far end likes -- and one
    such call can carry the run past its own end, where nothing is handed in.
    """
    read = getattr(response, "read1", None)
    if read is None:
        return response.read()
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    parts: list[bytes] = []
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("no whole reply inside the time given")
        if sock is not None:
            try:
                sock.settimeout(max(0.5, left))
            except OSError:
                pass
        try:
            chunk = read(65536)
        except socket.timeout as error:
            raise TimeoutError(str(error) or "timed out") from error
        if not chunk:
            return b"".join(parts)
        parts.append(chunk)

def base_urls() -> list[str]:
    out = []
    for candidate in (
        (os.getenv("OPENROUTER_BASE_URL") or "").strip().rstrip("/"),
        FALLBACK_BASE_URL,
    ):
        if candidate and candidate not in out:
            out.append(candidate)
    relay = (os.getenv("SANDBOX_PROXY_URL") or "").strip().rstrip("/")
    if relay:
        for suffix in ("/api/v1", "/v1"):
            if relay + suffix not in out:
                out.append(relay + suffix)
    return out

class Seat:
    roster: list = []
    patient = True

    def __init__(self, allowance: Allowance, models: list | None = None,
                 patient: bool = True, effort: str = "") -> None:
        self.allowance = allowance
        self.patient = patient
        # The reasoning this seat asks for; "" is the run's own setting.
        self.effort = effort
        self.choice = "auto"
        self.eased = False
        # How long one call may take, when this seat needs other than the default.
        self.call_ceiling = 0.0
        if models:
            self.models = list(models)
        else:
            self.models = [DRIVER_MODEL]
            if RELIEF_MODEL and RELIEF_MODEL != DRIVER_MODEL:
                self.models.append(RELIEF_MODEL)
        self.roster = list(self.models)
        self.original_models = list(self.models)
        self.empty_timeout_roster_resets = 0
        self.timeouts: dict = {}
        self.bases = base_urls()
        self.key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("RIDGES_OPENROUTER_API_KEY")
            or os.getenv("AI_PROXY_KEY")
            or ""
        )

    def current(self) -> str:
        return self.models[0]

    def retire(self, model: str, timeout_recovery: bool = False) -> bool:
        if self.allowance.edits or not timeout_recovery:
            return False
        if model in self.models and len(self.models) > 1:
            self.models.remove(model)
            if model in self.roster:
                self.roster.remove(model)
            say("[SEAT] retired %s, now on %s" % (model, self.models[0]))
            return True
        return False

    def ask(self, messages: list[dict], tools: list[dict] | None,
            tool_choice: str = "auto") -> dict:
        self.choice = tool_choice
        budget = self._budget()
        inflight_state = {"retries": 0}
        while True:
            model = self.current()
            try:
                return self._attempt(model, messages, tools, budget,
                                     inflight_state=inflight_state)
            except SeatRefused as refusal:
                say("[SEAT] %s refused: %s" % (model, str(refusal)[:200]))
                if self.allowance.edits:
                    self.models = [model]
                    self.roster = [model]
                    if isinstance(refusal, SeatTimedOut):
                        # A reply that thinks past its share of the clock is
                        # asked once more to think less, rather than ending a
                        # run that has work in the tree and time left.
                        if (not self.eased and HIGH_REASONING
                                and self.allowance.clock_left() > EASED_RETRY_MIN_SEC):
                            self.eased = True
                            self.effort = EASED_EFFORT
                            budget = self._budget()
                            say("[SEAT] %s went quiet after an edit; asking again at %s reasoning"
                                % (model, EASED_EFFORT))
                            continue
                        raise Spent(
                            "writer went quiet after an edit; preserving the tree"
                        )
                if (isinstance(refusal, SeatTimedOut)
                        and self.timeouts.get(model, 0) >= 2
                        and self.retire(model, timeout_recovery=True)):
                    budget = self._budget()
                    say("[SEAT] fresh request share for %s before first edit"
                        % self.current())
                    continue
                if len(self.models) > 1 and isinstance(refusal, SeatTimedOut):
                    self.models.remove(model)
                    say("[SEAT] benched %s, now on %s" % (model, self.models[0]))
                    if isinstance(refusal, SeatTimedOut):
                        budget = self._budget()
                        say("[SEAT] fresh request share for %s before first edit"
                            % self.current())
                    continue
                if isinstance(refusal, SeatTimedOut):
                    if (
                        self.allowance.edits == 0
                        and self.empty_timeout_roster_resets
                        < EMPTY_TIMEOUT_ROSTER_RESETS
                        and len(self.original_models) > 1
                        and self.allowance.clock_left()
                        >= EMPTY_TIMEOUT_RESET_MIN_WALL_SEC
                    ):
                        self.empty_timeout_roster_resets += 1
                        self.models = list(self.original_models)
                        self.roster = list(self.original_models)
                        self.timeouts = {}
                        budget = self._budget()
                        say(
                            "[SEAT] every provider timed out before an edit; "
                            "restored the roster (%d/%d)"
                            % (
                                self.empty_timeout_roster_resets,
                                EMPTY_TIMEOUT_ROSTER_RESETS,
                            )
                        )
                        continue
                    raise Spent("every seat went quiet: %s" % refusal)
                if not self.patient:
                    raise
                wait = min(SEAT_REFUSED_WAIT_SEC,
                           self.allowance.clock_left() - WALL_RESERVE_SEC - 60.0)
                if wait <= 0:
                    raise Spent("no seat will serve this run")
                say("[SEAT] every seat refused; asking again in %.0fs" % wait)
                time.sleep(wait)
                self.models = list(self.roster)
                budget = self._budget()

    def _budget(self):
        share = self.allowance.clock_left() * CALL_CLOCK_SHARE
        return share, time.monotonic(), self.allowance.clock_left()

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
        if HIGH_REASONING:
            body["reasoning"] = dict(REASONING_CONFIG)
            if self.effort:
                body["reasoning"]["effort"] = self.effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = self.choice
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        backoff = 3.0
        sweep: list[str] = []
        refusal = ""
        refused_sweeps = 0
        timed_out = 0
        attempts = REQUEST_ATTEMPTS if self.patient else 1
        ceiling = self.call_ceiling or (SEAT_CALL_TIMEOUT_SEC if self.patient else 60.0)
        share, began, started_with = budget if budget else self._budget()

        def spent_share() -> float:
            return max(time.monotonic() - began,
                       started_with - self.allowance.clock_left())
        for attempt in range(attempts):
            if self.allowance.clock_left() <= 5:
                raise Spent("clock ran out mid-request")
            asked = 0
            walled = 0
            quiet = 0
            sweep = []
            granted = max(SEAT_RETRY_FLOOR_SEC,
                          ceiling * (SEAT_RETRY_DECAY ** timed_out))
            for base in self.bases:
                room = min(share - spent_share(),
                           self.allowance.clock_left() - 10)
                if room < SEAT_RETRY_FLOOR_SEC:
                    break
                asked += 1
                try:
                    request = urllib.request.Request(
                        base + "/chat/completions", data=payload, headers=headers
                    )
                    until = time.monotonic() + min(granted, room)
                    with urllib.request.urlopen(request, timeout=min(granted, room)) as response:
                        parsed = json.loads(read_within(response, until).decode("utf-8", "replace"))
                    return self._book(model, parsed)
                except urllib.error.HTTPError as error:
                    detail = error.read()[:400].decode("utf-8", "replace")
                    sweep.append("%s %s" % (error.code, foreign(detail)))
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
                        say("[SEAT] in-flight allowance busy; retry %d/%d in %.1fs"
                            % (inflight_retry + 1, INFLIGHT_RETRIES, delay))
                        time.sleep(delay)
                        return self._attempt(model, messages, tools, None,
                                             inflight_state)
                    if error.code == 403:
                        walled += 1
                        continue
                    if error.code in (400, 402, 413):
                        raise Spent("endpoint refused the request: " + sweep[-1])
                    if error.code == 429 and ("budget" in detail.lower() or "cost" in detail.lower()):
                        raise Spent("allowance exhausted upstream")
                except Exception as error:
                    reason = getattr(error, "reason", None)
                    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
                        timed_out += 1
                        quiet += 1
                        sweep.append("timed out after %.0fs" % min(granted, room))
                    else:
                        sweep.append("%s: %s" % (type(error).__name__, foreign(error)))
            if asked and walled and not quiet:
                refused_sweeps += 1
                refusal = " | ".join(sweep)
                if refused_sweeps >= 2:
                    raise SeatRefused(refusal)
            if attempt + 1 >= attempts or spent_share() >= share:
                break
            nap = min(backoff, max(0.0, self.allowance.clock_left() - 5),
                      max(0.0, share - spent_share()))
            if nap <= 0:
                break
            time.sleep(nap)
            backoff = min(backoff * 2, SEAT_RETRY_NAP_CEILING_SEC)
        said = " | ".join(sweep) or "no base was asked"
        if timed_out:
            self.timeouts[model] = self.timeouts.get(model, 0) + 1
            raise SeatTimedOut("%d timeout(s) in %d attempt(s): %s"
                               % (timed_out, attempt + 1, said))
        raise Spent("no reply after %d attempts: %s" % (attempt + 1, said))

    def _book(self, model: str, parsed: dict) -> dict:
        choices = parsed.get("choices") or []
        if not choices:
            raise Spent("reply carried no choices")
        message = choices[0].get("message") or {}
        usage = parsed.get("usage") or {}
        cost = self.allowance.charge(model, usage)
        served = one_line(parsed.get("provider") or parsed.get("served_by"))
        answered = one_line(parsed.get("model"))
        aside = ""
        if served:
            aside += " via=%s" % served[:40]
        if answered and answered != model:
            aside += " answered=%s" % answered[:60]
        thought = reasoning_tokens(usage)
        if thought >= 0:
            aside += " thought=%d" % thought
        say(
            "[SEAT] %s call=%d $%.4f total=$%.4f left=%.0fs said=%s%s"
            % (model, self.allowance.calls, cost, self.allowance.spent,
               self.allowance.clock_left(), reply_fingerprint(message), aside)
        )
        finish = choices[0].get("finish_reason") or ""
        message["_finish"] = finish
        if finish not in ("stop", "tool_calls", ""):
            named = finish if finish in FINISH_REASONS else "other"
            say("[SEAT] %s reply ended on %s after %d token(s)"
                % (model, named, int(usage.get("completion_tokens") or 0)))
        return message

GIT_TIMED_OUT = 124

def git(args: list[str], cwd: str, timeout: float = 60.0) -> tuple[int, str]:
    try:
        done = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=max(2.0, timeout),
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return GIT_TIMED_OUT, "git timed out"
    except Exception as error:
        return 1, "%s: %s" % (type(error).__name__, error)
    return done.returncode, (done.stdout or "") + (done.stderr or "")

def run_piped(
    command: list[str],
    cwd: str,
    timeout: float = 60,
    stdin_text: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(1.0, timeout),
            check=False,
            input=None if stdin_text is None else stdin_text.encode("utf-8"),
            env=env,
            preexec_fn=child_limits_hook(),
        )
        return completed.returncode, completed.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as expired:
        partial = (expired.stdout or b"").decode("utf-8", errors="replace")
        return 124, "%s\n[timed out after %.0fs]" % (partial, timeout)
    except FileNotFoundError as missing:
        return 127, "command not found: %s" % missing
    except Exception as error:
        return 1, "%s: %s" % (type(error).__name__, error)

class Tree:
    def __init__(self, root: str) -> None:
        self.root = root
        code, out = git(["rev-parse", "HEAD"], root, 30)
        self.base = out.strip() if code == 0 else ""
        self.untracked_at_start = self._untracked()

    def _untracked(self) -> set:
        code, out = git(["ls-files", "--others", "--exclude-standard", "-z"], self.root, 30)
        return {p for p in out.split("\0") if p} if code == 0 else set()

    def absolute(self, path: str) -> str:
        root = os.path.normpath(self.root)
        joined = os.path.normpath(os.path.join(root, path))
        if joined != root and not joined.startswith(root + os.sep):
            raise ToolFault("path escapes the repository: %s" % path)
        return joined

    def read(self, path: str) -> str:
        full = self.absolute(path)
        if not os.path.isfile(full):
            raise ToolFault("no such file: %s" % path)
        with open(full, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()

    def write(self, path: str, text: str) -> None:
        full = self.absolute(path)
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def diff(self, budget: float = 60.0) -> str:
        git(["add", "-A", "-N"], self.root, budget)
        args = ["diff", "--binary", "--no-color"] + ([self.base] if self.base else [])
        code, out = git(args, self.root, budget)
        if code != 0:
            say("[TREE] diff failed (%s), retrying once: %s" % (code, out.strip()[:200]))
            code, out = git(args, self.root, max(budget, 90.0))
            if code != 0:
                say("[TREE] diff failed again: %s" % out.strip()[:200])
                return ""
        return out

    def has_changes(self, budget: float = 10.0) -> bool | None:
        code, out = git(["add", "-A", "-N"], self.root, budget)
        if code != 0:
            say("[TREE] change probe could not stage intent: %s" % out.strip()[:200])
            return None
        args = ["diff", "--quiet"] + ([self.base] if self.base else [])
        code, out = git(args, self.root, budget)
        if code == 0:
            return False
        if code == 1:
            return True
        say("[TREE] change probe failed: %s" % out.strip()[:200])
        return None

    def applies(self, patch: str, budget: float = 30.0) -> bool | None:
        if not patch.strip():
            say("[PATCH] empty: the run finished without changing a line")
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="agent-patch-", suffix=".diff")
        except OSError as error:
            say("[PATCH] could not be written out for checking: %s" % error)
            return None
        try:
            with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(patch)
            code, out = git(["apply", "--check", path], self.root, budget)
        except OSError as error:
            say("[PATCH] could not be filled for checking: %s" % error)
            return None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if code == 0:
            say("[PATCH] applies cleanly")
            return True
        if code == GIT_TIMED_OUT:
            say("[PATCH] could not be checked in time")
            return None
        say("[PATCH] will not apply: %s" % out.strip()[:200])
        return False

    def salvage(self, patch: str, budget: float = 45.0) -> str:
        deadline = time.time() + max(1.0, budget)
        parts = split_by_file(patch)
        if len(parts) < 2:
            say("[PATCH] nothing to salvage: %d section(s)" % len(parts))
            return ""
        kept, dropped, unread = [], 0, 0
        for part in parts:
            left = deadline - time.time()
            answer = self.applies_quietly(part, left) if left > 0 else None
            if answer is None:
                unread = len(parts) - len(kept) - dropped
                say("[PATCH] salvage left %d section(s) unread" % unread)
                break
            if answer:
                kept.append(part)
            else:
                dropped += 1
        if not kept:
            say("[PATCH] salvage kept nothing of %d section(s)" % len(parts))
            return ""
        joined = "".join(kept)
        whole = self.applies_quietly(joined, max(1.0, deadline - time.time()))
        if whole is None:
            say("[PATCH] salvage could not re-check its %d section(s)"
                % len(kept))
            return ""
        if not whole:
            say("[PATCH] salvage kept %d section(s) that will not apply together"
                % len(kept))
            return ""
        say("[PATCH] salvaged %d of %d section(s), dropped %d, unread %d"
            % (len(kept), len(parts), dropped, unread))
        return joined

    def applies_quietly(self, patch: str, budget: float) -> bool | None:
        if not patch.strip():
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="agent-part-", suffix=".diff")
        except OSError:
            return None
        try:
            with os.fdopen(handle, "w", encoding="utf-8",
                           errors="surrogateescape") as fh:
                fh.write(patch)
            code, _ = git(["apply", "--check", path], self.root, budget)
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

    def restore(self, budget: float = 60.0) -> None:
        if self.base:
            code, out = git(["reset", "--hard", self.base], self.root, budget)
        else:
            code, out = git(["checkout", "--", "."], self.root, budget)
        if code != 0:
            say("[TREE] restore said: %s" % out.strip()[:200])
        added = self._untracked() - self.untracked_at_start
        for path in sorted(added, key=len, reverse=True):
            try:
                full = self.absolute(path)
            except ToolFault:
                continue
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True)
                else:
                    os.remove(full)
            except OSError as error:
                say("[TREE] could not remove %s: %s" % (path, error))
        say("[TREE] restored to %s, removed %d path(s) the run created" % (self.base[:8] or "?", len(added)))

class ToolFault(Exception):
    pass

CLIP_NOTE = "\n... [%d characters of %s elided] ...\n"

def bounded_output_file(path: str, cap: int, label: str = "output") -> str:
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        if size <= cap:
            return handle.read().decode("utf-8", "replace")
        half = max(1, cap // 2)
        head = handle.read(half)
        handle.seek(max(0, size - half))
        tail = handle.read(half)
    note = CLIP_NOTE % (max(0, size - len(head) - len(tail)), label)
    room = max(0, cap - len(note.encode("utf-8")))
    left = room // 2
    right = room - left
    data = head[:left] + note.encode("utf-8") + (tail[-right:] if right else b"")
    return data.decode("utf-8", "replace")

def clip(text: str, cap: int, label: str = "output") -> str:
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
    say("[SHELL] %.1fs %dc :: %s :: %s"
        % (time.time() - job.started, len(out or ""),
           " ".join(job.command.split())[:SHELL_REPORT_CAP],
           tail[:SHELL_REPORT_CAP]))

FINDING_CHECK = re.compile(r"^\s*ruff\s+check\b")
FINDING_ARROW = re.compile(r"^\s*-->\s+(\S+?):(\d+):\d+\s*$", re.M)
FINDING_CONCISE = re.compile(r"^(\S+?):(\d+):\d+:\s", re.M)
HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")

def path_tail(name: str, root: str = "") -> str:
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
                rows.setdefault(path_tail(name, root), set()).add(number)
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
        out.setdefault(path_tail(name, root), set()).add(row)
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
    return path_tail(text)

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
        text = one_line(command)
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

_MEMBOUND_LIMIT: dict = {}

def _cgroup_megabytes(files) -> tuple:
    for path, layout in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                raw = handle.read().strip()
        except OSError:
            continue
        try:
            value = float(raw) / (1024.0 * 1024.0)
        except ValueError:
            continue
        if value > 0.0:
            return value, layout
    return None, "assumed"

def container_limit_mb() -> tuple:
    cached = _MEMBOUND_LIMIT.get("limit")
    if cached is not None:
        return cached
    value, layout = _cgroup_megabytes(CGROUP_LIMIT_FILES)
    if value is None or value > MEMBOUND_MAX_LIMIT_MB:
        value, layout = MEMBOUND_FALLBACK_MB, "assumed"
    _MEMBOUND_LIMIT["limit"] = (value, layout)
    return value, layout

def child_ceiling_bytes() -> int:
    limit, _ = container_limit_mb()
    return int(min(float(CHILD_MEMORY_BYTES), limit * MEMBOUND_SHARE * 1024.0 * 1024.0))

def resident_by_group() -> tuple:
    try:
        page = os.sysconf("SC_PAGE_SIZE") / (1024.0 * 1024.0)
        entries = os.listdir(PROCESS_TABLE)
    except (OSError, ValueError, AttributeError):
        return 0.0, {}
    total, groups = 0.0, {}
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(os.path.join(PROCESS_TABLE, entry, "statm"), "r",
                      encoding="utf-8", errors="replace") as handle:
                resident = int(handle.read().split()[1]) * page
            with open(os.path.join(PROCESS_TABLE, entry, "stat"), "r",
                      encoding="utf-8", errors="replace") as handle:
                fields = handle.read().rsplit(") ", 1)[-1].split()
            group = int(fields[2])
        except (OSError, IndexError, ValueError):
            continue
        total += resident
        groups[group] = groups.get(group, 0.0) + resident
    return total, groups

_CHILD_CAP_STATE: dict = {}

def _child_limits() -> None:
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        cap = child_ceiling_bytes()
        if hard != resource.RLIM_INFINITY:
            cap = min(cap, hard)
        if soft != resource.RLIM_INFINITY:
            cap = min(cap, soft)
        resource.setrlimit(resource.RLIMIT_AS, (cap, hard))
    except Exception:
        pass

def child_limits_hook():
    beacon = Beacon("childcap")
    said = _CHILD_CAP_STATE.get("said")
    _CHILD_CAP_STATE["said"] = True
    if not CHILD_CAP:
        if not said:
            beacon.skipped("not switched on for this run")
        return None
    if not hasattr(os, "fork"):
        if not said:
            beacon.skipped("children are started here without a hook to bound them")
        return None
    if not said:
        beacon.reached(0, 0.0, 0.0)
        beacon.fired("children of this run get an address-space ceiling")
    return _child_limits

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
        child_env = os.environ.copy()
        child_env.setdefault("GOMAXPROCS", "2")
        child_env.setdefault("CARGO_BUILD_JOBS", "2")
        child_env.setdefault("CMAKE_BUILD_PARALLEL_LEVEL", "2")
        child_env.setdefault("MAKEFLAGS", "-j2")
        self.process = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            stdout=self.sink,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=child_env,
            preexec_fn=child_limits_hook(),
        )

    def _text(self) -> str:
        try:
            self.sink.flush()
            return bounded_output_file(self.sink.name, TOOL_OUTPUT_READ_CAP, "tool output")
        except (OSError, ValueError):
            # ValueError: the sink was already closed.  What the job said is
            # gone, but that is no reason for the tool reading it to fail.
            return ""

    def wait(self, timeout: float) -> tuple:
        try:
            self.process.wait(timeout=max(1.0, timeout))
            return True, self._text()
        except subprocess.TimeoutExpired:
            return False, self._text()

    def finished(self) -> bool:
        return self.process.poll() is not None

    def drain(self) -> str:
        bounded = getattr(self, "bounded", "")
        if self.process.poll() is None:
            return self._text() + "\n" + STILL_RUNNING
        return self._text() + bounded

    def halt(self) -> None:
        """End the job's processes, keeping what it printed for whoever collects it."""
        if self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    self.process.kill()
                except Exception:
                    pass
            try:
                self.process.wait(timeout=5)
            except Exception:
                pass

    def stop(self) -> None:
        self.halt()
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
            raise ToolFault(
                "no background job named %s: its output was already returned by an earlier "
                "bash_poll, or it was never started. Run the command again if you still need "
                "what it prints." % name)
        return job

    def close(self) -> None:
        for job in list(self.jobs.values()):
            try:
                report_shell(job, job.drain())
                job.stop()
            except Exception:
                pass
        self.jobs.clear()

class MemoryBound:
    def __init__(self, pool: "ShellPool") -> None:
        self.pool = pool
        self.beacon = Beacon("membound")
        self.limit, self.source = container_limit_mb()
        self.ceiling = self.limit * MEMBOUND_SHARE
        self.thread = None
        self.running = False
        self.stopped: list = []
        self.peak = 0.0
        self.reading = "resident"
        self.said_nothing_to_stop = False

    def arm(self) -> None:
        self.beacon.reached(0, 0.0, 0.0)
        if not MEMBOUND:
            self.beacon.skipped("not switched on for this run")
            return
        if not os.path.isdir(PROCESS_TABLE):
            self.beacon.skipped("there is no process table to read here")
            return
        import threading
        self.running = True
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        say("[MEMBOUND] reading a %dMB limit (%s), ceiling %dMB, children capped at %dMB"
            % (self.limit, self.source, self.ceiling,
               child_ceiling_bytes() / (1024.0 * 1024.0)))

    def _watch(self) -> None:
        while self.running:
            try:
                self._sample()
            except Exception:
                pass
            time.sleep(MEMBOUND_SAMPLE_SEC)

    def _sample(self) -> None:
        resident, groups = resident_by_group()
        used, reading = _cgroup_megabytes(CGROUP_USAGE_FILES)
        if used is None:
            used, reading = resident, "resident"
        self.peak = max(self.peak, used)
        self.reading = reading
        if used <= self.ceiling:
            return
        try:
            ours = os.getpgrp()
        except (OSError, AttributeError):
            return
        worst, held, inside = None, 0.0, 0.0
        for job in list(self.pool.jobs.values()):
            if job.finished():
                continue
            try:
                group = os.getpgid(job.process.pid)
            except (OSError, ProcessLookupError):
                continue
            if group == ours:
                continue
            size = groups.get(group, 0.0)
            inside += size
            if size > held:
                worst, held = job, size
        if worst is None or held < MEMBOUND_MIN_JOB_MB or used - inside > self.ceiling:
            if not self.said_nothing_to_stop:
                self.said_nothing_to_stop = True
                self.beacon.skipped("%dMB of the %dMB limit is held outside the "
                                    "background jobs (%s over %s)"
                                    % (used - inside, self.limit, reading, self.source))
            return
        self.stopped.append(worst.command)
        worst.bounded = ("\n\n[stopped early: this command's processes were holding "
                         "%dMB of a %dMB container and were stopped before the "
                         "container filled; the output above is partial. Run a "
                         "narrower command -- one package, one directory or one "
                         "test -- rather than everything at once.]"
                         % (held, self.limit))
        # Halted, not stopped: the job stays collectable, so the next poll
        # returns what it printed and the note above instead of failing.
        worst.halt()
        self.beacon.fired("stopped %s holding %dMB at %dMB of a %dMB limit (%s over %s): %s"
                          % (worst.name, held, used, self.limit, reading, self.source,
                             one_line(worst.command)[:160]))

    def close(self) -> None:
        self.running = False
        if not MEMBOUND:
            return
        artefact = "\n".join(one_line(c) for c in self.stopped)
        digest = self.beacon.artefact("before", artefact)
        self.beacon.outcome(digest, artefact)
        if not self.stopped:
            self.beacon.skipped("under bounds: %dMB held at the peak of a %dMB "
                                "limit (%s over %s)"
                                % (self.peak, self.limit, self.reading, self.source))
        self.beacon.bill()

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
            "description": (
                "Replace exact spans of text in one file. Give one change as old/new, or "
                "every change the file needs as `changes` -- a list applied in order, all or "
                "none -- in a single call: a change touching several places in a file is one "
                "call, not one call per place. The reply shows the lines written. Set "
                "replace_all when one span occurs at several places and each needs the same change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string", "description": "Exact text to find, including indentation."},
                    "new": {"type": "string", "description": "Replacement text."},
                    "changes": {
                        "type": "array",
                        "description": "Several changes to this file, applied in order, all or none.",
                        "items": {
                            "type": "object",
                            "properties": {"old": {"type": "string"}, "new": {"type": "string"}},
                            "required": ["old", "new"],
                        },
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace every occurrence instead of requiring a unique one.",
                    },
                },
                "required": ["path"],
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
            "description": "Collect output from a background command started with bash.",
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
            "name": "run_sql",
            "description": (
                "Run SQL against the live PostgreSQL or ClickHouse database this "
                "repository uses. Prefer this over shelling out to psql. Use it for "
                "EXPLAIN (ANALYZE, BUFFERS) on PostgreSQL, EXPLAIN indexes=1 on "
                "ClickHouse, schema inspection, and trying a query. On "
                "PostgreSQL the call runs inside a transaction that is rolled "
                "back afterwards, so you can insert an awkward case, query it "
                "and read the result, but nothing you write here persists. On "
                "ClickHouse reads run anywhere and writes run only inside "
                "agent_scratch, a database that belongs to this run: copy a "
                "table's structure into it with CREATE TABLE agent_scratch.t AS "
                "db.table, fill it from numbers(N), and put your statement to "
                "it. Every ClickHouse result ends with the rows and bytes the "
                "server read for it. A statement that runs too long is cut off "
                "rather than held."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL to run."},
                    "engine": {
                        "type": "string",
                        "enum": ["postgresql", "clickhouse"],
                        "description": "Force an engine when more than one is known.",
                    },
                    "database": {
                        "type": "string",
                        "description": "Override the database / schema name.",
                    },
                    "url": {
                        "type": "string",
                        "description": "postgresql://... or http://host:8123 when discovery missed it.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Finish the run. Call this only once the change is complete and you have re-run the command that found the problem to confirm nothing is left.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]

def _schema(name: str) -> dict:
    return next(t["function"] for t in TOOL_SCHEMAS if t["function"]["name"] == name)

def acting_tool_schemas(schemas: list[dict]) -> list[dict]:
    return [t for t in schemas
            if t["function"]["name"] not in READ_ONLY_TOOL_NAMES]

def tool_offer_image(schemas: list[dict]) -> str:
    return json.dumps(schemas, sort_keys=True)

def tree_untouched(tree) -> bool:
    try:
        return not changed_paths_of(tree)
    except Exception:
        return False

def middle_value(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    half = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[half]
    return (ordered[half - 1] + ordered[half]) / 2.0

if SEARCH_LIMIT:
    _search = _schema("search_text")
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
RUFF_COMMAND_LINE = re.compile(r"^.*\bruff\b[^\n]*$", re.M)
SOURCE_PATH_IN_TEXT = re.compile(
    r"[\w][\w./-]*\."
    r"(?:py|pyi|sql|go|rs|java|kt|kts|scala|rb|php|cs|js|jsx|ts|tsx|"
    r"c|cc|cpp|cxx|h|hh|hpp|hxx|sh)",
    re.I,
)
DECLARED_FILE_SCOPE_RE = re.compile(
    r"\b(?:limit(?:ed)?\s+(?:production\s+|your\s+|the\s+)?changes?\s+to|"
    r"you\s+may\s+edit\s+only|may\s+edit\s+only|edit\s+only|only\s+edit|"
    r"change\s+only|touch\s+only|modify\s+only|"
    r"production\s+changes\s+(?:are\s+)?limited\s+to)\s+"
    r"`(?P<path>[\w][\w./-]*\."
    r"(?:py|pyi|sql|go|rs|java|kt|kts|scala|rb|php|cs|js|jsx|ts|tsx|"
    r"c|cc|cpp|cxx|h|hh|hpp|hxx|sh))`",
    re.I,
)
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

    def __add__(self, other):
        # Building a path or a message out of a constant the absent package
        # exports -- `PREFIX + absent.NAME` -- is an ordinary thing for a
        # module to do while being imported, and without this it raises
        # `TypeError: can only concatenate str (not "_Null") to str`: the same
        # loss the missing import was, one line further on.  Answered rather
        # than raised for the same reason as everything else here -- nothing it
        # returns is a claim about the project, and a reading that comes back
        # mostly red over stand-ins is refused anyway.
        return _Null(self._name + "+")

    __radd__ = __add__
    __mod__ = __add__
    __rmod__ = __add__

    def __repr__(self):
        return "<stand-in %s>" % self._name


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

def inside(path: str, root: str) -> bool:
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

import builtins
NAME_CHECK = flag("RIDGES_NAME_CHECK")
NAME_CHECK_MAX_FILES = 12
MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__package__", "__spec__",
                  "__loader__", "__builtins__", "__path__", "__all__", "__dict__",
                  "__annotations__", "__cached__", "__debug__", "__class__",
                  "__qualname__", "__module__"}
NAME_HEAD = ("Not handed in yet: the changed code reads a name its module never "
             "binds, so it fails the moment that line runs. One look before it goes:")
NAME_NOTE = ("`%s` is used at %s:%d, and nothing in that module binds it: no import, "
             "definition or assignment, and %s. Python raises NameError the moment "
             "that line runs, and neither compiling the file nor a lint that ignores "
             "star imports can see it. Import the name explicitly, or reach it through "
             "a module the file already binds.")

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
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("exec", "eval", "globals", "vars", "locals", "__import__")):
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

def star_exports(root: str, path: str, seen: set | None = None) -> set | None:
    seen = set() if seen is None else seen
    if path in seen:
        return set()
    seen.add(path)
    try:
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read())
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
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.lineno in lines and node.id not in bound and id(node) not in skip):
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

def path_added_lines(root: str, base: str, path: str) -> set:
    code, out = git(["diff", "--unified=0", base or "HEAD", "--", path], root, 30)
    if code != 0:
        return set()
    if not out.strip():
        known, _ = git(["cat-file", "-e", "%s:%s" % (base or "HEAD", path)], root, 10)
        if known == 0:
            return set()
        try:
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
                return set(range(1, len(handle.read().splitlines()) + 1))
        except OSError:
            return set()
    return added_line_numbers(out)

def declared_file(statement: str, root: str) -> str | None:
    explicit = DECLARED_FILE_SCOPE_RE.search(statement or "")
    if explicit:
        candidate = explicit.group("path")
        if (not TEST_PATH.search(candidate)
                and os.path.isfile(os.path.join(root, candidate))):
            return candidate
    if ELIXIR:
        for candidate in ELIXIR_PATH_IN_TEXT.findall(statement or ""):
            if candidate.endswith("_test.exs"):
                continue
            if os.path.isfile(os.path.join(root, candidate)):
                return candidate
    logical_lines: list[str] = []
    lines = (statement or "").splitlines()
    index = 0
    while index < len(lines):
        logical = lines[index]
        while logical.rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            logical = logical.rstrip()[:-1] + " " + lines[index].strip()
        logical_lines.append(logical)
        index += 1
    for line in logical_lines:
        if not re.search(r"\bruff\b", line):
            continue
        for candidate in SOURCE_PATH_IN_TEXT.findall(line):
            if TEST_PATH.search(candidate):
                continue
            if os.path.isfile(os.path.join(root, candidate)):
                return candidate
    return None

DECLARED_DEFINITION_RE = re.compile(
    r"\bspecifically\s+`?(?:(?P<owner>[A-Za-z_]\w*)\.)?"
    r"(?P<name>[A-Za-z_]\w*)\(\)`?",
    re.I,
)
# The phrases below are read out of prose wrapped at a fixed width, so any
# space in them may arrive as a line break: every gap is `\s+`, never " ".
EXCLUSIVE_FILE_RE = re.compile(
    r"\b(?:edit\s+only|may\s+edit\s+only|only\s+edit|limit\s+(?:production\s+)?changes\s+to|"
    r"production\s+changes\s+(?:are\s+)?limited\s+to|change\s+only|touch\s+only|modify\s+only|"
    r"changes?\s+(?:must\s+be\s+|are\s+)?(?:limited|confined|restricted)\s+to)\b",
    re.I,
)
METHOD_TICK_RE = re.compile(r"`((?:[A-Za-z_][\w]*\.)*)([A-Za-z_]\w*)\(\)`")
ELIXIR_PATH_IN_TEXT = re.compile(r"(?<![\w/])((?:[\w.\-]+/)+[\w.\-]+\.exs?)(?![\w])")
FUNCTION_ARITY_RE = re.compile(r"`((?:[A-Z]\w*\.)*)([a-z_]\w*[!?]?)/(\d+)`")
CONSTRUCT_BAN_RE = re.compile(
    r"no\s+python\s+loops|plain\s+orm\s+expressions|no\s+python\s+loops,\s+comprehensions", re.I
)
IMPORTS_FROZEN_RE = re.compile(
    r"including\s+imports|only\s+names\s+the\s+file\s+already\s+imports|"
    r"do\s+not\s+(?:add|change)\s+imports",
    re.I,
)
SIGNATURE_FROZEN_RE = re.compile(
    r"keep\s+(?:its|the|the\s+method)\s+signature|signature\s+(?:unchanged|intact|the\s+same)",
    re.I,
)
REST_FROZEN_RE = re.compile(
    r"rest\s+of\s+(?:its|the|that)\s+file\s+(?:unchanged|as\s+it\s+is|exactly)|"
    r"everything\s+else\s+in\s+(?:that|the)\s+file|all\s+unrelated\s+source|"
    r"unrelated\s+(?:source|code)\s+(?:unchanged|as\s+it\s+is)",
    re.I,
)

def declared_definition(statement: str) -> tuple[str | None, str] | None:
    match = DECLARED_DEFINITION_RE.search(statement or "")
    if match:
        return match.group("owner"), match.group("name")
    found: list[tuple[str | None, str]] = []
    for prefix, name in METHOD_TICK_RE.findall(statement or ""):
        pair = (prefix.rstrip(".") or None, name)
        if pair not in found:
            found.append(pair)
    if len(found) == 1:
        return found[0]
    owned = [pair for pair in found if pair[0]]
    if len(owned) == 1:
        return owned[0]
    return None

def definition_node(source: str, target: tuple[str | None, str]) -> ast.AST | None:
    try:
        module = ast.parse(source)
    except SyntaxError:
        return None
    owner, name = target
    matches: list[ast.AST] = []
    if owner:
        for node in ast.walk(module):
            if isinstance(node, ast.ClassDef) and node.name == owner:
                matches.extend(
                    child for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == name
                )
    else:
        matches.extend(
            node for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        )
    return matches[0] if len(matches) == 1 else None

def definition_contract(source: str, target: tuple[str | None, str]) -> tuple[str, str] | None:
    node = definition_node(source, target)
    if node is None:
        return None
    lines = source.splitlines(keepends=True)
    start = int(getattr(node, "lineno", 1)) - 1
    end = int(getattr(node, "end_lineno", start + 1))
    outside = "".join(lines[:start]) + "<DECLARED-DEFINITION>\n" + "".join(lines[end:])
    signature = ast.dump(getattr(node, "args"), include_attributes=False)
    returns = getattr(node, "returns", None)
    signature += "|" + (ast.dump(returns, include_attributes=False)
                         if returns is not None else "")
    signature += "|async=%s" % isinstance(node, ast.AsyncFunctionDef)
    return outside, signature

def declared_trace(statement: str, root: str) -> str:
    lines = RUFF_COMMAND_LINE.findall(statement or "")
    seen = dropped = existed = 0
    for line in lines:
        for candidate in SOURCE_PATH_IN_TEXT.findall(line):
            seen += 1
            if TEST_PATH.search(candidate):
                dropped += 1
            elif os.path.isfile(os.path.join(root, candidate)):
                existed += 1
    return ("%d command line(s), %d path(s) on them, %d dropped as tests, "
            "%d that exist here" % (len(lines), seen, dropped, existed))

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

def patch_shape(patch: str) -> str:
    files = hunks = 0
    added: list = []
    removed: list = []
    inside = False
    for line in (patch or "").split("\n"):
        if line.startswith("diff --git "):
            files += 1
            inside = False
        elif line.startswith("@@ "):
            hunks += 1
            inside = True
        elif inside and line.startswith("+"):
            added.append(line[1:].strip())
        elif inside and line.startswith("-"):
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

def visible_definitions(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []

    def walk(node: ast.AST, prefix: str, inside: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async" if isinstance(child, ast.AsyncFunctionDef) else "def"
                if not inside:
                    found.append("%s %s%s" % (kind, prefix, child.name))
                walk(child, prefix + child.name + ".", True)
            elif isinstance(child, ast.ClassDef):
                if not inside:
                    found.append("class %s%s" % (prefix, child.name))
                walk(child, prefix + child.name + ".", inside)
            else:
                walk(child, prefix, inside)
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

MIX_MANIFEST = "mix.exs"
MIX_TIERS = ("", " --no-deps-check")
MIX_BASELINE_SEC = 420.0
MIX_RECHECK_SEC = 300.0
MIX_BUILD_DIRS = ("deps", "_build")
MIX_FAST_FAIL_SEC = 30.0
ECTO_DIFF_CONTEXT = 3
ECTO_NOTE_MIN_SEC = 90.0

def elixir_project(root: str) -> bool:
    try:
        return os.path.isfile(os.path.join(root, MIX_MANIFEST))
    except OSError:
        return False

def mix_ready(where: str, live: str) -> bool:
    ok = True
    for name in MIX_BUILD_DIRS:
        source = os.path.join(live, name)
        target = os.path.join(where, name)
        if not os.path.isdir(source):
            continue
        if os.path.exists(target):
            continue
        try:
            os.symlink(source, target)
        except OSError:
            ok = False
    return ok

def mix_scope(root: str, declared: str | None) -> list[str]:
    if not declared:
        return []
    if declared.endswith("_test.exs"):
        return [declared] if os.path.isfile(os.path.join(root, declared)) else []
    if not declared.endswith((".ex", ".exs")):
        return []
    parts = [p for p in declared.split("/") if p]
    if not parts:
        return []
    base = os.path.splitext(parts[-1])[0]
    inner = parts[:-1]
    prefix: list[str] = []
    if len(parts) > 2 and parts[0] == "apps":
        prefix, inner = parts[:2], parts[2:-1]
    if inner and inner[0] in ("lib", "src", "web"):
        inner = inner[1:]
    tries: list[str] = []

    def under(*bits: str) -> None:
        path = "/".join([b for b in list(prefix) + list(bits) if b])
        if path and path not in tries:
            tries.append(path)
    for cut in range(len(inner) + 1):
        under("test", *inner[cut:], "%s_test.exs" % base)
    for cut in range(len(inner)):
        under("test", *inner[cut:])
    under("test")
    for rel in tries:
        full = os.path.join(root, *rel.split("/"))
        if rel.endswith(".exs"):
            if os.path.isfile(full):
                return [rel]
        elif os.path.isdir(full):
            return [rel]
    return []

MIX_FAILURE = re.compile(
    r"^[ \t]*\d+\)[ \t]+(?P<name>.+?)[ \t]*\((?P<mod>[A-Za-z0-9_.]+)\)[ \t]*\r?\n"
    r"[ \t]*(?P<at>[^\s:]+\.exs:\d+)",
    re.M,
)
MIX_FAILURE_LOOSE = re.compile(
    r"^[ \t]*\d+\)[ \t]+(?P<name>.+?)[ \t]*\((?P<mod>[A-Za-z0-9_.]+)\)[ \t]*$", re.M
)
MIX_LOCATION = re.compile(r"^[^\s:]+\.exs:\d+$")
MIX_COUNT = re.compile(
    r"(\d+)\s+(doctests?|properties|property|tests?|failures?|excluded|skipped|invalid)"
)
MIX_REASON = re.compile(
    r"^\*?\*?\s*((?:Can't continue due to errors|Could not compile|"
    r"could not compile|\*\* \(Mix\)|\*\* \(CompileError\)|"
    r"\*\* \(SyntaxError\)|\*\* \(TokenMissingError\)|"
    r"\*\* \(Ecto\.QueryError\)|The database for .* does not exist)\b.*)$",
    re.M,
)

def _mix_word(word: str) -> str:
    if word.startswith("propert"):
        return "property"
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word

def read_mix(out: str) -> tuple[set, int]:
    names: set = set()
    located: set = set()
    for match in MIX_FAILURE.finditer(out or ""):
        names.add(match.group("at"))
        located.add((match.group("mod"), match.group("name").strip()))
    for match in MIX_FAILURE_LOOSE.finditer(out or ""):
        pair = (match.group("mod"), match.group("name").strip())
        if pair not in located:
            names.add("%s %s" % pair)
    ran = failed = away = 0
    for line in (out or "").splitlines():
        if "failure" not in line or not MIX_COUNT.search(line):
            continue
        counts: dict = {}
        for number, word in MIX_COUNT.findall(line):
            counts[_mix_word(word)] = int(number)
        if "failure" not in counts:
            continue
        ran += counts.get("test", 0) + counts.get("doctest", 0) + counts.get("property", 0)
        failed += counts["failure"]
        away += counts.get("skipped", 0) + counts.get("excluded", 0) + counts.get("invalid", 0)
    return names, max(0, ran - failed - away)

def line_offsets(lines: list) -> list:
    starts, run = [], 0
    for line in lines:
        starts.append(run)
        run += len(line) + 1
    return starts

def line_at(starts: list, index: int) -> int:
    low, high = 0, len(starts) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if starts[middle] <= index:
            low = middle
        else:
            high = middle - 1
    return low

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

def fragment_arity_findings(diff: str) -> list:
    found: list = []
    for start, added, lines in engine_hunks(diff):
        offsets = {offset for offset, _ in added}
        text = "\n".join(lines)
        starts = line_offsets(lines)
        for match in re.finditer(r"\bfragment\(\s*", text):
            index = match.end()
            if text.startswith('"""', index):
                close = text.find('"""', index + 3)
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
                found.append(("ex_fragment_arity",
                              "fragment(...) with %d ? placeholder(s) and %d argument(s)"
                              % (placeholders, arguments), start + first))
    return found

ECTO_NOTES = {
    "ex_fragment_arity": ("`%s`. Ecto checks a fragment when the module compiles and rejects one whose count of ? "
                          "placeholders differs from the number of arguments after the string, so the module does "
                          "not compile. Give every ? exactly one argument, in order."),
}
ELIXIR_DEF = re.compile(
    r"^(?P<indent>[ \t]*)(?:def|defp|defmacro|defmacrop|defdelegate|defguard|defguardp)"
    r"\s+(?P<name>[a-z_]\w*[!?]?)\b"
)
ELIXIR_HEADER = re.compile(r"^[ \t]*(?:alias|import|require|use|@behaviour|@impl)\b.*$", re.M)
ELIXIR_BANNED = (
    (r"\bEnum\.", "Enum.*"),
    (r"\bStream\.", "Stream.*"),
    (r"\bfor\b\s+\w+\s+<-", "a for comprehension"),
    (r"\bfn\b", "an anonymous function"),
    (r"\bcase\b\s", "case"),
    (r"\bcond\b\s*do", "cond"),
    (r"\bwith\b\s+\{", "with"),
    (r"\btry\b\s*do", "try"),
    (r"\breceive\b\s*do", "receive"),
    (r"\bTask\.", "Task.*"),
    (r"\bProcess\.", "Process.*"),
    (r"\bapply\(", "apply/3"),
    (r"\bCode\.eval", "Code.eval_*"),
)

def elixir_header_block(text: str) -> list:
    return [line.strip() for line in ELIXIR_HEADER.findall(text or "")]

def elixir_def_spans(text: str, name: str) -> tuple | None:
    lines = (text or "").splitlines()
    first = last = None
    index = 0
    while index < len(lines):
        match = ELIXIR_DEF.match(lines[index])
        if not match or match.group("name") != name:
            index += 1
            continue
        indent = match.group("indent")
        start = index
        if re.search(r",\s*do:\s*\S", lines[index]) or lines[index].rstrip().endswith(", do:"):
            end = index
            while (end + 1 < len(lines) and lines[end + 1].strip()
                   and not ELIXIR_DEF.match(lines[end + 1])
                   and len(lines[end + 1]) - len(lines[end + 1].lstrip()) > len(indent)):
                end += 1
        else:
            end = None
            for after in range(index + 1, len(lines)):
                if lines[after].rstrip() == indent + "end":
                    end = after
                    break
            if end is None:
                return None
        first = start if first is None else min(first, start)
        last = end if last is None else max(last, end)
        index = end + 1
    if first is None:
        return None
    return (first + 1, last + 1)

def elixir_construct_faults(body: str) -> list:
    found: list = []
    for pattern, said in ELIXIR_BANNED:
        if re.search(pattern, body or "") and said not in found:
            found.append(said)
    return found

def elixir_audit(path: str, before: str, after: str, pins: "SpecPins") -> list:
    problems: list = []

    def said(name: str) -> str:
        arity = pins.arities.get(name)
        return "%s/%s" % (name, arity) if arity is not None else name
    if pins.imports_frozen and elixir_header_block(after) != elixir_header_block(before):
        problems.append(
            "The alias/import/require/use block of %s changed. The task says to use only "
            "what the module already brings in; restore those lines exactly and express "
            "the change with what is in scope." % path
        )
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    named_here = [
        (prefix, name) for prefix, name in pins.methods
        if elixir_def_spans(before, name) is not None
    ]
    if not named_here and (pins.rest_frozen or pins.signature_frozen or pins.constructs_banned):
        return problems
    for _, name in named_here:
        was = elixir_def_spans(before, name)
        now = elixir_def_spans(after, name)
        if was is None:
            continue
        if now is None:
            problems.append(
                "%s no longer defines %s; the task changes that function in place, "
                "it does not rename or remove it." % (path, said(name))
            )
            continue
        if pins.rest_frozen or pins.restricted:
            if (before_lines[: was[0] - 1] != after_lines[: now[0] - 1]
                    or before_lines[was[1]:] != after_lines[now[1]:]):
                problems.append(
                    "Lines outside %s in %s differ from the original. Everything else "
                    "in the file has to stay byte-identical. Put the rest back and keep "
                    "the change inside the function." % (said(name), path)
                )
        if pins.signature_frozen:
            was_head = "".join(before_lines[was[0] - 1: was[0]]).strip()
            now_head = "".join(after_lines[now[0] - 1: now[0]]).strip()
            if was_head.split("do")[0].strip() != now_head.split("do")[0].strip():
                problems.append(
                    "The head of %s changed (%s -> %s); keep it exactly as it was."
                    % (said(name), was_head[:80], now_head[:80])
                )
        if pins.constructs_banned:
            already = set(elixir_construct_faults("".join(before_lines[was[0] - 1: was[1]])))
            bad = [item for item in elixir_construct_faults("".join(after_lines[now[0] - 1: now[1]]))
                   if item not in already]
            if bad:
                problems.append(
                    "%s now contains forms the task forbids: %s. The function has to be a "
                    "plain Ecto query expression: no Enum/Stream, comprehensions, anonymous "
                    "functions, case/cond/with/try, or work done in Elixir that the query "
                    "should do in the database." % (said(name), ", ".join(bad[:6]))
                )
    return problems

class Warden:
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 statement: str = "") -> None:
        # What each file the run touched arrived with, once it has been read.
        self._arrived: dict = {}
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.declared = declared_file(statement, tree.root)
        self.kind = "mix" if (ELIXIR and elixir_project(tree.root)) else "pytest"
        self.site = "worktree"
        self.retried_live = False
        self.declared_target = declared_definition(statement)
        self.exclusive_file = bool(EXCLUSIVE_FILE_RE.search(statement or ""))
        self.statement = statement
        self.ledger = Beacon("ledger")
        self.read_back_at: str | None = None
        self.read_backs = 0
        self.records: list = []
        self.beacon = Beacon("warden")
        self.job: Shell | None = None
        self.started = time.time()
        self.before: tuple[set, int] | None = None
        self.refusals = 0
        self.stood_down = False
        self.where: str | None = None
        self.tier = 0
        self.scope: list[str] = []
        self.armed_after: float | None = None
        self.shims: list = []
        self.shim_dir = ""
        self.stood_in = 0

    def suite_command(self, root: str | None = None) -> str:
        root = root or self.tree.root
        if self.kind == "mix":
            return self.mix_command(root)
        path = os.pathsep.join(package_roots(root) + ([self.shim_dir] if self.shim_dir else []))
        where = " ".join(shlex.quote(rel) for rel in self.scope)
        return (
            "cd %s && PYTHONPATH=%s PYTHONHASHSEED=0 PYTHONPYCACHEPREFIX=%s %s -m pytest -q "
            "--no-header --tb=line -rfE -p no:cacheprovider -o addopts= "
            "--continue-on-collection-errors -W ignore::DeprecationWarning%s%s"
            % (root, path, tempfile.mkdtemp(prefix="pyc"),
               sys.executable or "python3", SUITE_TIERS[self.tier],
               (" " + where) if where else "")
        )

    def mix_command(self, root: str | None = None) -> str:
        root = root or self.tree.root
        where = " ".join(shlex.quote(rel) for rel in self.scope)
        return (
            "cd %s && MIX_ENV=test mix test --no-color --seed 0%s%s"
            % (shlex.quote(root), MIX_TIERS[self.tier], (" " + where) if where else "")
        )

    def mix_escalate(self) -> bool:
        if self.tier >= len(MIX_TIERS) - 1:
            return False
        if self.allowance.clock_left() < self.allowance.rung_min_wall_sec:
            self.beacon.skipped("below what a rung needs; not reading again")
            return False
        self.tier += 1
        self.beacon.fired("reading again at rung %d of %d" % (self.tier + 1, len(MIX_TIERS)))
        try:
            self.job = self.pool.start(self.mix_command(self.where or self.tree.root))
        except Exception as error:
            self.beacon.skipped("could not restart the baseline reading: %s" % error)
            return False
        return True

    def mix_retry_live(self, out: str, elapsed: float) -> bool:
        if self.site != "worktree" or self.retried_live or self.where is None:
            return False
        names, passing = read_mix(out)
        if passing or names or elapsed >= MIX_FAST_FAIL_SEC:
            return False
        self.retried_live = True
        self.site = "live"
        self.where = None
        self.beacon.fired("mix ran no test at the separate checkout in %.0fs (%s); "
                          "reading the live tree instead" % (elapsed, self.reason(out)))
        try:
            self.job = self.pool.start(self.mix_command(self.tree.root))
        except Exception as error:
            self.beacon.skipped("could not restart the baseline reading: %s" % error)
        return True

    def pristine(self) -> str | None:
        where = os.path.join(tempfile.mkdtemp(prefix="start"), "tree")
        code, out = git(["worktree", "add", "--detach", where, self.tree.base or "HEAD"],
                        self.tree.root, 60)
        if code != 0:
            self.beacon.skipped("no separate checkout to read: %s" % out.strip()[:120])
            return None
        return where

    def arm(self) -> None:
        if not SUBMISSION_WARDEN:
            self.beacon.skipped("not switched on for this run")
            return
        self.beacon.reached(0, self.allowance.spent, self.allowance.clock_left())
        try:
            self.where = self.pristine()
            if self.kind == "mix":
                if self.where and not mix_ready(self.where, self.tree.root):
                    self.beacon.fired("the separate checkout could not be given the "
                                      "build mix needs; reading the live tree instead")
                    self.where = None
                self.site = "worktree" if self.where else "live"
                self.scope = mix_scope(self.tree.root, self.declared) if SUITE_SCOPE else []
            else:
                self.scope = suite_scope(self.tree.root, self.declared) if SUITE_SCOPE else []
            say("[WARDEN] baseline scope: %s (%s, %s tree)"
                % (", ".join(self.scope) if self.scope else "the whole repository",
                   self.kind, self.site))
            if not self.scope:
                if not SUITE_SCOPE:
                    say("[WARDEN] wide baseline: not switched on for this run")
                elif self.declared is None:
                    say("[WARDEN] the statement gave: %s"
                        % declared_trace(self.statement, self.tree.root))
                else:
                    say("[WARDEN] wide baseline: nothing matched")
            self.job = self.pool.start(self.suite_command(self.where))
        except Exception as error:
            self.beacon.skipped("could not start the baseline reading: %s" % error)

    def escalate(self) -> bool:
        if self.where is None:
            return False
        if self.kind == "mix":
            return self.mix_escalate()
        top = len(SUITE_TIERS) - 1 if SUITE_IMPORTLIB else len(SUITE_TIERS) - 2
        if self.tier >= top:
            if self.tier < len(SUITE_TIERS) - 1:
                self.beacon.skipped("this rung is not switched on for this run")
            return False
        if self.allowance.clock_left() < self.allowance.rung_min_wall_sec:
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
        if self.allowance.clock_left() < self.allowance.standin_min_wall_sec:
            self.beacon.skipped("too little of the run left to read the suite again")
            return False
        if not self.shim_dir:
            try:
                room = tempfile.mkdtemp(prefix="standin")
            except OSError as error:
                self.beacon.skipped("nowhere to write a stand-in: %s" % error)
                self.shim_dir = ""
                return False
            if inside(room, self.tree.root):
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
                                % one_line(", ".join(wanted + records))[:80])
            return False
        told = []
        if made:
            told.append("does not carry " + one_line(", ".join(made))[:90])
        if kept:
            told.append("has no installed record of " + one_line(", ".join(kept))[:90])
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

    def settle(self, reserve_sec: float | None = None) -> None:
        for _ in range((1 + SUITE_SHIM_LIMIT) * len(SUITE_TIERS)):
            self.collect()
            if self.before is not None or self.job is None:
                return
            reserve = (self.allowance.warden_release_sec
                       if reserve_sec is None else
                       max(self.allowance.warden_release_sec, reserve_sec))
            if self.allowance.clock_left() < reserve:
                reserve = self.allowance.warden_release_sec
            room = self.allowance.clock_left() - reserve
            window = min(self.allowance.suite_settle_sec, room)
            if window < 5.0:
                break
            self.job.wait(window)
            if not self.job.finished():
                break
        self.collect()

    def collect(self) -> None:
        if self.job is None or self.before is not None:
            return
        if not self.job.finished():
            window = self.allowance.suite_baseline_sec
            if self.kind == "mix":
                window = max(window, MIX_BASELINE_SEC)
            if time.time() - self.job.started > window:
                self.job.stop()
                self.pool.jobs.pop(self.job.name, None)
                self.job = None
                self.beacon.skipped("the project's tests did not finish in the "
                                    "time this rung allows")
            return
        elapsed = time.time() - self.job.started
        done, out = self.job.wait(0.5)
        self.pool.jobs.pop(self.job.name, None)
        self.job = None
        if self.kind == "mix" and self.mix_retry_live(out, elapsed):
            return
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
        if propped:
            green = reading[1] / float(reading[1] + len(reading[0]) or 1)
            if green < SUITE_SHIM_MIN_GREEN:
                self.beacon.skipped(
                    "read over %d stand-in(s) and only %.0f%% of it passes; that is a "
                    "reading about the stand-ins, not about the project"
                    % (propped, 100 * green))
                return
        self.before = reading
        self.armed_after = time.time() - self.started
        say("[WARDEN] the project's tests at the start: %d failing, %d passing "
            "(tier %d, scope %s, %.0fs)"
            % (len(self.before[0]), self.before[1], self.tier + 1,
               ",".join(self.scope) or "repository", self.armed_after))

    def tally(self, out: str) -> str:
        if self.kind == "mix":
            lines = [line.strip() for line in (out or "").splitlines()
                     if "failure" in line and MIX_COUNT.search(line)]
            return lines[-1] if lines else "no tally"
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

    def read_suite(self, out: str) -> tuple[set, int]:
        if self.kind == "mix":
            return read_mix(out)
        counts = PASSED_COUNT.findall(out or "")
        return set(FAILED_TEST.findall(out or "")), int(counts[-1]) if counts else 0

    def suite_faults(self, reserve_sec: float | None = None) -> list[str]:
        if self.before is None:
            return []
        reserve = (self.allowance.warden_release_sec
                   if reserve_sec is None else
                   max(self.allowance.warden_release_sec, reserve_sec))
        if self.allowance.clock_left() < reserve:
            reserve = self.allowance.warden_release_sec
        room = self.allowance.clock_left() - reserve
        if room < 30.0:
            return []
        job = self.pool.start(self.suite_command())
        done, out = job.wait(min(MIX_RECHECK_SEC if self.kind == "mix" else SUITE_RECHECK_SEC, room))
        self.pool.jobs.pop(job.name, None)
        if not done:
            job.stop()
            self.beacon.skipped("the project's tests did not finish in the time left")
            return []
        broke, passing = self.read_suite(out)
        fresh = self.confirm(sorted(broke - self.before[0]), reserve_sec)
        if fresh:
            say("[WARDEN] the refusal %s the question"
                % ("carries" if WARDEN_ASK else "does not carry"))
            return ["The project's own tests were passing when this run started "
                    "and are failing now: %s. The task requires the project's tests to "
                    "keep passing, so this answer does not satisfy it as it "
                    "stands. Fix the behaviour rather than the test.%s"
                    % (", ".join(fresh[:6]), WARDEN_QUESTION if WARDEN_ASK else "")]
        if passing < self.before[1]:
            return ["The project's suite reported %d passing tests at the start "
                    "of this run and %d now. A suite that got smaller is not "
                    "evidence that behaviour was kept: a skipped or deselected "
                    "test proves nothing." % (self.before[1], passing)]
        return []

    def confirm(self, names: list[str], reserve_sec: float | None = None) -> list[str]:
        if not names:
            return []
        reserve = (self.allowance.warden_release_sec
                   if reserve_sec is None else
                   max(self.allowance.warden_release_sec, reserve_sec))
        if self.allowance.clock_left() < reserve:
            reserve = self.allowance.warden_release_sec
        room = self.allowance.clock_left() - reserve
        if room < 20.0:
            return names
        asked = names[:CONFIRM_MAX]
        if self.kind == "mix":
            asked = [n for n in asked if MIX_LOCATION.match(n)]
            if not asked:
                self.beacon.skipped("none of the changed-side names carry a location "
                                    "mix can be asked about; taking them as they stand")
                return names[:CONFIRM_MAX]
        job = self.pool.start("%s %s" % (self.suite_command(),
                                         " ".join(shlex.quote(n) for n in asked)))
        done, out = job.wait(min(MIX_RECHECK_SEC if self.kind == "mix" else SUITE_RECHECK_SEC, room))
        self.pool.jobs.pop(job.name, None)
        if not done:
            job.stop()
            return asked
        again, _ = self.read_suite(out)
        settled = [n for n in asked if n in again]
        if len(settled) != len(asked):
            self.beacon.fired("%d of %d only failed once and were let go"
                              % (len(asked) - len(settled), len(asked)))
        return settled

    def changed_paths(self) -> list[str]:
        code, out = git(["diff", "--name-only", self.tree.base or "HEAD"],
                        self.tree.root, 30)
        paths = [p for p in out.splitlines() if p.strip()] if code == 0 else []
        return paths + sorted(self.tree._untracked() - self.tree.untracked_at_start)

    def original(self, path: str) -> str | None:
        if path in self._arrived:
            # What a file arrived with cannot change while the run is going on,
            # and this is asked once per touched file from several readings of
            # the same change.
            return self._arrived[path]
        code, out = git(["show", "%s:%s" % (self.tree.base, path)], self.tree.root,
                        ORIGINAL_READ_SEC)
        if code != 0 and not out:
            # A read that came back with nothing may have run out rather than
            # found nothing, so it is not remembered.
            return None
        self._arrived[path] = out if code == 0 else None
        return out if code == 0 else None

    def change_faults(self) -> list[str]:
        faults: list[str] = []
        for path in self.changed_paths():
            if (self.exclusive_file and self.declared is not None
                    and path != self.declared):
                faults.append(
                    "This run edited %s, but the task limits production changes "
                    "to %s. Restore every other path before handing in."
                    % (path, self.declared)
                )
                continue
            if TEST_PATH.search(path):
                faults.append(
                    "This run edited %s. The task is to change the code under "
                    "repair, not the tests that check it; editing a test file "
                    "or a conftest reads as tampering. Put it back exactly as "
                    "it was and make the source satisfy the test instead." % path)
                continue
            faults.extend(self.file_faults(path))
        return faults

    def file_faults(self, path: str) -> list[str]:
        before = self.original(path)
        if before is None:
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
        added = len(NOQA_DIRECTIVE.findall(after)) - len(NOQA_DIRECTIVE.findall(before))
        if added > 0:
            out.append(
                "This run added %d suppression comment(s) to %s. Silencing "
                "the check is the one answer the task rules out; the count "
                "may not go up." % (added, path))
        if self.declared_target is not None and path == self.declared:
            old_contract = definition_contract(before, self.declared_target)
            new_contract = definition_contract(after, self.declared_target)
            if old_contract is not None and new_contract is not None:
                if old_contract[0] != new_contract[0]:
                    owner, name = self.declared_target
                    qualified = "%s.%s" % (owner, name) if owner else name
                    out.append(
                        "The task limits the change to %s(), but this diff also "
                        "changes imports or source outside that definition. "
                        "Restore the surrounding file exactly and keep only the "
                        "method-body repair." % qualified
                    )
                if old_contract[1] != new_contract[1]:
                    owner, name = self.declared_target
                    qualified = "%s.%s" % (owner, name) if owner else name
                    out.append(
                        "The callable signature of %s() changed. Restore its "
                        "original parameters and return annotation." % qualified
                    )
            if CONSTRUCT_BAN_RE.search(self.statement or ""):
                owner, name = self.declared_target
                before_span = method_span(before, owner or "", name)
                after_span = method_span(after, owner or "", name)
                if before_span and after_span:
                    already = set(construct_faults(before_span[2]))
                    bad = [item for item in construct_faults(after_span[2])
                           if item not in already]
                    if bad:
                        qualified = "%s.%s" % (owner, name) if owner else name
                        out.append(
                            "%s() now contains constructs the task forbids: %s. "
                            "Keep it as plain query-layer expressions."
                            % (qualified, ", ".join(bad[:6]))
                        )
        return out

    def work_mark(self) -> str | None:
        code, out = git(["diff", "--name-only", self.tree.base or "HEAD"],
                        self.tree.root, 30)
        if code != 0:
            return None
        listed, names = git(["ls-files", "--others", "--exclude-standard", "-z"],
                            self.tree.root, 30)
        if listed != 0:
            return None
        fresh = {p for p in names.split("\0") if p} - self.tree.untracked_at_start
        paths = sorted(set(p for p in out.splitlines() if p.strip()) | fresh)
        parts = []
        for path in paths:
            full = os.path.join(self.tree.root, path)
            try:
                with open(full, "rb") as handle:
                    parts.append("%s:%s" % (path, hashlib.sha256(
                        handle.read()).hexdigest()[:16]))
            except OSError:
                return None
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]

    def ledger_faults(self) -> list[str]:
        if not LEDGER_READBACK:
            self.ledger.skipped("not switched on for this run")
            return []
        items = stated_requirements(self.statement)
        if len(items) < LEDGER_MIN:
            self.ledger.skipped("%d item(s), below the floor" % len(items))
            return []
        mark = self.work_mark()
        if mark is None:
            mark = self.read_back_at
        if self.read_back_at is not None and self.read_back_at != mark:
            return []
        if self.allowance.clock_left() < self.allowance.conform_min_wall_sec:
            self.ledger.skipped("too little of the run left to act on it")
            return []
        if self.read_backs >= LEDGER_MAX_ASKS:
            self.ledger.skipped("asked %d time(s) already" % self.read_backs)
            return []
        if self.read_back_at == mark:
            held = [read_back(items)]
            self.read_backs += 1
            self.ledger.fired("again; the change has not moved since")
            return held
        held = [read_back(items)]
        self.read_backs += 1
        self.read_back_at = mark
        self.ledger.fired("%d item(s), %d of the kind that asks for an edit"
                          % (len(items),
                             sum(1 for i in items if wants_an_edit(i))))
        return held

    def verdict(self, reserve_sec: float | None = None) -> list[str]:
        if not SUBMISSION_WARDEN:
            return []
        self.settle(reserve_sec)
        if self.before is None and self.job is not None:
            self.beacon.skipped("the project's tests were still running when "
                                "the answer was ready")
        if self.refusals >= WARDEN_REFUSALS_MAX:
            self.stood_down = True
            self.beacon.skipped("already sent the run back %d times" % self.refusals)
            return []
        if self.allowance.clock_left() < self.allowance.warden_release_sec:
            self.stood_down = True
            self.beacon.skipped("too little of the run left to act on a refusal")
            return []
        faults = self.change_faults() or self.suite_faults(reserve_sec)
        said, mine = (faults[0][:120] if faults else ""), True
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

class Finished(Exception):
    pass

_CONFIG_NAMES = (
    "settings.py",
    "configuration.py",
    "config.py",
    "database.yml",
    "database.yaml",
    ".env",
    ".env.example",
    ".env.local",
    ".env.test",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "knexfile.js",
    "knexfile.ts",
    "schema.prisma",
    "alembic.ini",
    "ormconfig.json",
    "ormconfig.js",
    "ormconfig.ts",
    "drizzle.config.ts",
    "drizzle.config.js",
    "application.properties",
    "application.yml",
    "application.yaml",
    "config.toml",
    "config.yaml",
    "config.yml",
    "config.json",
    "settings.toml",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    "Makefile",
    "dev.exs",
    "test.exs",
    "runtime.exs",
    "sequelize.config.js",
    ".sequelizerc",
    "datasource.ts",
    "db.py",
    "database.py",
    "conftest.py",
    "local_settings.py",
    "settings_test.py",
    "test_settings.py",
)
_CONFIG_LINE = re.compile(
    r"(postgres|clickhouse|DATABASE_URL|DB_HOST|DB_NAME|DB_USER|DB_PASS|PGHOST|PGPORT|PGUSER|"
    r"PGPASSWORD|PGDATABASE|\bhost:|\bport:|\busername:|\bpassword:|\bdatabase:|\bdbname|"
    r"jdbc:|psql|:8123|:9000|:5432|\b5432\b|\b8123\b)",
    re.I,
)
_DJANGO_KEYS = re.compile(r"['\"](ENGINE|HOST|PORT|NAME|USER|PASSWORD)['\"]\s*:")
_DB_FILE = re.compile(r"postgres|clickhouse|DATABASES?\b|DATABASE_URL|psql|5432|8123", re.I)
_ENV_NAMES = re.compile(
    r"^(DATABASE_URL|TEST_DATABASE_URL|DB_|PG|POSTGRES|CLICKHOUSE|CH_|SQLALCHEMY_DATABASE|DJANGO_)",
    re.I,
)
_SKIP_PROBE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    "site-packages",
    ".idea",
    ".vscode",
    "static",
    "media",
    "vendor",
    "target",
    ".next",
    "coverage",
}
_KV_LINE = re.compile(
    r"^\s*(?:export\s+|-\s+)?[\"']?(?P<key>[A-Za-z_][\w.-]*)[\"']?\s*[:=]\s*[\"']?(?P<val>[^\"'#\n,]+)"
)
_KV_ROLES = {
    "host": (
        "host",
        "hostname",
        "db_host",
        "database_host",
        "pghost",
        "postgres_host",
        "postgresql_host",
        "clickhouse_host",
        "ch_host",
        "server",
    ),
    "port": (
        "port",
        "db_port",
        "database_port",
        "pgport",
        "postgres_port",
        "postgresql_port",
        "clickhouse_port",
        "ch_port",
    ),
    "name": (
        "database",
        "dbname",
        "db_name",
        "database_name",
        "db",
        "pgdatabase",
        "postgres_db",
        "postgres_database",
        "clickhouse_db",
        "clickhouse_database",
        "ch_database",
    ),
    "user": (
        "user",
        "username",
        "db_user",
        "database_user",
        "pguser",
        "postgres_user",
        "clickhouse_user",
        "ch_user",
    ),
    "password": (
        "password",
        "db_password",
        "database_password",
        "pgpassword",
        "postgres_password",
        "clickhouse_password",
        "ch_password",
        "pass",
    ),
}
_KV_ROLE_OF = {alias: role for role, aliases in _KV_ROLES.items() for alias in aliases}
_ENGINE_PG = re.compile(r"postgres|psql|\bpg\b|pg_|5432", re.I)
_ENGINE_CH = re.compile(r"clickhouse|\bch_|8123|9000", re.I)
_OTHER_SERVICE = re.compile(r"redis|rabbit|amqp|kafka|memcache|elastic|mongo|smtp|s3|minio", re.I)
_KV_WINDOW = 14
_ENV_DEFAULT = re.compile(
    r"(?:getenv|environ\.get|environ\[|env|config|settings)\(\s*[\"']([A-Za-z_][\w]*)[\"']"
    r"(?:\s*,\s*(?:default\s*=\s*)?[\"']?([^\"'()]*)[\"']?)?\s*\)?"
)
_KV_BASE_WORDS = {
    "host": ("hostname", "host", "server"),
    "port": ("port",),
    "name": ("database", "dbname", "db", "name"),
    "user": ("username", "user"),
    "password": ("password", "pass"),
}
_YAML_PARENT = re.compile(r"^(\s*)([\w.-]+)\s*:\s*[{&]?\s*[\w-]*\s*$")
_KV_INDENT = re.compile(r"^(\s*)")
_LAYER_MARKERS = (
    ("Django ORM", re.compile(r"(^|/)manage\.py$|(^|/)settings\.py$")),
    ("SQLAlchemy", re.compile(r"sqlalchemy", re.I)),
    ("Alembic migrations", re.compile(r"(^|/)alembic\.ini$|(^|/)alembic/")),
    ("Rails ActiveRecord", re.compile(r"(^|/)config/database\.yml$|(^|/)app/models/.*\.rb$")),
    ("Prisma", re.compile(r"schema\.prisma$")),
    ("Knex", re.compile(r"knexfile\.[jt]s$")),
    ("TypeORM", re.compile(r"ormconfig\.|typeorm", re.I)),
    ("Sequelize", re.compile(r"sequelize", re.I)),
    ("Drizzle", re.compile(r"drizzle\.config\.")),
    ("ClickHouse client code", re.compile(r"clickhouse", re.I)),
    ("SQL files", re.compile(r"\.sql$")),
)
_MIGRATION_PATH = re.compile(r"(^|/)migrations?(/|$)|(^|/)alembic(/|$)|(^|/)db/migrate(/|$)")
_PY_PG_RUNNER = r"""
import sys
url, query = sys.argv[1], sys.argv[2]
tab = len(sys.argv) > 3 and sys.argv[3] == "tab"
# psql's own commands mean nothing to the server; the script is otherwise sent
# as psql would send it, one statement at a time.
query = "\n".join(l for l in query.splitlines() if not l.lstrip().startswith("\\"))

def statements(text):
    out, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "'" or c == '"':
            j = i + 1
            while j < n:
                if text[j] == c and not (j + 1 < n and text[j + 1] == c):
                    break
                j += 2 if text[j] == c else 1
            cur.append(text[i:j + 1]); i = j + 1; continue
        if c == "$":
            import re
            m = re.match(r"\$[A-Za-z_]*\$", text[i:])
            if m:
                end = text.find(m.group(0), i + len(m.group(0)))
                end = n if end < 0 else end + len(m.group(0))
                cur.append(text[i:end]); i = end; continue
        if text.startswith("--", i):
            end = text.find("\n", i); end = n if end < 0 else end
            i = end; continue
        if c == ";":
            piece = "".join(cur).strip()
            if piece:
                out.append(piece)
            cur = []; i += 1; continue
        cur.append(c); i += 1
    piece = "".join(cur).strip()
    if piece:
        out.append(piece)
    return out

def show(names, rows):
    if tab:
        for row in rows:
            print("\t".join("NULL" if v is None else str(v) for v in row))
        return
    if names:
        print(" | ".join(names))
    for row in rows:
        print(" | ".join(str(v) for v in row))

parts = statements(query)
try:
    try:
        import psycopg
        conn = psycopg.connect(url, connect_timeout=8, autocommit=True)
    except ImportError:
        import psycopg2 as psycopg
        conn = psycopg.connect(url, connect_timeout=8)
        conn.autocommit = True
except ImportError:
    import asyncio
    import asyncpg

    async def run():
        c = await asyncpg.connect(url, timeout=8)
        try:
            for statement in parts:
                try:
                    rows = await c.fetch(statement)
                except Exception as error:
                    print("ERROR: %s" % error)
                    try:
                        await c.execute("ROLLBACK")
                    except Exception:
                        pass
                    return 3
                show(list(rows[0].keys()) if rows else [], [tuple(r.values()) for r in rows])
        finally:
            await c.close()
        return 0
    sys.exit(asyncio.run(run()))
cur = conn.cursor()
for statement in parts:
    try:
        cur.execute(statement)
    except Exception as error:
        print("ERROR: %s" % error)
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        sys.exit(3)
    if cur.description:
        show([d[0] for d in cur.description], cur.fetchall())
    elif not tab:
        print(getattr(cur, "statusmessage", "") or "")
"""
_PY_CH_RUNNER = r"""
import sys
host, port, user, password, database, query = sys.argv[1:7]
port = int(port)
statements = [s for s in query.split(";") if s.strip()]
try:
    import clickhouse_connect
    client = clickhouse_connect.get_client(host=host, port=port if port != 9000 else 8123, username=user or "default",
                                           password=password, database=database)
    for statement in statements:
        result = client.query(statement)
        if result.column_names:
            print(" | ".join(result.column_names))
        for row in result.result_rows:
            print(" | ".join(str(v) for v in row))
except ImportError:
    from clickhouse_driver import Client
    client = Client(host=host, port=port if port != 8123 else 9000, user=user or "default", password=password,
                    database=database, connect_timeout=8)
    for statement in statements:
        rows, columns = client.execute(statement, with_column_types=True)
        print(" | ".join(name for name, _ in columns))
        for row in rows:
            print(" | ".join(str(v) for v in row))
"""

def _config_files(root: str, deadline: float, cap: int = 60) -> list[str]:
    found: list[str] = []
    for current, dirs, files in os.walk(root):
        rel = os.path.relpath(current, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_PROBE_DIRS and not d.startswith("."))
        if depth >= 6 or time.monotonic() > deadline:
            dirs[:] = []
        for name in files:
            settings_like = name in _CONFIG_NAMES or name.startswith(".env") or (
                name.endswith((".ini", ".cfg", ".toml", ".yaml", ".yml", ".json"))
                and "config" in name.lower()
            )
            if settings_like:
                found.append("" if rel == "." else rel + "/" + name)
                if len(found) >= cap:
                    return found
    return found

def _reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _django_databases(text: str) -> list[tuple[str, dict[str, str]]]:
    out: list[tuple[str, dict[str, str]]] = []
    match = re.search(r"DATABASES\s*=\s*(\{.*?\n\})", text, re.S)
    if not match:
        return out
    try:
        literal = ast.literal_eval(match.group(1))
    except Exception:
        keys: dict[str, str] = {}
        for key in ("ENGINE", "NAME", "USER", "PASSWORD", "HOST", "PORT"):
            found = re.search(r"['\"]%s['\"]\s*:\s*['\"]?([^'\",\n]*)['\"]?" % key, match.group(1))
            if found:
                keys[key] = found.group(1).strip()
        return [("default", keys)] if keys else out
    if isinstance(literal, dict):
        for alias, conf in literal.items():
            if isinstance(conf, dict):
                out.append((str(alias), {k: str(v) for k, v in conf.items() if not isinstance(v, dict)}))
    return out

def _kv_value(raw: str, line: str) -> str:
    value = raw.strip()
    if "(" not in value and not value.startswith(("os.", "env")):
        return value
    match = _ENV_DEFAULT.search(line)
    if not match:
        return ""
    name, default = match.group(1), (match.group(2) or "").strip()
    return os.environ.get(name) or default

def _kv_prefix(key: str, role: str) -> str:
    lowered = key.lower()
    for word in _KV_BASE_WORDS[role]:
        if lowered == word:
            return ""
        if lowered.endswith(word):
            return lowered[: -len(word)].rstrip("_.-")
    return lowered

def _pg_url(conf: dict[str, str]) -> str:
    user = conf.get("USER") or "postgres"
    password = conf.get("PASSWORD") or ""
    host = conf.get("HOST") or "localhost"
    port = conf.get("PORT") or "5432"
    name = conf.get("NAME") or "postgres"
    auth = urllib.parse.quote(user, safe="") + (
        (":" + urllib.parse.quote(password, safe="")) if password else ""
    )
    return f"postgresql://{auth}@{host}:{port}/{name}"

def _kv_databases(text: str, path: str) -> list["Database"]:
    lines = text.splitlines()
    entries: list[tuple[int, str, str, str]] = []
    parents: list[tuple[int, str]] = []
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(_KV_INDENT.match(line).group(1).expandtabs(4))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        parent = _YAML_PARENT.match(line)
        match = _KV_LINE.match(line)
        if parent and (not match or not match.group("val").strip() or match.group("val").strip() in ("{", "&default")):
            parents.append((indent, parent.group(2)))
            continue
        if not match:
            continue
        key = match.group("key")
        lowered = key.lower()
        role = (
            _KV_ROLE_OF.get(lowered)
            or _KV_ROLE_OF.get(lowered.rsplit(".", 1)[-1])
            or _KV_ROLE_OF.get(lowered.rsplit("_", 1)[-1] if "_" in lowered else "")
        )
        if not role:
            continue
        value = _kv_value(match.group("val"), line)
        if not value or "$" in value or "<%" in value or "{{" in value or value.lower() in ("null", "none", "~"):
            continue
        full = ".".join([k for _, k in parents] + [key])
        entries.append((number, role, value, _kv_prefix(full, role)))
    found: list[Database] = []
    for number, role, value, prefix in entries:
        if role != "host":
            continue
        lo, hi = number - _KV_WINDOW, number + _KV_WINDOW
        window = "\n".join(lines[max(0, lo - 1) : hi])
        nearby = {"host": value}
        same = [e for e in entries if lo <= e[0] <= hi and e[1] != "host" and e[3] == prefix]
        loose = [e for e in entries if lo <= e[0] <= hi and e[1] != "host" and e[3] != prefix and not e[3]]
        hosted = {e[3] for e in entries if e[1] == "host" and lo <= e[0] <= hi}
        others = [
            e
            for e in entries
            if lo <= e[0] <= hi
            and e[1] != "host"
            and e[3]
            and e[3] != prefix
            and e[3] not in hosted
            and not _OTHER_SERVICE.search(e[3])
        ]
        for _other, orole, ovalue, _oprefix in (
            sorted(same, key=lambda e: abs(e[0] - number))
            + sorted(loose, key=lambda e: abs(e[0] - number))
            + sorted(others, key=lambda e: abs(e[0] - number))
        ):
            if orole not in nearby:
                nearby[orole] = ovalue
        marker = (prefix + " " + value).lower()
        if "clickhouse" in marker or re.search(r"(^|[_.-])ch([_.-]|$)", prefix):
            engine = "clickhouse"
        elif re.search(r"postgres|pg", marker) or nearby.get("port") == "5432":
            engine = "postgresql"
        elif _OTHER_SERVICE.search(marker):
            continue
        elif _ENGINE_CH.search(window) and "clickhouse" in window.lower() and not _ENGINE_PG.search(window):
            engine = "clickhouse"
        elif _ENGINE_PG.search(window) and not _OTHER_SERVICE.search(window):
            engine = "postgresql"
        elif os.path.basename(path) in ("database.yml", "database.yaml", "knexfile.js", "knexfile.ts"):
            engine = "postgresql"
        else:
            continue
        try:
            port = int(re.sub(r"\D", "", nearby.get("port") or "") or (5432 if engine == "postgresql" else 8123))
        except ValueError:
            port = 5432 if engine == "postgresql" else 8123
        conf = {
            "HOST": value,
            "PORT": str(port),
            "USER": nearby.get("user") or "",
            "PASSWORD": nearby.get("password") or "",
            "NAME": nearby.get("name") or "",
        }
        label = f"{path}:{number}"
        if engine == "postgresql":
            db = Database(
                "postgresql",
                label,
                url=_pg_url(conf),
                host=value,
                port=port,
                user=conf["USER"],
                password=conf["PASSWORD"],
                name=conf["NAME"] or "postgres",
            )
        else:
            db = Database(
                "clickhouse",
                label,
                host=value,
                port=port,
                user=conf["USER"],
                password=conf["PASSWORD"],
                name=conf["NAME"] or "default",
            )
        if not any(d.engine == db.engine and d.host == db.host and d.port == db.port and d.name == db.name for d in found):
            found.append(db)
    return found

def split_statements(script: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    quote = ""
    i = 0
    text = script
    while i < len(text):
        ch = text[i]
        if quote:
            current.append(ch)
            if ch == quote and not (i + 1 < len(text) and text[i + 1] == quote):
                quote = ""
            elif ch == quote:
                current.append(text[i + 1])
                i += 1
        elif ch in ("'", '"', "`"):
            quote = ch
            current.append(ch)
        elif ch == "-" and text[i : i + 2] == "--":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            current.append(text[i:end])
            i = end
            continue
        elif ch == ";":
            piece = "".join(current).strip()
            if piece:
                out.append(piece)
            current = []
        else:
            current.append(ch)
        i += 1
    piece = "".join(current).strip()
    if piece:
        out.append(piece)
    return out or [script]

def work_done(summary: str) -> str:
    """What a statement cost the server, from the summary it sent with the reply.

    Said on every result, because a bound on how much work a statement does
    is a property of the statement that no amount of reading it settles: a
    limit does not stop a read that runs on several threads, and a grouping
    reads every row it groups whatever it keeps.  Only the count the server
    reports says what happened.
    """
    try:
        data = json.loads(summary or "{}")
    except (ValueError, TypeError):
        return ""
    def number(key: str) -> int:
        try:
            return int(data.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    read_rows, read_bytes = number("read_rows"), number("read_bytes")
    written = number("written_rows")
    seconds = number("elapsed_ns") / 1e9
    parts = []
    if read_rows or read_bytes or not written:
        parts.append("read %s rows (%s)" % (format(read_rows, ","), human_bytes(read_bytes)))
    if written:
        parts.append("wrote %s rows" % format(written, ","))
    if not parts:
        return ""
    return "\n-- the server %s in %.2fs" % (" and ".join(parts), seconds)


def human_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d %s" % (size, unit)) if unit == "B" else ("%.1f %s" % (size, unit))
        size /= 1024
    return "%d B" % count


class Database:
    def __init__(
        self,
        engine: str,
        label: str,
        url: str = "",
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        name: str = "",
    ) -> None:
        self.engine = engine
        self.label = label
        self.url = url
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.name = name
        self.ok = False
        self.note = ""

    def describe(self) -> str:
        where = self.url if self.url else f"{self.host}:{self.port} db={self.name} user={self.user}"
        status = self.note or ("reachable" if self.ok else "not verified")
        return f"{self.engine} [{self.label}] {where} -- {status}"

    def run(self, query: str, database: str = "", timeout: float = 60.0, cwd: str = ".",
            tab: bool = False) -> tuple[int, str]:
        """Run `query`.  With `tab`, PostgreSQL rows come back one per line,
        cells split by tabs and NULL spelled out, with nothing else printed."""
        if self.engine == "postgresql":
            url = self.url
            if database:
                url = re.sub(r"/[^/?]*(\?|$)", "/" + database + r"\1", url, count=1)
            if shutil.which("psql"):
                shape = (["-q", "-A", "-t", "-F", "\t", "-P", "null=NULL"] if tab else [])
                return run_piped(
                    ["psql", url, "-X", "-v", "ON_ERROR_STOP=1", "-P", "pager=off"] + shape
                    + ["-f", "-"],
                    cwd,
                    timeout,
                    stdin_text=query,
                    extra_env={"PGCONNECT_TIMEOUT": "8"},
                )
            return run_piped([sys.executable, "-c", _PY_PG_RUNNER, url, query]
                             + (["tab"] if tab else []), cwd, timeout)
        if self.engine == "clickhouse":
            name = database or self.name or "default"
            if shutil.which("clickhouse-client") or shutil.which("clickhouse"):
                exe = ["clickhouse-client"] if shutil.which("clickhouse-client") else ["clickhouse", "client"]
                argv = exe + [
                    "--host",
                    self.host or "localhost",
                    "--port",
                    str(self.port or 9000),
                    "--database",
                    name,
                    "--multiquery",
                    "--format",
                    "PrettyCompactMonoBlock",
                ]
                if ROLLBACK_SQL:
                    argv += ["--max_execution_time", str(SQL_STATEMENT_TIMEOUT_SEC)]
                if self.user:
                    argv += ["--user", self.user]
                if self.password:
                    argv += ["--password", self.password]
                code, out = run_piped(argv, cwd, timeout, stdin_text=query)
                if code == 0 or "Connection refused" not in out:
                    return code, out
            code, out = self.http(query, name, timeout)
            if code == 1 and re.search(r"URLError|Connection refused|Name or service", out):
                argv = [
                    sys.executable,
                    "-c",
                    _PY_CH_RUNNER,
                    self.host or "localhost",
                    str(self.port or 9000),
                    self.user,
                    self.password,
                    name,
                    query,
                ]
                code2, out2 = run_piped(argv, cwd, timeout)
                if code2 == 0 or "No module named" not in out2:
                    return code2, out2
            return code, out
        return 1, f"no runner for engine {self.engine}"

    def http(self, query: str, database: str, timeout: float,
             fmt: str = "PrettyCompactMonoBlock") -> tuple[int, str]:
        port = self.port if self.port and self.port != 9000 else 8123
        # The server holds the reply until the statement has finished, so the
        # summary it sends with it counts everything the statement did
        # rather than whatever had been done when the first bytes went out.
        params = {"database": database, "default_format": fmt,
                  "wait_end_of_query": "1"}
        if ROLLBACK_SQL:
            params["max_execution_time"] = str(SQL_STATEMENT_TIMEOUT_SEC)
        url = f"http://{self.host or 'localhost'}:{port}/?{urllib.parse.urlencode(params)}"
        headers = {}
        if self.user:
            headers["X-ClickHouse-User"] = self.user
        if self.password:
            headers["X-ClickHouse-Key"] = self.password
        statements = split_statements(query)
        outputs: list[str] = []
        code = 0
        deadline = time.monotonic() + timeout
        for statement in statements:
            left = max(1.0, deadline - time.monotonic())
            until = time.monotonic() + left
            try:
                request = urllib.request.Request(url, data=statement.encode("utf-8"), headers=headers)
                with urllib.request.urlopen(request, timeout=left) as response:
                    body = read_within(response, until).decode("utf-8", "replace")
                    body = body.rstrip() + work_done(response.headers.get("X-ClickHouse-Summary", ""))
            except urllib.error.HTTPError as error:
                try:
                    body = error.read().decode("utf-8", "replace")
                except Exception:
                    body = str(error)
                code = error.code
            except Exception as error:
                body, code = f"{type(error).__name__}: {error}", 1
            if len(statements) > 1:
                outputs.append(f"-- {one_line(statement)[:80]}\n{body.rstrip()}")
            else:
                outputs.append(body)
            if code:
                break
        return code, "\n".join(outputs)

def probe_databases(root: str, budget: float = PROBE_BUDGET_SEC) -> tuple[list[Database], str]:
    deadline = time.monotonic() + budget
    lines: list[str] = []
    found: list[Database] = []
    tools = [n for n in ("psql", "pg_isready", "pg_dump", "clickhouse-client", "clickhouse", "curl") if shutil.which(n)]
    lines.append("Client tools on PATH: " + (", ".join(tools) or "none"))
    envs = sorted(k for k in os.environ if _ENV_NAMES.match(k))
    if envs:
        lines.append("Environment: " + ", ".join(f"{k}={os.environ[k][:80]}" for k in envs[:12]))
    configs = _config_files(root, deadline)
    snippets: list[str] = []
    for path in configs:
        if time.monotonic() > deadline:
            break
        try:
            with open(os.path.join(root, path), "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read(200_000)
        except OSError:
            continue
        hits = []
        if _DB_FILE.search(text):
            hits = [row.strip() for row in text.splitlines() if _CONFIG_LINE.search(row) or _DJANGO_KEYS.search(row)]
        if hits:
            snippets.append(f"  {path}: " + " | ".join(h[:100] for h in hits[:8]))
        for alias, conf in _django_databases(text):
            engine = (conf.get("ENGINE") or "").lower()
            if "postgres" in engine or "psycopg" in engine:
                try:
                    port = int(conf.get("PORT") or 5432)
                except ValueError:
                    port = 5432
                found.append(
                    Database(
                        "postgresql",
                        f"{path}:{alias}",
                        url=_pg_url(conf),
                        host=conf.get("HOST") or "",
                        port=port,
                        user=conf.get("USER") or "",
                        password=conf.get("PASSWORD") or "",
                        name=conf.get("NAME") or "",
                    )
                )
                match = re.search(r"'TEST'\s*:\s*\{[^}]*'NAME'\s*:\s*'([^']+)'", text)
                if match:
                    lines.append(f"  test database name for {alias}: {match.group(1)}")
            elif "clickhouse" in engine:
                try:
                    port = int(conf.get("PORT") or 9000)
                except ValueError:
                    port = 9000
                found.append(
                    Database(
                        "clickhouse",
                        f"{path}:{alias}",
                        host=conf.get("HOST") or "localhost",
                        port=port,
                        user=conf.get("USER") or "",
                        password=conf.get("PASSWORD") or "",
                        name=conf.get("NAME") or "",
                    )
                )
        for match in re.finditer(r"(postgres(?:ql)?://[^\s'\"<>]+)", text):
            url = match.group(1).rstrip(",;)")
            if not any(d.url == url for d in found):
                parsed = urllib.parse.urlparse(url)
                found.append(
                    Database(
                        "postgresql",
                        path,
                        url=url,
                        host=parsed.hostname or "",
                        port=parsed.port or 5432,
                        user=parsed.username or "",
                        password=parsed.password or "",
                        name=(parsed.path or "/").lstrip("/"),
                    )
                )
        for match in re.finditer(
            r"(clickhouse(?:s)?://[^\s'\"<>]+|https?://[\w.-]*clickhouse[\w.-]*:\d+)", text, re.I
        ):
            url = match.group(1).rstrip(",;)")
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname and not any(d.engine == "clickhouse" and d.host == parsed.hostname for d in found):
                found.append(
                    Database(
                        "clickhouse",
                        path,
                        host=parsed.hostname,
                        port=parsed.port or 8123,
                        user=parsed.username or "",
                        password=parsed.password or "",
                        name=(parsed.path or "/").lstrip("/"),
                    )
                )
    for path in configs:
        if time.monotonic() > deadline or len(found) >= 6:
            break
        if any(d.label.startswith(path) for d in found):
            continue
        try:
            with open(os.path.join(root, path), "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read(200_000)
        except OSError:
            continue
        for db in _kv_databases(text, path):
            if not any(
                d.engine == db.engine and d.host == db.host and d.port == db.port and d.name == db.name for d in found
            ):
                found.append(db)
    if snippets:
        lines.append("Connection settings seen in the repository:\n" + "\n".join(snippets[:12]))
    for name in ("DATABASE_URL", "TEST_DATABASE_URL", "SQLALCHEMY_DATABASE_URI"):
        url = os.getenv(name) or ""
        if url.startswith("postgres") and not any(d.url == url for d in found):
            parsed = urllib.parse.urlparse(url)
            found.append(
                Database(
                    "postgresql",
                    "env " + name,
                    url=url,
                    host=parsed.hostname or "",
                    port=parsed.port or 5432,
                    user=parsed.username or "",
                    password=parsed.password or "",
                    name=(parsed.path or "/").lstrip("/"),
                )
            )
        if url.startswith("clickhouse") or (url.startswith("http") and "clickhouse" in (name + url).lower()):
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname:
                found.append(
                    Database(
                        "clickhouse",
                        "env " + name,
                        host=parsed.hostname,
                        port=parsed.port or 8123,
                        user=parsed.username or "",
                        password=parsed.password or "",
                        name=(parsed.path or "/").lstrip("/"),
                    )
                )
    if os.getenv("PGHOST") and not any(d.engine == "postgresql" for d in found):
        conf = {
            "HOST": os.getenv("PGHOST") or "",
            "PORT": os.getenv("PGPORT") or "5432",
            "USER": os.getenv("PGUSER") or "",
            "PASSWORD": os.getenv("PGPASSWORD") or "",
            "NAME": os.getenv("PGDATABASE") or "postgres",
        }
        found.append(
            Database(
                "postgresql",
                "env PG*",
                url=_pg_url(conf),
                host=conf["HOST"],
                port=int(conf["PORT"] or 5432),
                user=conf["USER"],
                password=conf["PASSWORD"],
                name=conf["NAME"],
            )
        )
    if os.getenv("CLICKHOUSE_HOST") and not any(d.engine == "clickhouse" for d in found):
        found.append(
            Database(
                "clickhouse",
                "env CLICKHOUSE_*",
                host=os.getenv("CLICKHOUSE_HOST") or "",
                port=int(os.getenv("CLICKHOUSE_PORT") or 8123),
                user=os.getenv("CLICKHOUSE_USER") or "",
                password=os.getenv("CLICKHOUSE_PASSWORD") or "",
                name=os.getenv("CLICKHOUSE_DB") or "",
            )
        )
    hosts: list[str] = []
    for host in ("postgres", "postgresql", "db", "database", "pg", "localhost", "127.0.0.1"):
        if time.monotonic() > deadline:
            break
        if _reachable(host, 5432, 0.7):
            hosts.append(f"{host}:5432 (postgresql)")
    for host in ("clickhouse", "ch", "clickhouse-server", "localhost", "127.0.0.1"):
        if time.monotonic() > deadline:
            break
        for port in (8123, 9000):
            if _reachable(host, port, 0.7):
                hosts.append(f"{host}:{port} (clickhouse)")
    if hosts:
        lines.append("Open database ports: " + ", ".join(hosts))
        mentions = any("clickhouse" in s.lower() for s in snippets)
        if not any(d.engine == "clickhouse" for d in found):
            for entry in hosts:
                if "clickhouse" in entry and (":8123" in entry or mentions):
                    host, port = entry.split(" ")[0].split(":")
                    found.append(Database("clickhouse", "open port", host=host, port=int(port), name="default"))
                    break
    if len(found) > 8:
        found = found[:8]
    verified: list[Database] = []
    for db in found:
        if time.monotonic() > deadline:
            db.note = "not tried (probe budget spent)"
            verified.append(db)
            continue
        room = max(2.0, min(10.0, deadline - time.monotonic()))
        if db.engine == "postgresql":
            code, out = db.run(
                "SELECT current_database() AS db, current_user AS usr, version();"
                " SELECT count(*) AS user_tables FROM information_schema.tables"
                " WHERE table_schema NOT IN ('pg_catalog','information_schema');",
                timeout=room,
                cwd=root,
            )
        else:
            code, out = db.run("SELECT version(), currentDatabase()", timeout=room, cwd=root)
        db.ok = code == 0
        db.note = ("answers: " if db.ok else "failed: ") + one_line(out)[:220]
        verified.append(db)
    for entry in hosts:
        if time.monotonic() > deadline:
            break
        host_port, engine_name = entry.split(" ", 1)
        engine = "clickhouse" if "clickhouse" in engine_name else "postgresql"
        if any(d.engine == engine and d.ok for d in verified):
            continue
        host, port = host_port.split(":")
        if engine == "clickhouse":
            fallback = Database(
                "clickhouse",
                "open port",
                host=host,
                port=int(port),
                user=os.getenv("CLICKHOUSE_USER") or "",
                password=os.getenv("CLICKHOUSE_PASSWORD") or "",
                name=os.getenv("CLICKHOUSE_DB") or "default",
            )
            code, out = fallback.run("SELECT version(), currentDatabase()", timeout=6.0, cwd=root)
        else:
            conf = {
                "HOST": host,
                "PORT": port,
                "USER": os.getenv("PGUSER") or "postgres",
                "PASSWORD": os.getenv("PGPASSWORD") or "",
                "NAME": os.getenv("PGDATABASE") or "postgres",
            }
            fallback = Database(
                "postgresql",
                "open port",
                url=_pg_url(conf),
                host=host,
                port=int(port),
                user=conf["USER"],
                password=conf["PASSWORD"],
                name=conf["NAME"],
            )
            code, out = fallback.run("SELECT current_database(), current_user", timeout=6.0, cwd=root)
        fallback.ok = code == 0
        fallback.note = ("answers: " if fallback.ok else "failed: ") + one_line(out)[:160]
        if not any(d.engine == fallback.engine and d.host == fallback.host and d.port == fallback.port for d in verified):
            verified.append(fallback)
    if verified:
        lines.append("Databases:\n" + "\n".join("  " + d.describe() for d in verified))
    else:
        lines.append("Databases: none found from configuration; look for the connection settings the app uses.")
    return verified, "\n".join(lines)

def query_layers(files: set[str] | list[str]) -> str:
    rows: list[str] = []
    for name, pattern in _LAYER_MARKERS:
        hits = [p for p in files if pattern.search(p)]
        if hits:
            rows.append(f"{name} ({hits[0]})")
    migrations = [p for p in files if _MIGRATION_PATH.search(p)]
    if migrations:
        rows.append(f"{len(migrations)} migration files, e.g. {migrations[-1]}")
    return "; ".join(rows[:8])

CLICKHOUSE_READ_HEADS = (
    "select", "with", "explain", "show", "describe", "desc", "exists", "check",
)
# A database that belongs to the run.  Anything may be written inside it and
# nothing outside it.  It exists because a bound on how much work a statement
# does cannot be checked against tables that hold nothing -- every statement
# reads nothing from an empty table, the unbounded ones included -- so there
# has to be somewhere to build data of the right shape and size, and that
# somewhere must not be anything the application or its tests will read.
SCRATCH_DATABASE = "agent_scratch"
# The connections the run has written a scratch database on, so that it can be
# taken away again when the run ends.
SCRATCH_MADE: list = []
_CH_IDENT = r'(?:`[^`]+`|"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)'
_CH_NAME = r"(?P<first>%s)(?:\s*\.\s*(?P<second>%s))?" % (_CH_IDENT, _CH_IDENT)
# Each form a writing statement takes, and what it writes to.  A form not
# listed here is not run, whatever it names.
_CH_WRITE_FORMS = (
    (re.compile(r"create\s+database\s+(?:if\s+not\s+exists\s+)?" + _CH_NAME, re.I), "database"),
    (re.compile(r"create\s+(?:or\s+replace\s+)?(?:table|view)\s+(?:if\s+not\s+exists\s+)?"
                + _CH_NAME, re.I), "table"),
    (re.compile(r"insert\s+into\s+(?:table\s+)?(?!function\b)" + _CH_NAME, re.I), "table"),
    (re.compile(r"drop\s+database\s+(?:if\s+exists\s+)?" + _CH_NAME, re.I), "database"),
    (re.compile(r"drop\s+(?:table|view)\s+(?:if\s+exists\s+)?" + _CH_NAME, re.I), "table"),
    (re.compile(r"truncate\s+(?:table\s+)?(?:if\s+exists\s+)?" + _CH_NAME, re.I), "table"),
    (re.compile(r"optimize\s+table\s+" + _CH_NAME, re.I), "table"),
    (re.compile(r"alter\s+table\s+" + _CH_NAME, re.I), "table"),
    (re.compile(r"delete\s+from\s+" + _CH_NAME, re.I), "table"),
)
# Writes that can reach past the database they name: a view that feeds
# another table, a write through a table function to a file or a URL.
_CH_REACHES_OUT = re.compile(r"\bmaterialized\s+view\b|\binsert\s+into\s+function\b|"
                             r"\binto\s+outfile\b|\bdictionary\b|"
                             # A table whose engine forwards its rows elsewhere: a
                             # write to it inside agent_scratch lands outside it.
                             r"\bengine\s*=\s*(?:distributed|merge|buffer|url|file|s3|s3queue|"
                             r"hdfs|mysql|postgresql|mongodb|kafka|rabbitmq|nats|jdbc|odbc|"
                             r"executable|executablepool|redis|sqlite|azureblobstorage)\b|"
                             r"\bas\s+(?:remote|remotesecure|cluster|clusterallreplicas|url|s3|"
                             r"file|hdfs|mysql|postgresql|mongodb|jdbc|odbc)\s*\(", re.I)
_SQL_LEADING_NOISE = re.compile(r"^(?:\s+|--[^\n]*\n?|/\*.*?\*/|\()+", re.S)

def rolled_back_script(engine: str, query: str, timeout_sec: int) -> tuple[str, str]:
    body = (query or "").strip()
    if engine == "postgresql":
        script = (
            "\\set ON_ERROR_ROLLBACK on\n"
            "BEGIN;\n"
            "SET LOCAL statement_timeout = %d;\n"
            "%s\n;\n"
            "ROLLBACK;\n" % (timeout_sec * 1000, body.rstrip(";"))
        )
        return script, "transaction rolled back, statement_timeout %ds" % timeout_sec
    if engine == "clickhouse":
        return body, "reads anywhere, writes only in %s, max_execution_time %ds" % (
            SCRATCH_DATABASE, timeout_sec)
    return body, ""

def clickhouse_read_only(query: str) -> str:
    head = (query or "").strip().lstrip("(").split(None, 1)
    word = head[0].lower().rstrip(";") if head else ""
    return "" if word in CLICKHOUSE_READ_HEADS else (word or "(empty)")


def _unquote(name: str | None) -> str:
    return (name or "").strip().strip("`\"")


def clickhouse_write_refusal(query: str, database: str = "") -> str:
    """Why this script may not run on ClickHouse, or "" if every statement may.

    Every statement is asked, not only the first: a script is run statement by
    statement, so a harmless one at the front says nothing about what follows
    it.  A statement that reads runs anywhere.  One that writes runs only when
    everything it writes to is inside the run's own database.
    """
    for statement in split_statements(query or "") or [query or ""]:
        body = _SQL_LEADING_NOISE.sub("", statement).strip().rstrip(";")
        if not body:
            continue
        word = body.split(None, 1)[0].lower()
        if word in CLICKHOUSE_READ_HEADS:
            continue
        if _CH_REACHES_OUT.search(body):
            return "%s reaches outside the database it names" % one_line(body)[:60]
        for form, kind in _CH_WRITE_FORMS:
            found = form.match(body)
            if not found:
                continue
            first, second = _unquote(found.group("first")), _unquote(found.group("second"))
            if kind == "database":
                owner = first
            elif second:
                owner = first
            else:
                # An unqualified name goes wherever the connection points.
                owner = _unquote(database)
            if owner != SCRATCH_DATABASE:
                return "%s writes to %s, outside %s" % (word, owner or "the connection's database",
                                                          SCRATCH_DATABASE)
            break
        else:
            return word
    return ""

# -- worlds: a statement run on rows built for it ------------------------------

WORLD_CHECK = flag("RIDGES_WORLD_CHECK", "0")
# What a finish needs left before it is held for a world: enough to build
# one, read what came back, and change the code if it came back wrong.
WORLD_MIN_LEFT_SEC = 420.0
WORLD_MIN_MONEY_SHARE = 0.25
WORLD_DIFFERS_MIN_LEFT_SEC = 240.0
WORLD_ROWS_SHOWN = 40
WORLD_BEGIN = "<<agent-world>>"
WORLD_END = "<<agent-world-end>>"
# Engines that keep their own rows.  A copy of any other table's structure
# would carry its engine with it, and with that where its rows go.
_SCRATCH_COPY = re.compile(
    r"(?P<head>create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?"
    r"`?%s`?\s*\.\s*\S+\s+as\s+)(?P<source>[A-Za-z_`\"][\w`\".]*)\s*$" % SCRATCH_DATABASE,
    re.I | re.S)
_CH_OWN_ROWS = re.compile(r"MergeTree$|^(?:Memory|Log|TinyLog|StripeLog|Set|Join)$")
_SHADOW_AFTER = frozenset(("from", "join", "into", "table", "update"))


def _sql_tokens(sql: str) -> list:
    """(start, end, kind, text) for each word, quoted name and mark outside strings and comments."""
    out = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch.isspace():
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end < 0 else end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
        elif ch == "$" and re.match(r"\$[A-Za-z_]*\$", sql[i:]):
            tag = re.match(r"\$[A-Za-z_]*\$", sql[i:]).group(0)
            end = sql.find(tag, i + len(tag))
            i = n if end < 0 else end + len(tag)
        elif ch in "\"`":
            end = sql.find(ch, i + 1)
            end = n if end < 0 else end
            out.append((i, end + 1, "name", sql[i + 1:end]))
            i = end + 1
        elif ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            out.append((i, j, "word", sql[i:j]))
            i = j
        else:
            out.append((i, i + 1, "mark", ch))
            i += 1
    return out


def shadow_tables(sql: str, mapping: dict, default: str) -> str:
    """`sql` with each reference to a table in `mapping` pointed at its stand-in.

    `mapping` is keyed by (database or schema, table), lower-cased and
    unquoted, and gives the text to put in the reference's place.  A qualified
    name is replaced wherever it stands; a bare one only where a table goes --
    after FROM, JOIN, INTO, TABLE or UPDATE -- and then as `default`.<name>, so
    a column that happens to share a table's name is left alone.  Strings and
    comments are never touched.
    """
    if not mapping:
        return sql
    tokens = _sql_tokens(sql)
    edits = []
    k = 0
    while k < len(tokens):
        start, end, kind, text = tokens[k]
        if kind in ("word", "name"):
            before = tokens[k - 1] if k else None
            after_dot = before is not None and before[2] == "mark" and before[3] == "."
            dotted = (k + 2 < len(tokens) and tokens[k + 1][2] == "mark" and tokens[k + 1][3] == "."
                      and tokens[k + 2][2] in ("word", "name"))
            if not after_dot and dotted:
                key = (text.lower(), tokens[k + 2][3].lower())
                if key in mapping:
                    edits.append((start, tokens[k + 2][1], mapping[key]))
                    k += 3
                    continue
            elif (not after_dot and not dotted and before is not None
                  and before[2] == "word" and before[3].lower() in _SHADOW_AFTER):
                key = ((default or "").lower(), text.lower())
                if key in mapping:
                    edits.append((start, end, mapping[key]))
        k += 1
    for start, end, text in reversed(edits):
        sql = sql[:start] + text + sql[end:]
    return sql


def split_table_name(name: str, default: str) -> tuple:
    parts = [p.strip().strip("`\"") for p in (name or "").split(".") if p.strip()]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return default, (parts[0] if parts else "")


def pg_ident(name: str) -> str:
    return '"%s"' % name.replace('"', '""')


def ch_ident(name: str) -> str:
    return "`%s`" % name.replace("`", "\\`")


def ch_literal(text: str) -> str:
    return "'%s'" % text.replace("\\", "\\\\").replace("'", "\\'")


def world_cell(text: str) -> str:
    """One cell as the comparison sees it: NULL, a number, a truth value, or its text."""
    cell = (text or "").strip()
    low = cell.lower()
    if low in ("null", "\\n", "none", "<null>"):
        return "NULL"
    if cell in ("''", '""'):
        return ""
    if len(cell) >= 2 and cell[0] == cell[-1] and cell[0] in "'\"":
        cell = cell[1:-1]
        low = cell.lower()
    if low in ("true", "t"):
        return "true"
    if low in ("false", "f"):
        return "false"
    try:
        number = float(cell)
    except ValueError:
        return cell
    if number != number or number in (float("inf"), float("-inf")):
        return cell
    return repr(int(number)) if number == int(number) and abs(number) < 1e15 else repr(round(number, 9))


def expected_rows(text: str) -> list:
    """The rows a world was expected to return, one per line, cells split on | or tab."""
    body = (text or "").strip()
    if not body or body.lower() in ("(no rows)", "no rows", "none", "empty", "(empty)"):
        return []
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line or set(line) <= set("-+|= "):
            continue
        if line.startswith("|") and line.endswith("|") and len(line) > 1:
            line = line[1:-1]
        cells = line.split("\t") if "\t" in line else line.split("|")
        rows.append(tuple(world_cell(c) for c in cells))
    return rows


def compare_world(returned: list, expected: list, ordered: bool) -> str:
    """"MATCHES", or "DIFFERS: ..." saying which rows are missing and which were not asked for."""
    if ordered:
        if returned == expected:
            return "MATCHES"
        for index, (seen, wanted) in enumerate(zip(returned, expected)):
            if seen != wanted:
                return ("DIFFERS: row %d is %s, expected %s"
                        % (index + 1, " | ".join(seen), " | ".join(wanted)))
        return ("DIFFERS: %d row(s) came back, %d expected" % (len(returned), len(expected)))
    have = collections.Counter(returned)
    want = collections.Counter(expected)
    if have == want:
        return "MATCHES"
    missing = list((want - have).elements())
    extra = list((have - want).elements())
    parts = []
    if missing:
        parts.append("expected but not returned: "
                     + "; ".join(" | ".join(r) for r in missing[:6]))
    if extra:
        parts.append("returned but not expected: "
                     + "; ".join(" | ".join(r) for r in extra[:6]))
    return "DIFFERS: " + " -- ".join(parts)


def tsv_cell(text: str) -> str:
    if text == "\\N":
        return "NULL"
    return (text.replace("\\t", "\t").replace("\\n", "\n")
            .replace("\\'", "'").replace("\\\\", "\\"))


def split_work(out: str) -> tuple:
    """(what a statement returned, the line saying what it cost the server)."""
    rows, work = [], ""
    for line in (out or "").split("\n"):
        if line.startswith("-- the server "):
            work = line
        else:
            rows.append(line)
    return "\n".join(rows).rstrip("\n"), work


class StatementLog:
    """What reached a database while a command ran, read from the server's own record.

    ClickHouse keeps every statement it ran, with the rows it read, in
    system.query_log; PostgreSQL keeps counts per statement in
    pg_stat_statements when the extension is there.  Either may be missing or
    closed to this user, and then it says so rather than guessing.
    """

    MARK = "agent-statement-log"

    def __init__(self, db: "Database", cwd: str) -> None:
        self.db = db
        self.cwd = cwd
        self.since = ""
        self.before: dict = {}
        self.note = ""

    def ask(self, sql: str, timeout: float) -> tuple:
        if self.db.engine == "clickhouse":
            code, out = self.db.http(sql, self.db.name or "default", timeout, fmt="TabSeparated")
            return code, split_work(out)[0]
        return self.db.run(sql, timeout=timeout, cwd=self.cwd, tab=True)

    def pg_counts(self, timeout: float) -> tuple:
        code, out = self.ask(
            "SELECT /* %s */ queryid, calls, rows, shared_blks_hit + shared_blks_read, "
            "regexp_replace(query, '\\s+', ' ', 'g') FROM pg_stat_statements "
            "WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())"
            % self.MARK, timeout)
        if code or "ERROR" in out[:400]:
            return None, out
        counts = {}
        for line in out.splitlines():
            cells = line.split("\t")
            if len(cells) >= 5 and self.MARK not in cells[4]:
                try:
                    counts[cells[0]] = (int(cells[1]), int(cells[2]), int(cells[3]), cells[4])
                except ValueError:
                    continue
        return counts, ""

    def open(self, timeout: float) -> None:
        if self.db.engine == "clickhouse":
            code, out = self.ask("SELECT /* %s */ toString(now64(6))" % self.MARK, timeout)
            if code or not out.strip():
                self.note = ("ClickHouse's query log could not be read here: %s"
                             % one_line(out)[:200])
            else:
                self.since = out.strip().splitlines()[0]
            return
        counts, why = self.pg_counts(timeout)
        if counts is None:
            self.note = ("PostgreSQL keeps no statement record this user can read here "
                         "(%s). Print the statement from the code instead -- the ORM or "
                         "query builder can render the SQL it sends." % one_line(why)[:160])
        else:
            self.before = counts

    def close(self, timeout: float) -> str:
        if self.note:
            return self.note
        if self.db.engine == "clickhouse":
            code, _ = self.ask("SYSTEM FLUSH LOGS", timeout)
            if code:
                # Without the right to flush, wait out the log's own interval.
                time.sleep(min(8.0, max(0.0, timeout - 5.0)))
            code, out = self.ask(
                "SELECT /* %s */ query_duration_ms, read_rows, read_bytes, result_rows, "
                "type, replaceRegexpAll(exception, '\\\\s+', ' '), "
                "replaceRegexpAll(query, '\\\\s+', ' ') FROM system.query_log "
                "WHERE event_date >= toDate(toDateTime64(%s, 6)) "
                "AND event_time_microseconds >= toDateTime64(%s, 6) "
                "AND is_initial_query AND type != 'QueryStart' "
                "AND query NOT LIKE %s ORDER BY event_time_microseconds LIMIT 30"
                % (self.MARK, ch_literal(self.since), ch_literal(self.since),
                   ch_literal("%" + self.MARK + "%")), timeout)
            if code:
                return "ClickHouse's query log could not be read: %s" % one_line(out)[:200]
            lines = []
            for line in out.splitlines():
                cells = line.split("\t")
                if len(cells) < 7:
                    continue
                try:
                    ms, rows, size, got = (int(c) for c in cells[:4])
                except ValueError:
                    continue
                text = clip(tsv_cell(cells[6]), 1500, "statement")
                if cells[4] != "QueryFinish":
                    lines.append("- failed: %s\n  %s" % (clip(tsv_cell(cells[5]), 300, "error"), text))
                else:
                    lines.append("- %d ms, read %s rows (%s), returned %s rows\n  %s"
                                 % (ms, format(rows, ","), human_bytes(size), format(got, ","), text))
            if not lines:
                return ("The server logged no statement while the command ran: either none "
                        "reached it, or query logging is off for this user.")
            return "\n".join(lines)
        after, why = self.pg_counts(timeout)
        if after is None:
            return "PostgreSQL's statement record could not be read again: %s" % one_line(why)[:200]
        lines = []
        for key, (calls, rows, blocks, text) in after.items():
            was = self.before.get(key, (0, 0, 0, ""))
            if calls > was[0]:
                lines.append("- %d call(s), %s rows, %s blocks\n  %s"
                             % (calls - was[0], format(rows - was[1], ","),
                                format(blocks - was[2], ","), clip(text, 1500, "statement")))
        if not lines:
            return ("No statement reached this database while the command ran (or the "
                    "command used another database).")
        return "\n".join(lines[:30])


WORLD_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "sent_sql",
            "description": (
                "Run a shell command that exercises the changed code -- the project's focused "
                "test, or a small program calling it -- and see the statements the database "
                "actually received while it ran, as the server recorded them, with the rows "
                "each one read on ClickHouse. Use it to get the exact statement the code sends "
                "now, to put through try_world."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "number", "description": "Seconds to wait (default 180)."},
                    "engine": {"type": "string", "enum": ["postgresql", "clickhouse"]},
                    "url": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "try_world",
            "description": (
                "Run one statement on a small world you build for it, and compare what comes "
                "back with what you expected. The tables you name are replaced, for this call "
                "only, by empty copies of themselves (same columns, keys and sort order); "
                "`rows` fills them -- write it against the real table names, it is pointed at "
                "the copies -- so only the rows you put in exist. Nothing reaches the real "
                "tables. A table the database does not have can be built in `rows` instead "
                "(CREATE TEMP TABLE on PostgreSQL, CREATE TABLE agent_scratch.<name> on "
                "ClickHouse), from the project's own model or migration. "
                "Write `expected` before you run it: one row per line, cells split "
                "by |, NULL for null, '' for an empty string, (no rows) for none. The answer "
                "says MATCHES or DIFFERS, and on ClickHouse how many rows the server read."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hazard": {
                        "type": "string",
                        "description": "What this world tests, in a few words (e.g. 'absent key vs empty value').",
                    },
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables to replace with empty copies, as the statement names them (db.table or table).",
                    },
                    "rows": {
                        "type": "string",
                        "description": "INSERT statements (or INSERT ... SELECT ... FROM numbers(N)) that build the world.",
                    },
                    "statement": {
                        "type": "string",
                        "description": "The one statement the code sends, with its parameter values written in.",
                    },
                    "expected": {"type": "string", "description": "The rows you expect, written before running."},
                    "ordered": {"type": "boolean", "description": "True when the row order is part of the answer."},
                    "plan": {"type": "boolean", "description": "PostgreSQL: also show EXPLAIN (ANALYZE, BUFFERS)."},
                    "engine": {"type": "string", "enum": ["postgresql", "clickhouse"]},
                    "database": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["hazard", "statement", "expected"],
            },
        },
    },
]
if WORLD_CHECK:
    TOOL_SCHEMAS.extend(WORLD_TOOL_SCHEMAS)

WORLD_ASK = (
    "Not handed in yet - one check before it goes, and it happens only once. Nothing in "
    "this run has shown that the changed statement returns the right rows on rows built "
    "to test it. The rows already in the database are not the ones the change will be "
    "checked against; a statement can be right on them and wrong on others.\n\n"
    "Take the statement the code sends now -- sent_sql runs a command and shows what "
    "reached the database, or render it from the code -- and run it with try_world on "
    "small worlds you build for it, writing the rows you expect before you see any. "
    "Pick the cases this task's own requirements make relevant, for example:\n"
    "- a key, attribute or row that is absent, beside one present with an empty, zero "
    "or NULL value;\n"
    "- a group, window or filter that matches nothing;\n"
    "- two rows that tie on the ordering;\n"
    "- a row that joins to several rows on the other side;\n"
    "- a row just inside and one just outside each boundary (time window, range, limit);\n"
    "- rows of other keys, states or owners that must stay out;\n"
    "- every value the output must cover, including one with no rows behind it;\n"
    "- one parameter value against several, and a key that holds most of the rows "
    "(read the work the server reports).\n\n"
    "Fix what differs -- or, where your expectation was wrong, say why -- then hand in again."
)

_NO_SUCH_TABLE = re.compile(r'relation "[^"]+" does not exist|UNKNOWN_TABLE|'
                            r"Table \S+ does(?:n't| not) exist|UNKNOWN_DATABASE", re.I)
WORLD_NO_TABLE = (
    "That table is not in this database -- some projects create their tables only in a test "
    "database, or only while their tests run. Either name the database where it lives "
    "(`database`), or build the table yourself: leave `tables` empty and start `rows` with "
    "%s, its columns taken from the project's models or migrations, then the INSERTs. Point "
    "`statement` at the table you built."
)

WORLD_DIFFERS = (
    "Not handed in yet. These worlds came back different from what you wrote down, and "
    "nothing built since says otherwise:\n\n%s\n\nEither the change or the expectation is "
    "wrong. Find out which: fix the code and run the world again, or say why the "
    "expectation was wrong. Then hand in again."
)

WORLD_TESTS = """TEST ON A WORLD YOU BUILD

The rows already in the database are not the rows a change is checked against, and a statement
that is right on them can be wrong on others. Once you have a change, try it with try_world: name
the tables, put in the rows for one case, run the statement the code now sends (sent_sql shows it,
or render it from the code), and write down the rows you expect before you run it. Only the rows
you put in exist, so a few rows make a case. Cover the cases the requirements make relevant --
absent against empty, zero or NULL; nothing matching; ties; a join that fans out; each side of each
boundary; rows that must stay out; an output value with no rows behind it; one parameter value
against several. A DIFFERS answer means the change or the expectation is wrong; find out which."""


def without_transaction_echo(out: str) -> str:
    return "\n".join(
        line for line in (out or "").splitlines()
        if line.strip() not in ("BEGIN", "SET", "ROLLBACK")
    )

def pick_database(databases: list[Database], url: str = "", engine: str = "") -> Database | None:
    if url:
        parsed = urllib.parse.urlparse(url)
        kind = "postgresql" if url.startswith("postgres") else "clickhouse"
        host = parsed.hostname or ("localhost" if kind == "clickhouse" else "")
        port = parsed.port or (5432 if kind == "postgresql" else 8123)
        user, password, name = parsed.username or "", parsed.password or "", (parsed.path or "/").lstrip("/")
        if not user:
            donors = [d for d in databases if d.engine == kind and d.user and (d.host == host or d.ok)]
            donors.sort(key=lambda d: (d.host != host, not d.ok))
            if donors:
                user, password = donors[0].user, donors[0].password
                name = name or donors[0].name
        if kind == "postgresql":
            conf = {
                "HOST": host,
                "PORT": str(port),
                "USER": user,
                "PASSWORD": password,
                "NAME": name or "postgres",
            }
            return Database(
                "postgresql",
                "given url",
                url=_pg_url(conf),
                host=host,
                port=port,
                user=user,
                password=password,
                name=name or "postgres",
            )
        return Database(
            "clickhouse",
            "given url",
            host=host,
            port=port,
            user=user,
            password=password,
            name=name or "default",
        )
    pool = [d for d in databases if not engine or d.engine == engine]
    pool.sort(key=lambda d: (not d.ok, d.engine != "postgresql"))
    return pool[0] if pool else None

class SpecPins:
    def __init__(self, statement: str) -> None:
        flat = re.sub(r"\s+", " ", statement or "")
        self.restricted = bool(EXCLUSIVE_FILE_RE.search(flat))
        self.constructs_banned = bool(CONSTRUCT_BAN_RE.search(flat))
        self.imports_frozen = bool(IMPORTS_FROZEN_RE.search(flat))
        self.signature_frozen = bool(SIGNATURE_FROZEN_RE.search(flat))
        self.rest_frozen = bool(REST_FROZEN_RE.search(flat))
        seen: list[tuple[str, str]] = []
        for prefix, name in METHOD_TICK_RE.findall(statement or ""):
            pair = (prefix.rstrip("."), name)
            if pair not in seen:
                seen.append(pair)
        self.arities: dict = {}
        if ELIXIR:
            for prefix, name, arity in FUNCTION_ARITY_RE.findall(statement or ""):
                pair = (prefix.rstrip("."), name)
                self.arities.setdefault(name, arity)
                if pair not in seen:
                    seen.append(pair)
        self.methods = seen

    @property
    def active(self) -> bool:
        return bool(
            self.imports_frozen
            or self.signature_frozen
            or self.rest_frozen
            or self.constructs_banned
            or self.methods
        )

    def brief(self) -> str:
        if not self.active:
            return ""
        lines = ["Hard constraints the statement states (checked before the work is handed in):"]
        if self.methods:
            def render(prefix: str, name: str) -> str:
                arity = self.arities.get(name)
                if arity is not None:
                    return ("`%s.%s/%s`" % (prefix, name, arity) if prefix
                            else "`%s/%s`" % (name, arity))
                return "`%s.%s()`" % (prefix, name) if prefix else "`%s()`" % name
            names = ", ".join(render(p, n) for p, n in self.methods)
            lines.append("  Named target(s): %s. Change that method in place." % names)
        flags = []
        if self.constructs_banned:
            flags.append("plain query-layer expressions only (no loops, comprehensions, lambdas, try/except, with)")
        if self.imports_frozen:
            flags.append("imports are frozen; use only names the file already imports")
        if self.signature_frozen:
            flags.append("the target's signature is frozen")
        if self.rest_frozen:
            flags.append("every line outside the target must stay byte-identical")
        if flags:
            lines.append("  " + "; ".join(flags))
        return "\n".join(lines)

_BANNED_CONSTRUCTS = (
    ast.For, ast.AsyncFor, ast.While,
    ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
    ast.Lambda, ast.Try, ast.With, ast.AsyncWith, ast.Raise,
    ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await,
    ast.ClassDef, ast.Import, ast.ImportFrom, ast.Delete, ast.Match,
)
_BANNED_NAMES = {
    "__import__", "breakpoint", "compile", "eval", "exec", "getattr",
    "globals", "locals", "open", "setattr", "vars", "print", "input",
}

def parse_python(text: str):
    try:
        return ast.parse(text)
    except SyntaxError:
        return None

def find_method(tree, prefix: str, name: str):
    wanted = [p for p in prefix.split(".") if p]
    matches: list = []

    def walk(node, path: list) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, path + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == name and (not wanted or path[-len(wanted):] == wanted):
                    matches.append(child)
                walk(child, path)
    walk(tree, [])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1 and wanted:
        return None
    return matches[0] if len(matches) == 1 else None

def method_span(text: str, prefix: str, name: str):
    tree = parse_python(text)
    if tree is None:
        return None
    node = find_method(tree, prefix, name)
    if node is None:
        return None
    start = node.lineno
    if node.decorator_list:
        start = min(d.lineno for d in node.decorator_list)
    return start, getattr(node, "end_lineno", node.lineno), node

def import_block(text: str) -> list:
    tree = parse_python(text)
    if tree is None:
        return []
    return [
        ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

def header_dump(node) -> str:
    fields = {}
    for field in node._fields:
        if field == "body":
            continue
        value = getattr(node, field)
        if isinstance(value, ast.AST):
            fields[field] = ast.dump(value, include_attributes=False)
        elif isinstance(value, list):
            fields[field] = [
                ast.dump(v, include_attributes=False) if isinstance(v, ast.AST) else v
                for v in value
            ]
        else:
            fields[field] = value
    return json.dumps(fields, sort_keys=True, default=str)

def construct_faults(node) -> list[str]:
    faults: list[str] = []
    for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            faults.append("nested function %s" % child.name)
        elif isinstance(child, _BANNED_CONSTRUCTS):
            faults.append(type(child).__name__)
        elif isinstance(child, ast.Name) and (child.id in _BANNED_NAMES or "__" in child.id):
            faults.append("name %s" % child.id)
        elif isinstance(child, ast.Attribute) and "__" in child.attr:
            faults.append("attribute %s" % child.attr)
    seen: list[str] = []
    for item in faults:
        if item not in seen:
            seen.append(item)
    return seen

def _touched_line_numbers(before: str, after: str) -> set[int]:
    import difflib
    touched: set[int] = set()
    matcher = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines())
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            touched.update(range(i1 + 1, i2 + 1))
        if tag == "insert":
            touched.add(i1 if i1 else 1)
    return touched

def infer_target(original: str, current: str):
    tree = parse_python(original)
    if tree is None:
        return None
    touched = _touched_line_numbers(original, current)
    if not touched:
        return None
    best = None

    def walk(node, path: list) -> None:
        nonlocal best
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, path + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = getattr(child, "end_lineno", child.lineno)
                if all(start <= n <= end for n in touched):
                    best = (".".join(path), child.name)
                    walk(child, path)
    walk(tree, [])
    return best

def audit_shape(tree: "Tree", pins: SpecPins) -> list[str]:
    if not pins.active:
        return []
    code, out = git(["diff", "--name-only", tree.base or "HEAD"], tree.root, 30)
    watched = (".py", ".ex", ".exs") if ELIXIR else (".py",)
    paths = [p for p in out.splitlines() if p.endswith(watched)] if code == 0 else []
    for path in sorted(tree._untracked() - tree.untracked_at_start):
        if path.endswith(watched) and path not in paths:
            paths.append(path)
    problems: list[str] = []
    for path in paths:
        before = None
        if tree.base:
            status, shown = git(["show", "%s:%s" % (tree.base, path)], tree.root, 30)
            if status == 0:
                before = shown
        if before is None:
            continue
        try:
            after = tree.read(path)
        except ToolFault:
            continue
        if path.endswith((".ex", ".exs")):
            problems.extend(elixir_audit(path, before, after, pins))
            continue
        if parse_python(after) is None:
            problems.append("%s no longer parses as Python." % path)
            continue
        if pins.imports_frozen and import_block(after) != import_block(before):
            problems.append(
                "The import block of %s changed. The task says to use only names "
                "the file already imports; restore the imports exactly and express "
                "the change with what is in scope." % path
            )
        targets = list(pins.methods)
        named_here = any(method_span(before, prefix, name) is not None for prefix, name in targets)
        if not named_here and (pins.rest_frozen or pins.signature_frozen or pins.constructs_banned):
            inferred = infer_target(before, after)
            if inferred:
                targets.append(inferred)
            elif _touched_line_numbers(before, after) and (
                pins.signature_frozen or pins.constructs_banned
            ):
                problems.append(
                    "The changes in %s are not confined to one method. The task "
                    "changes a single method in place and leaves the rest of the "
                    "file byte-identical; undo every line outside that method." % path
                )
        for prefix, name in targets:
            before_span = method_span(before, prefix, name)
            if before_span is None:
                continue
            after_span = method_span(after, prefix, name)
            if after_span is None:
                problems.append(
                    "%s no longer defines %s(); the task changes that method in "
                    "place, it does not rename or remove it." % (path, name)
                )
                continue
            before_lines = before.splitlines(keepends=True)
            after_lines = after.splitlines(keepends=True)
            if pins.rest_frozen or pins.restricted:
                if (
                    before_lines[: before_span[0] - 1] != after_lines[: after_span[0] - 1]
                    or before_lines[before_span[1]:] != after_lines[after_span[1]:]
                ):
                    problems.append(
                        "Lines outside %s() in %s differ from the original. "
                        "Everything else in the file has to stay byte-identical. "
                        "Put the rest back and keep the change inside the method."
                        % (name, path)
                    )
            if pins.signature_frozen and header_dump(before_span[2]) != header_dump(after_span[2]):
                problems.append(
                    "The signature (or decorators) of %s() changed; keep it exactly as it was."
                    % name
                )
            if pins.constructs_banned:
                already = set(construct_faults(before_span[2]))
                bad = [item for item in construct_faults(after_span[2]) if item not in already]
                if bad:
                    problems.append(
                        "%s() now contains constructs the task forbids: %s. "
                        "The method has to be plain query-layer expressions: no loops, "
                        "comprehensions, lambdas, try/except, with, raise, nested "
                        "functions, or dunder access."
                        % (name, ", ".join(bad[:6]))
                    )
    return problems

EXECUTION_SIGNATURES = (
    ("traceback", r"^Traceback \(most recent call last\)"),
    ("error", r"^\s*(?:E\s+\w+Error|\w+Error:)"),
    ("failed", r"^(?:FAILED|ERROR)\b|\b\d+ failed\b"),
    ("panic", r"^panic:"),
    ("fail", r"^FAIL\b"),
    ("compile", r"\bundefined:|cannot use|error TS\d+"),
    ("exception", r"\bTypeError\b|Exception\b"),
)
EXECUTION_ERROR_RE = re.compile(
    "|".join("(?:" + pattern + ")" for _, pattern in EXECUTION_SIGNATURES), re.M)
EXECUTION_ENVIRONMENT = (
    ("command not found", r"command not found"),
    ("missing command", r"(?:^|\n)(?:[^\n]*?: )?(?P<command>[^:\n]+): No such file or directory"),
    ("could not connect", r"could not connect"),
    ("connection refused", r"Connection refused"),
    ("not installed", r"not installed"),
    ("permission denied", r"Permission denied"),
    ("executable file not found", r"executable file not found"),
)
EXECUTION_EXCLUDED = re.compile(
    r"\s*(?:(?:uv run|poetry run|bundle exec|npx|pnpm exec|python[23]? -m)\s+)?"
    r"(?:rubocop|ruff|eslint|gofmt|go\s+(?:vet|build|fmt)|npm run build|tsc|make|"
    r"cargo build|echo|printf|rg|grep|cat|sed|ls|find|git)\b")
EXECUTION_RUNNER = re.compile(
    r"\bmanage\.py\s+(?:shell|test)\b|\brails\s+runner\b|\brspec\b|"
    r"\bpytest\s+(?:-\S+\s+)*[^\s-]|\bgo\s+test\s+(?:-\S+\s+)*[^\s-]|"
    r"\bmix\s+test\b|\bnpm\s+test\b|\bcargo\s+test\b|\bunittest\b")

def execution_signature(output: str) -> str:
    return next((name for name, pattern in EXECUTION_SIGNATURES
                 if re.search(pattern, output or "", re.M)), "")

def execution_environment(command: str, output: str) -> str:
    for name, pattern in EXECUTION_ENVIRONMENT:
        match = re.search(pattern, output or "", re.I)
        if not match:
            continue
        if name == "missing command":
            missing = match["command"].strip().strip("'\"")
            try:
                commands = [shlex.split(part)[0] for part in re.split(r"&&|;|\|\|", command or "")
                            if part.strip()]
            except ValueError:
                commands = []
            if missing not in commands and os.path.basename(missing) not in commands:
                continue
        return name
    return ""

def changed_execution(command: str, changed_paths=()) -> bool:
    for part in re.split(r"&&|;|\|\|", command or ""):
        if EXECUTION_EXCLUDED.match(part):
            continue
        if EXECUTION_RUNNER.search(part):
            return True
        for path in changed_paths:
            path = path.removeprefix("./")
            stem = os.path.splitext(path)[0]
            package = os.path.dirname(path)
            names = {path, stem.replace("/", ".")}
            if package:
                names.update((package, package.replace("/", ".")))
            if any(re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w/-])", part)
                   for name in names if name):
                return True
    return False

def changed_paths_of(tree: "Tree") -> list:
    code, out = git(["diff", "--name-only", tree.base or "HEAD"], tree.root, 30)
    paths = [p for p in out.splitlines() if p.strip()] if code == 0 else []
    return paths + sorted(tree._untracked() - tree.untracked_at_start)

def original_text(tree: "Tree", path: str):
    code, out = git(["show", "%s:%s" % (tree.base, path)], tree.root, 30)
    return out if code == 0 else None

def import_bindings(source: str) -> dict:
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return {}
    bound: dict = {}
    for node in ast.walk(module):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name.split(".")[0]
                bound[name] = (node.lineno, getattr(node, "end_lineno", node.lineno))
    return bound

def names_in_use(source: str) -> set:
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return set()
    used = set()
    for node in ast.walk(module):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            used.add(node.value.strip())
    return used

def unused_removed_imports(before: str, after: str) -> dict:
    was, now = import_bindings(before), import_bindings(after)
    if not was:
        return {}
    used = names_in_use(after)
    rows = before.splitlines(keepends=True)
    put_back: dict = {}
    for name, (start, end) in was.items():
        if name in now or name not in used:
            continue
        if start < 1 or end > len(rows):
            continue
        put_back[start] = "".join(rows[start - 1:end])
    return put_back

COMMENT_ROW = re.compile(r"^\s*(?:#|//|--)|^\s*$")

def comment_only_removals(before: str, after: str) -> list:
    import difflib
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    runs = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, old, new, autojunk=False).get_opcodes():
        if tag != "delete":
            continue
        block = old[i1:i2]
        if not block or not all(COMMENT_ROW.match(line) for line in block):
            continue
        if all(line.strip() == "" for line in block):
            continue
        runs.append((j1, "".join(block)))
    return runs

def scope_put_back(before: str, after: str) -> str:
    rows = after.splitlines(keepends=True)
    inserts: dict = {}
    for at, text in comment_only_removals(before, after):
        inserts.setdefault(at, []).append(text)
    imports = unused_removed_imports(before, after)
    if imports:
        now = import_bindings(after)
        at = min((start for start, _ in now.values()), default=1) - 1
        for _, text in sorted(imports.items()):
            inserts.setdefault(at, []).append(text)
    if not inserts:
        return ""
    out = []
    for index in range(len(rows) + 1):
        for text in inserts.get(index, []):
            out.append(text if text.endswith("\n") else text + "\n")
        if index < len(rows):
            out.append(rows[index])
    return "".join(out)

def numbered_lines(lines: list, first: int) -> str:
    return "\n".join("%6d\t%s" % (first + i, line) for i, line in enumerate(lines))


def shown_region(text: str, start: int, count: int) -> str:
    """Lines start..start+count-1 (1-based) of `text` with a few either side, numbered."""
    lines = text.split("\n")
    low = max(1, start - EDIT_SHOWN_CONTEXT)
    high = min(len(lines), start + max(count, 1) - 1 + EDIT_SHOWN_CONTEXT)
    return clip(numbered_lines(lines[low - 1:high], low), EDIT_SHOWN_CHARS, "edited lines")


def _indent(line: str) -> str:
    return line[:len(line) - len(line.lstrip())]


def tolerant_windows(text: str, old: str) -> list:
    """Where `old` stands in `text` once each line's surrounding whitespace is ignored.

    Returns the 0-based first line of each window that matches.  The commonest
    miss is text copied with its indentation or trailing spaces a little off,
    which is no reason to send the model back to read the file again.
    """
    want = [line.strip() for line in old.strip("\n").split("\n")]
    if not any(want):
        return []
    lines = text.split("\n")
    have = [line.strip() for line in lines]
    size = len(want)
    return [i for i in range(len(have) - size + 1)
            if have[i] == want[0] and have[i:i + size] == want]


def reindented(new: str, old_first: str, file_first: str) -> list:
    """`new`'s lines moved from the indentation `old` was written with to the file's."""
    was, now = _indent(old_first), _indent(file_first)
    out = []
    for line in new.strip("\n").split("\n") if new.strip("\n") else []:
        if not line.strip():
            out.append("")
        elif line.startswith(was):
            out.append(now + line[len(was):])
        else:
            out.append(now + line.lstrip())
    return out


def nearest_block(text: str, old: str) -> str:
    """The lines of `text` most like `old`, numbered, to copy from without reading again."""
    import difflib
    want = [line.strip() for line in old.strip("\n").split("\n")][:NEAREST_MAX_LINES]
    lines = text.split("\n")
    have = [line.strip() for line in lines]
    anchors = [i for i, line in enumerate(want) if line][:1]
    if not anchors:
        return ""
    at = anchors[0]
    candidates = difflib.get_close_matches(want[at], have, n=5, cutoff=0.5)
    best, score = None, 0.0
    for candidate in candidates:
        for index, line in enumerate(have):
            if line != candidate:
                continue
            first = max(0, index - at)
            window = have[first:first + len(want)]
            ratio = difflib.SequenceMatcher(None, "\n".join(window), "\n".join(want)).ratio()
            if ratio > score:
                best, score = first, ratio
    if best is None or score < 0.4:
        return ""
    low = max(0, best - 2)
    high = min(len(lines), best + len(want) + 2)
    return clip(numbered_lines(lines[low:high], low + 1), EDIT_SHOWN_CHARS * 2, "nearest lines")


# A format check that failed, and the command that fixes what it found.
_FORMAT_CHECKS = (
    (re.compile(r"\bgofmt\s+-[ld]\b([^;&|\n]*)"), lambda out: bool(
        re.search(r"(?m)^\S+\.go$|^diff ", out)), lambda paths: "gofmt -w" + paths),
    (re.compile(r"\bmix\s+format\s+--check-formatted\b([^;&|\n]*)"), lambda out: bool(
        re.search(r"mix format failed|not formatted|--check-formatted", out, re.I)),
     lambda paths: "mix format" + paths),
    (re.compile(r"\bprettier\s+(?:[^;&|\n]*?\s)?--check\b([^;&|\n]*)"), lambda out: bool(
        re.search(r"Code style issues|\[warn\]", out)), lambda paths: "prettier --write" + paths),
    (re.compile(r"\bblack\s+--check\b([^;&|\n]*)"), lambda out: bool(
        re.search(r"would reformat", out, re.I)), lambda paths: "black" + paths),
    (re.compile(r"\bruff\s+format\s+--check\b([^;&|\n]*)"), lambda out: bool(
        re.search(r"would (?:reformat|be reformatted)", out, re.I)),
     lambda paths: "ruff format" + paths),
)


def formatter_hint(command: str, out: str) -> str:
    """One line naming the formatter run that fixes a failed format check, or ""."""
    for check, failed, fix in _FORMAT_CHECKS:
        found = check.search(command or "")
        if found and failed(out or ""):
            paths = " " + found.group(1).strip() if found.group(1).strip() else ""
            return ("\n\n[formatting] the check above found unformatted code. Run `%s` to "
                    "format it; do not fix whitespace by hand." % fix(paths))
    return ""


def apply_change(text: str, old: str, new: str, every: bool, path: str) -> tuple:
    """`text` with one change made: (the new text, how many places, how it was matched).

    An exact match first.  Failing that, the one place `old` stands once each
    line's surrounding whitespace is ignored, written at the file's own
    indentation.  Failing that, a refusal that shows the nearest lines.
    """
    if not old:
        raise ToolFault("old must not be empty; use create_file to write a whole file")
    hits = text.count(old)
    if hits > 1 and not every:
        raise ToolFault(
            "that text occurs %d times in %s. Either extend it until it is unique, "
            "or pass replace_all=true if all %d should change the same way." % (hits, path, hits))
    if hits:
        return (text.replace(old, new) if every else text.replace(old, new, 1)), hits, ""
    windows = tolerant_windows(text, old)
    if len(windows) > 1:
        raise ToolFault(
            "that exact text is not in %s, and it matches %d places once indentation is "
            "ignored; include more of the surrounding lines so it is unique" % (path, len(windows)))
    if not windows:
        near = nearest_block(text, old)
        if near:
            raise ToolFault(
                "that exact text is not in %s. The nearest lines are below; copy the text "
                "to replace from them exactly as it stands:\n%s" % (path, near))
        raise ToolFault("that text is not in %s, nor anything close to it; search for a "
                        "line of it to find where it is" % path)
    first = windows[0]
    lines = text.split("\n")
    size = len(old.strip("\n").split("\n"))
    written = reindented(new, old.strip("\n").split("\n")[0], lines[first])
    return ("\n".join(lines[:first] + written + lines[first + size:]), 1,
            "matched with each line's surrounding whitespace ignored")


class Kit:
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 warden: Warden | None = None, label: str = "",
                 findings: "FindingMap | None" = None,
                 databases: list | None = None,
                 pins: "SpecPins | None" = None) -> None:
        # Which kinds of engine fault this seat has already been told about.
        self.engine_said: set = set()
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.warden = warden
        self.findings = findings
        self.databases = list(databases or [])
        self.pins = pins
        self.seen: dict[str, int] = {}
        self.edit_all = Beacon("editall")
        self.ecto = Beacon("ecto")
        self.ecto_noted: set = set()
        self.bg = Beacon("bgshell")
        self.conform = Beacon("conform")
        self.fence = Beacon("fence")
        self.label = label
        self.conform_state = "armed" if FINISH_CONFORM else "off"
        self.conform_edits = 0
        self.blank_submit_refusals = 0
        self.unbound = Beacon("names")
        self.names_noted: set = set()
        self.names_asked = False
        self.names_before = ""
        self.executions: list = []
        self.executed_asks = 0
        self.executed_pending = None
        self.executed = Beacon("executed")
        self.scope = Beacon("scope")
        # Each world this run has built: (what it tests, MATCHES or DIFFERS...).
        self.worlds: list = []
        self.world = Beacon("world")
        self.world_state = "armed" if WORLD_CHECK else "off"
        self.statement = ""
        self.verify_state = "armed" if VERIFY else "off"
        self.verify = Beacon("verify")
        self.world_mark = 0

    def note_findings(self, command: str, out: str) -> None:
        if self.findings is None:
            return
        try:
            self.findings.observe(command, out)
        except BaseException:
            self.findings.beacon.skipped("the output could not be read")

    def note_execution(self, command: str, out: str) -> None:
        if not EXECUTED:
            return
        try:
            if isinstance(command, (list, tuple)):
                command = shlex.join(command)
            tail = "\n".join((out or "").splitlines()[-EXECUTED_TAIL_LINES:])[-EXECUTED_TAIL_CHARS:]
            self.executions.append((str(command), tail, execution_signature(out)))
            del self.executions[:-EXECUTED_KEEP]
        except BaseException:
            self.executed.skipped("the output could not be kept")

    def settle_executed(self) -> None:
        pending = self.executed_pending
        if pending is None:
            return
        self.executed_pending = None
        digest, _ = pending
        try:
            after = self.tree.diff(15.0)
        except BaseException:
            after = ""
        self.executed.outcome(digest, after)
        self.executed.bill()

    def execution_note(self) -> str | None:
        self.executed.reached(0, self.allowance.spent, self.allowance.clock_left())
        if not EXECUTED:
            self.executed.skipped("not switched on for this run")
            return None
        if self.executed_asks:
            self.executed.skipped("sent back already")
            return None
        if self.allowance.clock_left() < EXECUTED_MIN_LEFT_SEC:
            self.executed.skipped("too little of the run left to act on a send-back")
            return None
        try:
            paths = changed_paths_of(self.tree)
        except BaseException as error:
            self.executed.skipped("the change did not list: %s" % type(error).__name__)
            return None
        if not paths:
            self.executed.skipped("nothing differs from the base")
            return None
        related = [row for row in self.executions if changed_execution(row[0], paths)]
        try:
            before = self.tree.diff(15.0)
        except BaseException:
            before = ""
        digest = self.executed.artefact("before", before)
        if not related:
            self.executed.fired("no command in this run exercised %d changed path(s)"
                                % len(paths))
            self.executed_asks += 1
            self.executed_pending = (digest, before)
            return ("Not handed in yet - one step before it goes, and it happens only "
                    "once. Nothing this run has executed so far touches the code it "
                    "changed:\n\n" + "\n".join("  " + p for p in paths[:8])
                    + "\n\nRun one command that executes the changed path -- the "
                    "narrowest one that reaches it -- read what it prints, fix "
                    "anything it reports, and call hand it in again.")
        command, tail, signature = related[-1]
        environment = execution_environment(command, tail)
        if environment:
            self.executed.fired("last run over the change could not start: " + environment)
            self.executed_asks += 1
            self.executed_pending = (digest, before)
            return ("Not handed in yet - one step before it goes, and it happens only "
                    "once. The last command this run executed over the changed code "
                    "did not get as far as running it:\n\n$ " + command[:300]
                    + "\n\n" + tail[-2000:]
                    + "\n\nRun it another way -- the project's own entry point, or a "
                    "narrower command -- read what it prints, and call hand it in again.")
        if not signature:
            self.executed.skipped("the last command over the change came back clean")
            self.executed.outcome(digest, before)
            self.executed.bill()
            return None
        self.executed.fired("read back %s from: %s" % (signature, one_line(command)[:120]))
        self.executed_asks += 1
        self.executed_pending = (digest, before)
        return ("Not handed in yet - one step before it goes, and it happens only "
                "once. This is the output of the last command this run executed over "
                "the code it changed:\n\n$ " + command[:300] + "\n\n" + tail[-2000:]
                + "\n\nThat output is what the change produces as it stands. Fix what "
                "it reports, or confirm from the source that it is unrelated to the "
                "change, then call hand it in again.")

    def repair_scope(self) -> None:
        self.scope.reached(0, self.allowance.spent, self.allowance.clock_left())
        if not SCOPE:
            self.scope.skipped("not switched on for this run")
            return
        if self.allowance.clock_left() < SCOPE_MIN_LEFT_SEC:
            self.scope.skipped("too little of the run left to read the change back")
            return
        repaired, before_all, after_all = [], [], []
        try:
            paths = [p for p in changed_paths_of(self.tree) if p.endswith(".py")]
        except BaseException as error:
            self.scope.skipped("the change did not list: %s" % type(error).__name__)
            return
        if not paths:
            self.scope.skipped("the change touches no file this can read")
            return
        if len(paths) > SCOPE_MAX_PATHS:
            self.scope.skipped("%d changed path(s) is more than this reads" % len(paths))
            return
        for path in paths:
            try:
                before = original_text(self.tree, path)
                if before is None:
                    continue
                after = self.tree.read(path)
                if len(before) + len(after) > SCOPE_MAX_BYTES:
                    continue
                before_all.append(after)
                put_back = scope_put_back(before, after)
                if not put_back or put_back == after:
                    after_all.append(after)
                    continue
                try:
                    ast.parse(put_back)
                except (SyntaxError, ValueError, RecursionError):
                    after_all.append(after)
                    continue
                self.tree.write(path, put_back)
                after_all.append(put_back)
                repaired.append(path)
            except BaseException as error:
                self.scope.skipped("%s could not be read back: %s"
                                   % (path, type(error).__name__))
        digest = self.scope.artefact("before", "".join(before_all))
        if repaired:
            self.scope.fired("put back removals outside the change in %d file(s): %s"
                             % (len(repaired), ", ".join(repaired[:4])))
        else:
            self.scope.skipped("the change removed nothing it still refers to")
        self.scope.outcome(digest, "".join(after_all))
        self.scope.bill()

    def note_read(self, what: str) -> None:
        say("[READ]%s %s" % (" " + self.label if self.label else "", what))

    def run(self, name: str, args: dict) -> str:
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
                row = clip(row, READ_OUTPUT_CAP, "line")
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
            rows[0] = clip(rows[0], max(0, READ_OUTPUT_CAP - len(head) - 1), "line")
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
        served = clip("%s, %d lines, %d definitions\n" % (path, len(text.splitlines()),
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
            with tempfile.NamedTemporaryFile(mode="w+b", suffix=".search", delete=True) as sink:
                subprocess.run(
                    cmd, cwd=self.tree.root, stdout=sink, stderr=subprocess.DEVNULL,
                    timeout=60, check=False
                )
                sink.flush()
                out = bounded_output_file(sink.name, TOOL_OUTPUT_READ_CAP, "search output")
        except subprocess.TimeoutExpired:
            raise ToolFault("search timed out; narrow the pattern or the path")
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
        served = clip(out, SEARCH_OUTPUT_CAP, "matches")
        self.note_read("search_text %r %s -> %dc" % (pattern, mode, len(served)))
        return served

    def do_find_files(self, args: dict) -> str:
        import fnmatch
        pattern = str(args.get("pattern") or "*")
        self.guard_repeat("glob:%s" % pattern)
        code, out = git(["ls-files"], self.tree.root, 30)
        if code != 0:
            raise ToolFault("could not list tracked files")
        hits = [p for p in out.splitlines() if fnmatch.fnmatch(p, pattern)]
        if not hits:
            loose = pattern if pattern.startswith("*") else "*" + pattern
            hits = [p for p in out.splitlines() if fnmatch.fnmatch(p, loose)]
        if not hits:
            return "no tracked file matches %s" % pattern
        return clip("\n".join(hits[:400]), SEARCH_OUTPUT_CAP, "paths")

    def do_edit(self, args: dict) -> str:
        path = str(args.get("path") or "")
        changes = args.get("changes")
        if changes:
            if not isinstance(changes, list) or not all(isinstance(c, dict) for c in changes):
                raise ToolFault("changes is a list of {old, new} objects, applied in order")
            pairs = [(str(c.get("old") or ""), str(c.get("new") or "")) for c in changes]
        else:
            pairs = [(str(args.get("old") or ""), str(args.get("new") or ""))]
        every = bool(args.get("replace_all")) and REPLACE_ALL and len(pairs) == 1
        text = self.tree.read(path)
        original, hows, total = text, [], 0
        for index, (old, new) in enumerate(pairs, 1):
            try:
                text, hits, how = apply_change(text, old, new, every, path)
            except ToolFault as fault:
                if len(pairs) == 1:
                    raise
                raise ToolFault("change %d of %d was not applied, so none of them were: %s"
                                % (index, len(pairs), fault))
            total += hits
            if how:
                hows.append(how)
        if every and total > 1:
            self.edit_all.fired("%s x%d" % (path, total))
            before = self.edit_all.artefact("before", original)
        else:
            before = ""
        self.tree.write(path, text)
        self.allowance.edits += 1
        self.forget_reads(path)
        if before:
            self.edit_all.outcome(before, text)
        if len(pairs) > 1:
            say("[EDIT] %s: %d changes in one call" % (path, len(pairs)))
        for how in hows:
            say("[EDIT] %s %s" % (path, how))
        head = ("edited %s (%d change%s%s)" % (
            path, len(pairs) if len(pairs) > 1 else total,
            "s" if (len(pairs) > 1 or total > 1) else "",
            "; " + "; ".join(sorted(set(hows))) if hows else ""))
        return head + self.after_edit(path, text, [new for _, new in pairs])

    def after_edit(self, path: str, updated: str, written: list) -> str:
        note = self.compile_check(path)
        note += self.name_note(path)
        note += self.ecto_note(path)
        note += self.engine_note(path)
        shown, seen = [], set()
        for new in written:
            at = updated.find(new.strip("\n")) if new.strip() else -1
            if at < 0:
                continue
            start = updated.count("\n", 0, at) + 1
            if start in seen:
                continue
            seen.add(start)
            count = new.strip("\n").count("\n") + 1
            shown.append("lines %d-%d now read:\n%s"
                         % (start, start + count - 1, shown_region(updated, start, count)))
        body = clip("\n".join(shown), EDIT_SHOWN_CHARS * 2, "edited lines")
        return ("; " + body if body else "") + note

    def forget_reads(self, path: str) -> None:
        """A file that has just changed may be read again without that being a repeat."""
        for key in [k for k in self.seen
                    if k.startswith(("read:%s:" % path, "outline:%s" % path, "grep:", "glob:"))]:
            del self.seen[key]

    def do_create_file(self, args: dict) -> str:
        path = str(args.get("path") or "")
        content = str(args.get("content") or "")
        self.tree.write(path, content)
        self.allowance.edits += 1
        self.forget_reads(path)
        note = "%s%s" % (self.compile_check(path), self.name_note(path))
        note += self.ecto_note(path)
        note += self.engine_note(path)
        count = len(content.split("\n"))
        return ("wrote %s (%d line%s):\n%s%s"
                % (path, count, "" if count == 1 else "s", shown_region(content, 1, count), note))

    def compile_check(self, path: str) -> str:
        suffix = os.path.splitext(path)[1].lower()
        if suffix in (".ex", ".exs") and not ELIXIR:
            return ""
        argv = SYNTAX_CHECKS.get(suffix)
        if not argv or not shutil.which(argv[0]):
            return ""
        if any("{path}" in part for part in argv):
            return self.parse_back(suffix, argv, self.tree.absolute(path))
        done = subprocess.run(
            argv + [self.tree.absolute(path)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if done.returncode == 0:
            return ""
        return "\n\nWARNING: the file no longer parses:\n" + clip(done.stderr or "", 1200, "error")

    def parse_back(self, suffix: str, argv: list, full: str) -> str:
        argv = [part.replace("{path}", json.dumps(full)) for part in argv]
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
        return "\n\nWARNING: the file no longer parses:\n" + clip(done.stderr or "", 1200, "error")

    def engine_note(self, path: str) -> str:
        """What the engine will not do with the lines this edit just added.

        Said as a note on the edit rather than held against the hand-in.  Each
        of these is read off the change by code that knows the engine, and
        code that knows the engine is still capable of being wrong about a
        particular line: a note costs a sentence the writer may disregard,
        while a hold costs a rewrite it cannot.  Once per kind, so a fact the
        writer has been told and has chosen to leave is not repeated.
        """
        if not ENGINE_FACTS or self.allowance.clock_left() < 60.0:
            return ""
        if TEST_PATH_PATTERN.search(path or ""):
            return ""
        base = self.tree.base or "HEAD"
        try:
            code, diff = git(["diff", "-U3", base, "--", path], self.tree.root,
                             max(2.0, min(20.0, self.allowance.clock_left() - 10.0)))
        except Exception:  # noqa: BLE001
            return ""
        if code != 0:
            return ""
        if not (diff or "").strip():
            # A file the run wrote from nothing has no diff against the base.
            # All of it is added, so all of it is read.
            known, _ = git(["cat-file", "-e", "%s:%s" % (base, path)], self.tree.root, 10)
            if known == 0:
                return ""
            try:
                lines = self.tree.read(path).splitlines()
            except Exception:  # noqa: BLE001
                return ""
            diff = ("diff --git a/%s b/%s\n--- /dev/null\n+++ b/%s\n@@ -0,0 +1,%d @@\n"
                    % (path, path, path, len(lines))
                    + "".join("+%s\n" % line for line in lines))
        try:
            source = self.tree.read(path)
        except Exception:  # noqa: BLE001
            source = ""
        engine = self._engine_of(path, source)
        try:
            found = [f for f in engine_findings(diff, engine, None, source)
                     if f[0] not in self.engine_said]
        except Exception as error:  # noqa: BLE001
            say("[ENGINE] the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.engine_said.update(kind for kind, _, _ in found)
        say("[ENGINE] on edit: %s" % ", ".join("%s at %s:%d" % (k, path, l) for k, _, l in found[:3]))
        return "\n\nOn the change just made, shown once: " + " ".join(engine_text(found))

    def _engine_of(self, path: str, source: str) -> str:
        """Which engine's rules to read a file by.

        The connection says it where one has been found.  Otherwise the code
        itself does, and the code is asked rather than the file listing: a
        repository can hold both engines, and which one a particular file
        talks to is a property of what that file writes, not of what is
        installed beside it.
        """
        for holder in (getattr(self, "database", None), getattr(self, "environment", None)):
            engine = str(getattr(holder, "engine", "") or "")
            if engine in ("clickhouse", "postgresql"):
                return engine
        if _CLICKHOUSE_TONGUE_RE.search(source or ""):
            return "clickhouse"
        return "postgresql"

    def ecto_note(self, path: str) -> str:
        if not ELIXIR or not path.endswith((".ex", ".exs")):
            return ""
        if self.allowance.clock_left() < ECTO_NOTE_MIN_SEC:
            return ""
        base = self.tree.base or "HEAD"
        diff = ""
        try:
            code, shown = git(["diff", "-U%d" % ECTO_DIFF_CONTEXT, base, "--", path],
                              self.tree.root,
                              max(2.0, min(20.0, self.allowance.clock_left() - 10.0)))
            if code == 0 and shown.strip():
                diff = shown
        except Exception:
            return ""
        if not diff:
            known, _ = git(["cat-file", "-e", "%s:%s" % (base, path)], self.tree.root, 10)
            if known == 0:
                return ""
            try:
                lines = self.tree.read(path).splitlines()
            except ToolFault:
                return ""
            diff = "@@ -0,0 +1,%d @@\n" % len(lines) + "\n".join("+" + line for line in lines)
        try:
            found = [f for f in fragment_arity_findings(diff)
                     if (f[0], f[1]) not in self.ecto_noted]
        except Exception as error:
            self.ecto.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if not found:
            return ""
        self.ecto_noted.update((kind, name) for kind, name, _ in found)
        self.ecto.fired("on edit: " + ", ".join("%s at %s:%d" % (name, path, line)
                                                for _, name, line in found[:4]))
        said, out = set(), []
        for kind, name, _ in found:
            if kind in said:
                continue
            said.add(kind)
            out.append(ECTO_NOTES[kind] % name)
        return "\n\nNote on the change just made (shown once): " + " ".join(out)

    def do_bash(self, args: dict) -> str:
        command = str(args.get("command") or "")
        self.vet_command(command)
        want_bg = bool(args.get("background")) and ASYNC_SHELL
        asked = float(args.get("timeout") or 120)
        room = self.allowance.clock_left() - WALL_RESERVE_SEC
        if room < 5.0:
            raise ToolFault(
                "not enough of the run left to wait on a command; make the "
                "change you already have evidence for, or finish")
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
            self.note_execution(command, out)
            return (clip(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)") + formatter_hint(command, out)
        self.bg.fired("kept %s alive past %.0fs: %s" % (job.name, budget, command[:120]))
        return (
            clip(out, SHELL_OUTPUT_CAP, "partial output")
            + "\n\n[still running after %.0fs, moved to the background as %s; "
            "keep working and collect it later with bash_poll]" % (budget, job.name)
        )

    def vet_command(self, command: str) -> None:
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
        blocked = HISTORY_GIT.search(command)
        if blocked:
            raise ToolFault(
                "git %s is not available here. Your changes are collected from the working "
                "tree as it stands, so moving or discarding them loses the work. Read-only "
                "git (status, diff, log, grep, show, ls-files) is fine." % blocked.group(1)
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
            self.note_execution(job.command, out)
            return (clip(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)") + formatter_hint(job.command, out)
        return clip(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)"

    def do_run_sql(self, args: dict) -> str:
        query = str(args.get("query") or "")
        if not query.strip():
            raise ToolFault("run_sql requires a non-empty query")
        engine = str(args.get("engine") or "")
        database = str(args.get("database") or "")
        url = str(args.get("url") or "")
        db = pick_database(self.databases, url=url, engine=engine)
        if db is None:
            raise ToolFault(
                "no database connection is known; pass url=... "
                "(postgresql://user:pass@host:port/db or http://host:8123) "
                "after finding the settings the application uses"
            )
        room = min(180.0, self.allowance.clock_left() - WALL_RESERVE_SEC)
        if room < 5.0:
            raise ToolFault("not enough of the run left to wait on a query")
        beacon = Beacon("ROLLBACK")
        beacon.reached(0, self.allowance.spent, self.allowance.clock_left())
        sent, wrapper = query, ""
        budget = int(max(5.0, min(float(SQL_STATEMENT_TIMEOUT_SEC), room - 6.0)))
        if not ROLLBACK_SQL:
            beacon.skipped("not switched on for this run")
        elif db.engine not in ("postgresql", "clickhouse"):
            beacon.skipped("engine %s has no statement bound to apply" % db.engine)
        else:
            if db.engine == "clickhouse":
                refused = clickhouse_write_refusal(query, database or db.name)
                if refused:
                    beacon.fired("clickhouse statement refused: %s" % refused)
                    beacon.bill()
                    raise ToolFault(
                        "not run: %s. On ClickHouse this tool reads anywhere and writes only "
                        "inside %s, which belongs to this run: CREATE DATABASE IF NOT EXISTS %s, "
                        "then CREATE TABLE %s.<name> AS <database>.<table> to copy a table's "
                        "structure, and INSERT INTO %s.<name> SELECT ... FROM numbers(N) to fill it."
                        % (refused, SCRATCH_DATABASE, SCRATCH_DATABASE, SCRATCH_DATABASE,
                           SCRATCH_DATABASE))
                query = self.scratch_copies(db, query, database or db.name or "default", room)
                if re.search(r"\b%s\b" % SCRATCH_DATABASE, query):
                    # One entry per server, not per call: each call may build a
                    # fresh connection object for the same place.
                    place = (db.host, db.port, db.user)
                    if place not in {(d.host, d.port, d.user) for d in SCRATCH_MADE}:
                        SCRATCH_MADE.append(db)
            sent, wrapper = rolled_back_script(db.engine, query, budget)
            beacon.fired("%s statement bounded: %s" % (db.engine, wrapper))
        before = beacon.artefact("before", query)
        code, out = db.run(sent, database=database, timeout=room, cwd=self.tree.root)
        if sent != query:
            out = without_transaction_echo(out)
        beacon.outcome(before, sent)
        beacon.bill()
        if code in (401, 403) or (
            code != 0
            and re.search(
                r"authentication failed|password authentication|"
                r"Authentication failed|permission denied for",
                out,
                re.I,
            )
        ):
            known = [d for d in self.databases if d.ok and d.engine == db.engine and d is not db]
            if known:
                say("[SQL] %s refused credentials; retrying via %s" % (db.label, known[0].label))
                db = known[0]
                code, out = db.run(sent, database=database, timeout=room, cwd=self.tree.root)
                if sent != query:
                    out = without_transaction_echo(out)
        say("[SQL] %s via %s rc=%s %dc :: %s"
            % (db.engine, db.label, code, len(out), one_line(query)[:100]))
        head = db.engine + " via " + db.label + ((" database=" + database) if database else "")
        body = clip(out, SQL_OUTPUT_CAP, "rows") if out else "(no output)"
        return head + "\n" + body + (("\n[exit code %s]" % code) if code else "")

    def scratch_copies(self, db: "Database", query: str, base: str, room: float) -> str:
        """`query` with each bare `CREATE TABLE agent_scratch.x AS db.t` made safe to write to."""
        if not re.search(r"create\s+(?:or\s+replace\s+)?table\b[^;]*\b%s\b" % SCRATCH_DATABASE,
                         query, re.I):
            return query
        out = []
        for statement in split_statements(query):
            found = _SCRATCH_COPY.match(statement.strip().rstrip(";"))
            if found:
                schema, table = split_table_name(found.group("source"), base)
                source, engine, note = self.scratch_source(db, schema, table, base,
                                                           min(15.0, room))
                if note:
                    say("[SQL] scratch copy of %s.%s: %s" % (schema, table, note))
                statement = found.group("head") + source + engine
            out.append(statement)
        return ";\n".join(out)

    def pick(self, args: dict) -> "Database":
        db = pick_database(self.databases, url=str(args.get("url") or ""),
                           engine=str(args.get("engine") or ""))
        if db is None:
            raise ToolFault(
                "no database connection is known; pass url=... "
                "(postgresql://user:pass@host:port/db or http://host:8123) "
                "after finding the settings the application uses")
        return db

    def do_sent_sql(self, args: dict) -> str:
        command = str(args.get("command") or "")
        self.vet_command(command)
        db = self.pick(args)
        room = self.allowance.clock_left() - WALL_RESERVE_SEC
        if room < 40.0:
            raise ToolFault("not enough of the run left to run a command and read the log")
        budget = max(10.0, min(float(args.get("timeout") or 180), SHELL_BUDGET_CEILING_SEC,
                               room - 25.0))
        log = StatementLog(db, self.tree.root)
        log.open(10.0)
        job = self.pool.start(command)
        done, out = job.wait(budget)
        self.pool.jobs.pop(job.name, None)
        if done:
            report_shell(job, out)
            self.note_findings(command, out)
            self.note_execution(command, out)
        else:
            job.stop()
            out += "\n[stopped after %.0fs]" % budget
        seen = log.close(min(20.0, max(5.0, self.allowance.clock_left() - WALL_RESERVE_SEC)))
        say("[SQL] sent_sql %s %s :: %s" % (db.engine, "done" if done else "stopped",
                                             one_line(command)[:100]))
        return ("$ %s\n%s\n\nWhat reached %s while it ran:\n%s"
                % (command[:300], clip(out, 3000, "command output") or "(no output)",
                   db.engine, clip(seen, SQL_OUTPUT_CAP, "statements")))

    def scratch_source(self, db: "Database", schema: str, table: str, base: str,
                       timeout: float) -> tuple:
        """(what to copy, an ENGINE clause or "", a note) for a scratch copy of schema.table.

        A copy made with AS takes its source's engine.  For a table that keeps
        its own rows that is the point -- the sort key comes with it -- but a
        Distributed table forwards what is written to it, so its copy would
        write to the real table; that one is copied from the table it
        distributes, and anything else that keeps no rows of its own becomes a
        plain MergeTree.
        """
        named = "%s.%s" % (ch_ident(schema), ch_ident(table))
        code, out = db.http("SELECT engine, engine_full FROM system.tables WHERE database = %s "
                            "AND name = %s" % (ch_literal(schema), ch_literal(table)),
                            base, timeout, fmt="TabSeparated")
        found = split_work(out)[0].strip() if not code else ""
        if not found:
            return named, " ENGINE = MergeTree ORDER BY tuple()", (
                "its engine could not be read, so the copy is a plain MergeTree")
        engine, _, full = found.splitlines()[0].partition("\t")
        full = tsv_cell(full)
        if _CH_OWN_ROWS.search(engine):
            return named, "", ""
        if engine == "Distributed":
            args = [a.strip().strip("'\"") for a in
                    full[full.find("(") + 1:full.rfind(")")].split(",")]
            if len(args) >= 3 and args[2]:
                local_schema = args[1] if args[1] and "(" not in args[1] else schema
                return ("%s.%s" % (ch_ident(local_schema), ch_ident(args[2])), "",
                        "copied from %s.%s, the table it distributes" % (local_schema, args[2]))
        return named, " ENGINE = MergeTree ORDER BY tuple()", (
            "its %s engine keeps no rows of its own, so the copy is a plain MergeTree" % engine)

    def do_try_world(self, args: dict) -> str:
        hazard = one_line(str(args.get("hazard") or ""))[:120]
        statement = str(args.get("statement") or "").strip().rstrip(";").strip()
        if not hazard:
            raise ToolFault("say in `hazard` what this world tests")
        if not statement:
            raise ToolFault("`statement` is the one statement to run on the world")
        if args.get("expected") is None:
            raise ToolFault("write the rows you expect in `expected` before running it; "
                            "(no rows) when none should come back")
        if len(split_statements(statement)) > 1:
            raise ToolFault("`statement` holds one statement; what builds the world goes in `rows`")
        db = self.pick(args)
        room = min(180.0, self.allowance.clock_left() - WALL_RESERVE_SEC)
        if room < 15.0:
            raise ToolFault("not enough of the run left to build a world")
        tables = [str(t).strip() for t in (args.get("tables") or []) if str(t).strip()]
        rows = str(args.get("rows") or "").strip()
        database = str(args.get("database") or "")
        if db.engine == "clickhouse":
            code, returned, notes, sent, extra = self.world_clickhouse(
                db, database, tables, rows, statement, room)
        elif db.engine == "postgresql":
            code, returned, notes, sent, extra = self.world_postgres(
                db, database, tables, rows, statement, bool(args.get("plan")), room)
        else:
            raise ToolFault("no world can be built on %s" % db.engine)
        head = ["world on %s: %s" % (db.engine, hazard)] + ([] if code else notes)
        if code:
            self.worlds.append((hazard, "NOT RUN"))
            say("[WORLD] %s not run :: %s" % (db.engine, one_line(extra)[:160]))
            lines = head + ["NOT RUN -- the world could not be built or read:",
                            clip(extra, 3000, "output")]
            if _NO_SUCH_TABLE.search(extra or ""):
                lines.append(WORLD_NO_TABLE % (
                    "CREATE TEMP TABLE <name> (...)" if db.engine == "postgresql"
                    else "CREATE TABLE %s.<name> (...) ENGINE = MergeTree ORDER BY ..."
                    % SCRATCH_DATABASE))
            return "\n".join(lines)
        wanted = expected_rows(str(args.get("expected")))
        verdict = compare_world(returned, wanted, bool(args.get("ordered")))
        self.worlds.append((hazard, verdict))
        say("[WORLD] %s %s :: %s" % (db.engine, verdict[:60], hazard[:80]))
        shown = [" | ".join(r) for r in returned[:WORLD_ROWS_SHOWN]]
        if len(returned) > WORLD_ROWS_SHOWN:
            shown.append("... %d more" % (len(returned) - WORLD_ROWS_SHOWN))
        lines = head + ["ran: " + clip(one_line(sent), 800, "statement"),
                        "returned %d row(s)%s" % (len(returned), ":" if shown else "")]
        lines += ["  " + r for r in shown]
        lines.append(verdict)
        if extra:
            lines.append(clip(extra, 4000, "plan"))
        return "\n".join(lines)

    def world_clickhouse(self, db: "Database", database: str, tables: list, rows: str,
                         statement: str, room: float) -> tuple:
        base = database or db.name or "default"
        deadline = time.monotonic() + room
        left = lambda: max(3.0, deadline - time.monotonic())
        notes, mapping, taken = [], {}, set()
        code, out = db.http("CREATE DATABASE IF NOT EXISTS %s" % SCRATCH_DATABASE, base, left())
        if code:
            return code, [], notes, statement, out
        place = (db.host, db.port, db.user)
        if place not in {(d.host, d.port, d.user) for d in SCRATCH_MADE}:
            SCRATCH_MADE.append(db)
        for name in tables:
            schema, table = split_table_name(name, base)
            shadow = table if table.lower() not in taken else "%s__%s" % (schema, table)
            taken.add(shadow.lower())
            source, engine, note = self.scratch_source(db, schema, table, base, min(20.0, left()))
            target = "%s.%s" % (SCRATCH_DATABASE, ch_ident(shadow))
            code, out = db.http("DROP TABLE IF EXISTS %s; CREATE TABLE %s AS %s%s"
                                % (target, target, source, engine), base, left())
            if code:
                return code, [], notes, statement, out
            mapping[(schema.lower(), table.lower())] = target
            notes.append("%s.%s stands in as %s%s" % (schema, table, target,
                                                       (" (" + note + ")") if note else ""))
        seed = shadow_tables(rows, mapping, base) if rows else ""
        if seed:
            refused = clickhouse_write_refusal(seed, base)
            if refused:
                return 1, [], notes, statement, (
                    "`rows` would write outside the stand-ins (%s); name every table it "
                    "fills in `tables`" % refused)
            code, out = db.http(seed, base, left(), fmt="TabSeparated")
            if code:
                return code, [], notes, statement, out
        sent = shadow_tables(statement, mapping, base)
        if clickhouse_read_only(sent):
            return 1, [], notes, sent, "`statement` must read (SELECT or WITH ...); build the world in `rows`"
        code, out = db.http(sent, base, left(), fmt="TabSeparated")
        if code:
            return code, [], notes, sent, out
        body, work = split_work(out)
        returned = [tuple(world_cell(tsv_cell(c)) for c in line.split("\t"))
                    for line in body.split("\n")] if body else []
        return 0, returned, notes, sent, work

    def world_postgres(self, db: "Database", database: str, tables: list, rows: str,
                       statement: str, plan: bool, room: float) -> tuple:
        parts, mapping, notes, taken = [], {}, [], set()
        for name in tables:
            schema, table = split_table_name(name, "public")
            if table.lower() in taken:
                raise ToolFault("two tables named %s; build them in two worlds" % table)
            taken.add(table.lower())
            parts.append("CREATE TEMP TABLE %s (LIKE %s.%s INCLUDING ALL)"
                         % (pg_ident(table), pg_ident(schema), pg_ident(table)))
            # A column numbered from the real table's sequence would move that
            # sequence on, and a sequence is not undone with the rest.
            parts.append(
                "DO $agent$ DECLARE r record; s text; BEGIN FOR r IN SELECT a.attname FROM "
                "pg_attribute a JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
                "WHERE a.attrelid = %s::regclass AND pg_get_expr(d.adbin, d.adrelid) LIKE "
                "'nextval(%%' LOOP s := 'agent_seq_' || md5(%s || '.' || r.attname); "
                "EXECUTE format('CREATE TEMP SEQUENCE %%I', s); "
                "EXECUTE format('ALTER TABLE pg_temp.%%I ALTER COLUMN %%I SET DEFAULT "
                "nextval(%%L)', %s, r.attname, 'pg_temp.' || s); END LOOP; END $agent$"
                % ("'pg_temp.%s'" % pg_ident(table).replace("'", "''"),
                   "'%s'" % table.replace("'", "''"), "'%s'" % table.replace("'", "''")))
            mapping[(schema.lower(), table.lower())] = "pg_temp." + pg_ident(table)
            notes.append("%s.%s stands in as an empty temporary copy" % (schema, table))
        seed = shadow_tables(rows, mapping, "public") if rows else ""
        sent = shadow_tables(statement, mapping, "public")
        body = parts + ([seed.rstrip().rstrip(";")] if seed else [])
        body += ["SELECT '%s'" % WORLD_BEGIN, sent, "SELECT '%s'" % WORLD_END]
        if plan:
            body.append("EXPLAIN (ANALYZE, BUFFERS) " + sent)
        budget = int(max(5.0, min(float(SQL_STATEMENT_TIMEOUT_SEC), room - 6.0)))
        script, _ = rolled_back_script("postgresql", ";\n".join(body), budget)
        code, out = db.run(script, database=database, timeout=room, cwd=self.tree.root, tab=True)
        lines = out.split("\n")
        if WORLD_BEGIN not in lines or WORLD_END not in lines:
            return code or 1, [], notes, sent, out
        first, last = lines.index(WORLD_BEGIN), lines.index(WORLD_END)
        returned = [tuple(world_cell(c) for c in line.split("\t"))
                    for line in lines[first + 1:last]]
        after = "\n".join(l for l in lines[last + 1:] if l.strip())
        return 0, returned, notes, sent, (("plan:\n" + after) if plan and after else "")

    def verify_note(self) -> str | None:
        """Once per run: the change read afresh by a second model before it goes."""
        if self.verify_state != "armed":
            return None
        self.verify_state = "done"
        left = self.allowance.clock_left()
        self.verify.reached(0, self.allowance.spent, left)
        if not self.statement:
            self.verify.skipped("no task to check against")
            return None
        if left < VERIFY_MIN_LEFT_SEC:
            self.verify.skipped("too little of the run left to act on a second reading")
            return None
        if self.allowance.money_left() < VERIFY_MIN_MONEY_USD:
            self.verify.skipped("too little of the money left for a second reading")
            return None
        found = run_verifier(self.statement, self.tree, self.pool, self.allowance,
                             self.databases, self.verify)
        self.verify.bill()
        if found:
            # The second reading stands in for the writer's own re-reading.
            if self.conform_state == "armed":
                self.conform_state = "done"
            return VERIFY_ASK % "\n".join(
                "- %s%s%s\n  evidence: %s" % (
                    item["problem"],
                    (" (at %s)" % item["where"]) if item["where"] else "",
                    (' -- the task says: "%s"' % item["task_quote"]) if item["task_quote"] else "",
                    one_line(item["evidence"])[:400])
                for item in found)
        if found == [] and self.conform_state == "armed":
            self.conform_state = "done"
        return None

    def world_note(self) -> str | None:
        if self.world_state in ("off", "done"):
            return None
        left = self.allowance.clock_left()
        self.world.reached(len(self.worlds), self.allowance.spent, left)
        if self.world_state == "armed":
            built = [w for w in self.worlds if w[1] != "NOT RUN"]
            if not any(d.engine in ("postgresql", "clickhouse") for d in self.databases):
                why = "no database is known to build a world on"
            elif len(built) >= 2:
                why = "the run built %d world(s) before handing in" % len(built)
            elif left < WORLD_MIN_LEFT_SEC:
                why = "too little of the run left to build a world"
            elif self.allowance.money_left() < self.allowance.soft_usd * WORLD_MIN_MONEY_SHARE:
                why = "too little of the money left to build a world"
            else:
                why = ""
            if why:
                self.world_state = "done"
                self.world.skipped(why)
                return None
            self.world_state = "asked"
            self.world_mark = len(self.worlds)
            self.world.fired("hand-in held for worlds; %d built so far" % len(built))
            return WORLD_ASK
        self.world_state = "done"
        since = self.worlds[self.world_mark:]
        latest: dict = {}
        for hazard, verdict in since:
            latest[hazard] = verdict
        wrong = [(h, v) for h, v in latest.items() if v.startswith("DIFFERS")]
        if wrong and left >= WORLD_DIFFERS_MIN_LEFT_SEC:
            self.world.fired("%d of %d world(s) still differ" % (len(wrong), len(latest)))
            return WORLD_DIFFERS % "\n".join("- %s: %s" % (h, v) for h, v in wrong[:6])
        self.world.fired("released after %d world(s), %d differing"
                         % (len(since), len(wrong)))
        return None

    def name_findings(self, paths: list) -> list:
        found: list = []
        for path in [p for p in paths if (p or "").endswith(".py")][:NAME_CHECK_MAX_FILES]:
            if TEST_PATH.search(path):
                continue
            lines = path_added_lines(self.tree.root, self.tree.base or "HEAD", path)
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
        if not NAME_CHECK or not (path or "").endswith(".py"):
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
        if not NAME_CHECK:
            return ""
        paths = list(self.warden.changed_paths()) if self.warden is not None else []
        try:
            found = self.name_findings(paths)
        except Exception as error:
            self.unbound.skipped("the change could not be read: %s" % type(error).__name__)
            return ""
        if self.names_asked:
            if self.names_before:
                self.unbound.outcome(self.names_before,
                                     " ".join("%s@%s:%d" % (n, p, l) for n, l, _, p in found))
                self.unbound.bill()
                self.names_before = ""
            return ""
        self.unbound.reached(len(paths), self.allowance.spent, self.allowance.clock_left())
        if not found:
            self.unbound.skipped("every name the change reads is bound in its own module")
            self.names_asked = True
            self.unbound.bill()
            return ""
        self.names_asked = True
        self.names_before = self.unbound.artefact(
            "before", " ".join("%s@%s:%d" % (n, p, l) for n, l, _, p in found))
        self.unbound.fired("held hand-in: "
                           + ", ".join("%s at %s:%d" % (n, p, l) for n, l, _, p in found[:4]))
        return (NAME_HEAD + "\n\n"
                + "\n\n".join("- " + NAME_NOTE % (n, p, l, why) for n, l, why, p in found[:3])
                + "\n\nFix this and call hand it in again.")

    def do_finish(self, args: dict) -> str:
        self.settle_executed()
        if self.blank_submit_refusals < 2 and self.allowance.clock_left() >= BLANK_FINISH_MIN_WALL_SEC:
            try:
                changed = self.tree.has_changes(10.0)
            except BaseException:
                changed = None
            if changed is False:
                self.blank_submit_refusals += 1
                return (
                    "Not handed in: the final patch is empty. The database task requires "
                    "a concrete production change. Re-check the requested behavior, inspect "
                    "the target definition and its callers, make the narrowest real edit, "
                    "run a focused check, and call hand it in again."
                )
        if (self.pins is not None and self.pins.active
                and self.allowance.clock_left() >= BLANK_FINISH_MIN_WALL_SEC):
            try:
                shape = audit_shape(self.tree, self.pins)
            except BaseException:
                shape = []
            if shape:
                return (
                    "Not handed in. The statement's own patch-shape rules are "
                    "not met yet:\n\n"
                    + "\n\n".join(shape[:4])
                    + "\n\nThere is budget left. Fix the shape and call hand it in again."
                )
        if self.allowance.clock_left() >= BLANK_FINISH_MIN_WALL_SEC:
            held = self.name_faults()
            if held:
                return held
        reserve = (self.allowance.conform_min_wall_sec
                   if (self.conform_state == "armed" and
                       self.allowance.clock_left() >=
                       self.allowance.conform_min_wall_sec) else
                   self.allowance.warden_release_sec)
        faults = self.warden.verdict(reserve) if self.warden else []
        if not faults:
            note = self.world_note()
            if note:
                return note
            note = self.verify_note()
            if note:
                return note
            if self.warden is None or not self.warden.stood_down:
                note = self.conform_note()
                if note:
                    return note
            note = self.execution_note()
            if note:
                return note
            self.repair_scope()
            raise Finished(str(args.get("summary") or ""))
        return ("Not handed in. The task states conditions this run can "
                "check itself, and they are not met yet:\n\n"
                + "\n\n".join(faults[:3])
                + "\n\nThere is budget left. Fix this and call hand it in again.")

    def conform_note(self) -> str | None:
        if self.conform_state == "asked":
            self.conform_state = "done"
            self.conform.fired("rehanded in after %d further edit(s)"
                               % (self.allowance.edits - self.conform_edits))
            return None
        if self.conform_state != "armed":
            return None
        if self.allowance.clock_left() < self.allowance.conform_min_wall_sec:
            self.conform_state = "done"
            self.conform.skipped("too little of the run left to act on the answer")
            return None
        self.conform_state = "asked"
        self.conform_edits = self.allowance.edits
        self.conform.fired("hand-in paused to re-read the statement's requirements")
        return ("Not handed in yet - one check before it goes, and it happens only "
                "once. Re-read the problem statement and collect every specific "
                "database detail it requires: result grain, NULL behavior, duplicate "
                "handling, ordering, boundaries, exact values, laziness, query-count "
                "bounds, engine rules, and editable scope. Also check that independent filters "
                "and lifecycle conditions still compose; stale state cannot overwrite newer "
                "state after a wait; compare-and-set and bit updates preserve unrelated fields "
                "or flags; empty subsets, zero values, ties, and composite identities keep their "
                "stated meaning. Apply these only where the statement or source requires them. "
                "For each one, point at the code that "
                "satisfies it as the tree now stands - a line of your diff, or code "
                "that was already right and needed no change. Fix any requirement "
                "nothing satisfies; a detail the statement spells out holds to the "
                "letter. Then inspect the completed query or migration and confirm the "
                "diff changed nothing outside the stated production scope. When both hold, "
                "call hand it in again.")

WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
QUOTED_RE = re.compile(r"[`'\"]([A-Za-z_][A-Za-z0-9_.]{2,})[`'\"]")
COMMON_WORDS = frozenset(
    """the this that with from when what which should would could have been
    test tests file files line lines code error errors return returns value
    values method function class module import python true false none self
    argument arguments result results object objects string strings expected""".split()
)

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
    for term in sorted(terms)[:40]:
        if looked >= 30:
            break
        done = subprocess.run(
            ["git", "grep", "-lFi", "--", term],
            cwd=tree.root,
            capture_output=True,
            text=True,
            errors="replace",
        )
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

def repo_sketch(tree: Tree) -> str:
    parts = []
    code, listing = git(["ls-files"], tree.root, 30)
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

BRIEF = """You are implementing a production database-query change in a checked-out repository. You have shell access
and file tools. When you are done, the working tree is the answer: your changes are read
straight off it, so leave the fix in place and call finish.

Work inside the repository as it is. Do not add dependencies and do not rewrite
unrelated code. Implement the stated query semantics at the repository's existing
abstraction level. Do not weaken tests or hard-code examples from the statement.

CRITICAL - spend turns carefully. Every reply costs one exchange with the model, and
exchanges are the scarcest thing you have. Put every tool call that does not depend on another one into the
SAME reply. Reading four files is four calls in one reply, not four replies. Searching for
three patterns is three calls in one reply. Only wait for a result when the next thing you
do genuinely depends on it.

Do not sit idle while a slow command runs. Start a test suite with background=true, keep
reading code, and collect it with bash_poll when you need the answer.

HOW TO READ THE PROBLEM AND REPOSITORY

1. Locate the exact file and definition named by the statement. Read its imports, model
   or schema, nearest caller, and adjacent repository-native query patterns before editing.
   If the statement restricts the editable method or file, treat that as a hard patch boundary.

2. Translate the requested result into a small semantic table: empty input, NULL values,
   duplicate relationships, unrelated rows, filtering, ordering, and projected fields.
   Use that table to reason about cardinality and query shape without inventing requirements.

3. Determine the actual database engine and query layer from repository evidence. Prefer
   the native ORM, query builder, manager, migration, or SQL idiom already used nearby.
   Keep reads lazy and composable unless the task explicitly requires evaluation or a write.

IMPLEMENT AND VALIDATE

Make the smallest patch that satisfies the complete contract, and make it as one complete
edit of the definition -- the whole function or statement -- rather than a series of small
ones; the edit's reply shows the lines it wrote, so they need no reading again. Fix formatting
by running the project's formatter on the changed file, never by editing whitespace by hand.
Inspect its query shape for
accidental row multiplication, eager materialisation, per-row queries, engine-incompatible
constructs, or a migration state mismatch. Run a cheap syntax or query-construction check
first, then the narrow repository tests that cover the changed path. Do not keep polling a
hung database command; use its failure mode to refine the query or choose a cheaper check.

Before the first edit, map every independent requirement to a changed expression, an existing
line deliberately preserved, or a focused check. Re-read that map against the complete final
query or transaction, not only the edited hunk. Make independent constraints compose: a fix
for membership, aggregation, final-row selection, or concurrency must preserve every existing
filter, ordering and pagination key, lock or transaction boundary, and no-op behavior.

For state transitions and concurrent writes, identify the version or identity that authorizes
the update. Re-read after waits where repository semantics require it; a stale callback or
terminal result must not overwrite newer state, and compare-and-set logic must preserve fields
changed independently. Treat flags as composable bit sets when the repository does. Exercise
degenerate dimensions explicitly: empty subsets must not become all rows, zero denominators
must retain the stated result, ties need the complete ordering key, and multi-column identity
must compare every axis. Do not invent any of these rules when the statement or source proves
the opposite.

BEFORE YOU FINISH

Read the final diff hunk by hunk. Confirm every changed line is inside the allowed scope,
the query preserves required multiplicity and laziness, imports and signatures obey the
statement, and unrelated behavior is untouched. Call finish with a one-line summary."""

def without_sweep(brief: str) -> str:
    start = brief.find("WHEN THE SAME DEFECT")
    end = brief.find("BEFORE YOU FINISH")
    return brief[:start] + brief[end:] if 0 <= start < end else brief

RESTRUCTURE = """WHEN THE DATABASE TASK REQUIRES RESTRUCTURING

The behaviours the statement asks to change are the only behaviours that may change.
Every other visible behaviour must survive your edit, whether or not any test names
it. Structure is yours: add helpers, adjust call sites, fix at the layer the defect
actually lives - but through all of it the code keeps doing what it did.

1. Restructure by MOVING lines, never by re-deriving them from memory. A block lifted
   into a helper keeps its text apart from what the move itself requires - a name now
   qualified, a value now passed in: the same names, the same exception tuples, the
   same operators and boundaries, the same short-circuits, the same order of cases.
   If two places handled failure differently before, they still differ after; do not
   merge branches that were merely similar.
2. Where the statement spells out a specific detail - an ordering, a boundary, a
   default, which failures are tolerated - that detail is a requirement, not colour.
   Implement each one literally and at full strength.
3. Before you finish, read your own diff hunk by hunk. Every changed line should be a
   move, a mechanical consequence of one (a name now qualified, a parameter now
   passed), or a change the statement asked for. A line that is none of these is a
   defect you introduced."""
INVARIANTS = """PRESERVE DATABASE INVARIANTS

Change only the narrowest decision point. Copy existing attribute names,
operators, defaults, guard scopes, branches and exception boundaries instead of
re-deriving them. Preserve transaction boundaries, query laziness, ordering,
cardinality, NULL behavior, and the distinction between entity rows and joined
relationship rows unless the statement explicitly changes one of them."""
DATABASE_QUERY_ENGINEERING = """DATABASE QUERY ENGINEERING

This agent is dedicated to production database-query changes. Before editing,
make five contracts explicit: permitted source scope, exact result semantics,
laziness and composability, database-work complexity, and the engine or
query-layer rules. Every restriction in the problem statement is part of the
implementation contract, including allowed imports and constructs.

1. Read the complete target definition, its current imports, and the nearest
   caller, model, schema, or migration that establishes the relationships.
   Reuse repository-native APIs, expressions, naming, and compatibility
   patterns; never invent framework behavior from memory. Treat scope limits
   as patch-shape limits: when only one method may change and imports must
   remain, any diff outside that method is invalid. Existing imports and a
   placeholder expression are evidence for the intended abstraction level;
   prefer completing that expression over replacing its surrounding design.
2. Work out the applicable behavior for empty inputs, NULLs, duplicate joins,
   unrelated rows, filtering, ordering, slicing, projections, and transaction
   boundaries. Preserve cardinality and distinguish unique entities from
   repeated relationship rows. Keep query construction lazy unless a write is
   explicitly required.
3. Derive the database-work bound from the final query shape. Python iteration
   over rows, materialising a result merely to filter it, and a probe followed
   by per-row queries all scale with data even when a small fixture looks fine.
   Prefer a repository-native set expression that stays composable.
4. For a correlated ORM subquery, construct the complete scalar shape before
   trying to compile or evaluate it: correlate, clear irrelevant ordering,
   group at the intended result grain, annotate the aggregate, project exactly
   one column, and bound it to one row where the ORM requires that. An OuterRef
   queryset is not independently executable. Do not pass an OuterRef to an API
   that requires an immediate Python boolean, such as an is-null flag; express
   NULL-safe equality with query expressions supported by the repository and
   inspect the SQL of the completed outer query. Give arithmetic, Coalesce,
   Case, and Subquery expressions an explicit compatible output type when the
   ORM cannot infer one safely.
5. Respect the actual PostgreSQL, ClickHouse, ORM, query-builder, manager,
   filterset, or migration semantics present in the repository. For an index
   or plan change, match production predicates, operator classes, column order,
   and migration state rather than adding a superficially similar index.
6. Keep the patch inside the stated files and definitions. Before hand-in,
   inspect the diff before starting a slow suite and repair every scope breach.
   Compile or render the query cheaply where possible, then run the narrow
   repository tests and parser or type check. Confirm query count, schema
   state, multiplicity, imports, and untouched behavior remain consistent with
   the contract. A hung database check is evidence against the current query
   shape, not a reason to keep polling it indefinitely.
7. When a live engine is reachable, use run_sql. On PostgreSQL measure with
   EXPLAIN (ANALYZE, BUFFERS); a write there is undone when the call ends, so
   you can insert an awkward row, query it and read the result back without
   wrapping it yourself. On ClickHouse use EXPLAIN indexes=1, and read the line
   every result ends with, which gives the rows and bytes the server read for
   it; writes there run only inside agent_scratch and are not undone, so build
   data in it once and query it as often as you need. If the configured database
   is empty, the project's test database (often kept by --keepdb) is the ready
   schema once a named test has run once. Do not start a second suite against
   the same --keepdb database while one is still running.
8. If the file already uses RawSQL / text() / a SQL string, write one
   correlated raw subquery per annotation rather than a tower of
   OuterRef/Subquery/Exists that needs new imports. Watch integer vs numeric
   division (100 -> 100.0 rather than importing Cast), DISTINCT double-counting
   across joins, NULL-safe equality, and N+1. On ClickHouse filter on the
   ORDER BY / partition key so PREWHERE and pruning work; avoid SELECT * and
   FINAL unless required. Helpers and new import lines are not free when the
   statement freezes the rest of the file: stay inside the named method."""
DB_SEMANTICS = """CONCURRENT AND ORDERED WRITES

When operations described by the task can overlap, or an update must not undo a
later one, the question is which committed version of a row the change may
overwrite, not only what the query returns.

- Put the condition that justified the write into the write itself, so the
  database applies it only while that condition still holds, instead of
  reading, deciding in application code, and then updating by identity alone.
- Check how many rows the write changed; when none did, follow the path stated
  for that case rather than the success path.
- Write only the fields this operation owns. Reading a whole row and writing it
  back erases what another operation changed in the meantime.
- Apply effects in the order of the version they were computed from, not the
  order they arrive in. A failed, finished, or superseded attempt must not
  clear state that a later success set, and a retry reads the committed state
  again instead of trusting the value it started with.
- Keep the lock scopes, row locks, ordering keys, and no-op branches already
  there; they are what makes the interleaving safe.
- Keep the number of statements fixed as a batch grows, and add no index,
  column, method, or query that is not called for.

POSTGRESQL NOTES

- A condition written for the missing side of an outer join (a joined column
  IS NULL, or NULL allowed in a status list) means "no matching row". When the
  join becomes a subquery or EXISTS, drop that condition instead of carrying it
  into the subquery.
- Wrapping a FROM clause in a subquery: give the subquery the alias the outer
  query used (FROM (...) AS t), so every existing fragment that refers to
  t.column still resolves. This holds in any SQL dialect.
- At READ COMMITTED a statement reads the snapshot taken when it started; a
  lock acquired inside that same statement does not refresh it. When one row
  takes over a flag from another, choose the rows to clear by identity (every
  row other than the new holder) so the row-level re-check sees the latest
  committed version, or take the lock in an earlier statement.

CLICKHOUSE NOTES

- Compute a share-of-total denominator over the same filter as the numerator,
  within each time bucket or other outer grain the result is reported in and
  summed across the groups being compared -- not one total for the whole
  result."""

BOUNDED_WORK = """WHEN THE TASK BOUNDS THE WORK

When the task limits how much a statement may read or do -- rows read, work that must stay
proportional to what was asked for rather than to the size of a table, one statement rather than
several -- that is a property of the statement to measure, not of its text to argue. An empty table
measures nothing: every statement reads no rows from one, the ones that would read a whole table
included. So build the data first. On ClickHouse copy the real table's structure, sort key and all,
into agent_scratch (CREATE TABLE agent_scratch.t AS db.table); on PostgreSQL insert rows inside the
rolled-back transaction. Fill it with the shape the task describes -- if it says one key holds
millions of values while the others hold few, build exactly that -- at a size where reading
everything and reading only what was asked for are far apart. Then run the statement the code will
actually send, with the values it will put in it, and read what the server reports: the rows read on
ClickHouse, EXPLAIN (ANALYZE, BUFFERS) on PostgreSQL. Compare that with the bound before finishing.
A LIMIT does not stop a read that runs on several threads, which has already read past it; a
grouping reads every row it groups, whatever it keeps."""


def compose_brief() -> str:
    text = BRIEF
    if MOVE_VERBATIM:
        marker = "BEFORE YOU FINISH"
        text = (text.replace(marker, RESTRUCTURE + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + RESTRUCTURE)
    if INVARIANT_BRIEF:
        marker = "BEFORE YOU FINISH"
        text = (text.replace(marker, INVARIANTS + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + INVARIANTS)
    marker = "BEFORE YOU FINISH"
    body = DATABASE_QUERY_ENGINEERING + "\n\n" + DB_SEMANTICS + "\n\n" + BOUNDED_WORK
    if WORLD_CHECK:
        body += "\n\n" + WORLD_TESTS
    text = (text.replace(marker, body + "\n\n" + marker, 1)
            if marker in text else text + "\n\n" + body)
    return text

def declared_scope_excerpt(statement: str, tree: Tree) -> str:
    path = declared_file(statement, tree.root)
    if path is None:
        return ""
    try:
        source = tree.read(path)
    except ToolFault:
        return ""
    target = declared_definition(statement)
    if target is None:
        return clip("FILE %s\n%s" % (path, source), DECLARED_SCOPE_CHARS,
                    "declared source file")
    node = definition_node(source, target)
    if node is None:
        return clip("FILE %s\n%s" % (path, source), DECLARED_SCOPE_CHARS,
                    "declared source file")
    try:
        module = ast.parse(source)
    except SyntaxError:
        return ""
    imports = []
    for item in module.body:
        if isinstance(item, (ast.Import, ast.ImportFrom)):
            text = ast.get_source_segment(source, item)
            if text:
                imports.append(text)
    body = ast.get_source_segment(source, node) or ""
    owner, name = target
    qualified = "%s.%s" % (owner, name) if owner else name
    rendered = (
        "DECLARED SOURCE SCOPE (current code, not a proposed answer)\n"
        "FILE %s\nTARGET %s() lines %d-%d\n\nIMPORTS\n%s\n\nDEFINITION\n%s"
        % (path, qualified, getattr(node, "lineno", 0),
           getattr(node, "end_lineno", 0), "\n".join(imports), body)
    )
    return clip(rendered, DECLARED_SCOPE_CHARS, "declared source scope")

def opening_message(statement: str, tree: Tree, hints: list[str],
                    db_report: str = "", pins: "SpecPins | None" = None) -> str:
    blocks = ["Problem to fix:\n\n" + statement.strip(), "\nRepository at a glance:\n" + repo_sketch(tree)]
    if hints:
        blocks.append(
            "\nFiles whose contents overlap the rare terms in the problem, most overlap first. "
            "This is a starting point produced by text matching, not an answer:\n"
            + "\n".join("  " + p for p in hints)
        )
    scope = declared_scope_excerpt(statement, tree)
    if scope:
        blocks.append(
            "\nThe task explicitly names this source scope. It is included so "
            "you can preserve its imports and surrounding code from the first "
            "turn:\n" + scope
        )
    pin_text = pins.brief() if pins is not None else ""
    if pin_text:
        blocks.append("\n" + pin_text)
    try:
        code, listing = git(["ls-files"], tree.root, 15)
        layers = query_layers(listing.splitlines()) if code == 0 else ""
        if layers:
            blocks.append("\nQuery layer hints from the tree: " + layers)
    except Exception:
        pass
    if db_report.strip():
        blocks.append(
            "\nLive database, probed before the first turn (no tokens). "
            "Use run_sql against a reachable engine; on PostgreSQL what a "
            "call writes is undone when it ends:\n" + db_report
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
    say("[TRIM] freed %dB, transcript now ~%dB" % (freed, total))
    return True

PLAN_BRIEF = """You are planning, not editing. You can read this repository but you cannot change it.

Another agent has been reading this task for several turns and has not managed to change
anything yet. Your job is to work out where the change belongs and say so.

You have a reading budget of %d characters of tool output; what is left of it is reported
back to you after every turn. A ranged read costs what it returns, so read narrowly: find
the file first, then the lines.

Call set_plan whenever your understanding improves. It overwrites the previous note, and the
note MAY BE READ AT ANY MOMENT -- so keep it worth reading from the first call onward rather
than saving it for the end. Call done_planning as soon as you have enough; you are not
required to spend the budget.

A good note names files and line ranges and says what has to become true. It does not
restate the task."""
PLAN_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline", "run_sql")
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
                           "is good enough; spending the whole budget buys nothing by itself.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

def plan_tools() -> list[dict]:
    return [s for s in TOOL_SCHEMAS
            if s["function"]["name"] in PLAN_TOOL_NAMES] + PLAN_EXTRA_TOOLS

def run_plan(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance,
             beacon: Beacon, turn: int, databases: list | None = None) -> str:
    beacon.reached(turn, allowance.spent, allowance.clock_left())
    if not PLAN_SEAT:
        beacon.skipped("not switched on for this run")
        return ""
    spent_at_entry, calls_at_entry = allowance.spent, allowance.calls
    ceiling = spent_at_entry + allowance.soft_usd * PLAN_SPEND_SHARE
    kit = Kit(tree, pool, allowance, label="PLAN", databases=list(databases or []))
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
            calls = reply.get("tool_calls") or []
            entry = {"role": "assistant", "content": str(reply.get("content") or "")}
            if calls:
                entry["tool_calls"] = recorded_calls(calls)
            messages.append(entry)
            if not calls:
                stop = "silent"
                break
            finished = False
            for call in calls:
                function = call.get("function") or {}
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
                served = clip(str(result), READ_OUTPUT_CAP)
                read += len(served)
                messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                 "content": served})
            if finished:
                stop = "done"
                break
            messages.append({"role": "user", "content": "Reading budget: %d used, %d left."
                             % (read, max(0, PLAN_READ_BUDGET - read))})
    except Exception as error:
        stop = "error"
        say("[PLAN] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    beacon.fired("stopped=%s steps=%d read=%dc note=%dB" % (stop, step, read, len(note)))
    empty = beacon.artefact("before", "")
    beacon.outcome(empty, note.strip())
    if note.strip():
        say("[PLAN] note %s" % note.strip().replace("\n", " | ")[:PLAN_NOTE_CHARS])
    beacon.bill()
    return note.strip()

SCOUT_BRIEF = """You are reading ahead for another agent that will change this repository. You cannot change
anything, and you are not asked to solve the task.

Your one useful output is a single concrete case, taken from this repository, on which the code as it
stands and the task disagree: the input rows or objects, what the code returns for them now, what the
task requires instead, and the smallest existing command or reading that would show the difference.
Read the definition the task points at, its nearest caller, the model or schema behind it and an
adjacent test when there is one. General remarks about NULLs, grain, joins, ordering or duplicates are
not a case; the rows are.

Pair the case with one neighbouring case that has to keep its present result: a caller, branch, helper
or test you actually read, or a line of the task that says what to leave alone. Put its input, its
unchanged result and how to check it in change_boundary. It separates the narrow change from a wider
one and does not repeat the failing case. When the task and the repository establish no such case, say
so there rather than invent one.

Call set_case only when you can quote the requirement exactly from the task and quote the code exactly
from a repository file that is not a test. Both quotes are checked before the other agent sees the
card; a card that fails the check comes back to you with the reason. A second exact quote may cite a
caller, a schema or a test. When the task and the code do not support a specific case, call no_case
rather than guess. One grounded card is the whole job; stop after it.

You have a reading allowance of %d characters of tool output; what is left of it is reported back after
every turn. A ranged read costs what it returns, so find the file first, then the lines."""
SCOUT_TOOL_NAMES = ("read_file", "search_text", "find_files", "outline")
SCOUT_CLOSING = ("The reading has ended. Record the card now from what you have read -- set_case -- or "
                 "call no_case if it does not support one.")
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

def loose(text: object) -> str:
    return " ".join(str(text or "").split())

def quoted_from(quote: str, text: str) -> bool:
    return bool(quote) and (quote in text or loose(quote) in loose(text))

def scout_quote(args: dict, name: str) -> str:
    return str(args.get(name) or "").strip()

def grounded_card(statement: str, tree: "Tree", args: dict) -> tuple:
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
    fields = {name: loose(args.get(name))[:1200] for name, _ in SCOUT_CARD_FIELDS}
    thin = [name for name, value in fields.items() if len(value) < low]
    if thin:
        return "", "too little in " + ", ".join(thin)
    anchors = ["- task requirement: `%s`" % one_line(requirement)[:900],
               "- code anchor `%s`: `%s`" % (path, one_line(quote)[:700])]
    if related:
        anchors.append("- related anchor `%s`: `%s`" % (related, one_line(related_quote)[:700]))
    head = "Case found before any edit, anchored in this repository\n" + "\n".join(anchors)
    labels = [(name, "\n- %s: " % label) for name, label in SCOUT_CARD_FIELDS]
    card = head + "".join(label + fields[name] for name, label in labels)
    if len(card) <= SCOUT_CARD_CHARS:
        return card, ""
    room = (SCOUT_CARD_CHARS - len(head) - sum(len(label) for _, label in labels)) // len(labels)
    if room < 80:
        return "", "the anchors leave no room for the case itself"
    return head + "".join(label + clip(fields[name], room, name) for name, label in labels), ""

def run_scout(statement: str, tree: "Tree", pool: "ShellPool", allowance: "Allowance",
              beacon: Beacon, hints: list) -> str:
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
    seat = Seat(allowance, models=[DRIVER_MODEL], patient=False, effort=SCOUT_EFFORT)
    allowed = {schema["function"]["name"] for schema in scout_tools()}
    opening = ("Task:\n" + clip(statement, SCOUT_STATEMENT_CHARS, "task")
               + "\n\nRepository at a glance:\n" + repo_sketch(tree))
    if hints:
        opening += ("\n\nFiles whose contents overlap the rare terms in the task, most overlap first; a starting "
                    "point from text matching, not a conclusion:\n" + "\n".join("  " + p for p in hints[:12]))
    messages = [{"role": "system", "content": SCOUT_BRIEF % SCOUT_READ_BUDGET},
                {"role": "user", "content": opening}]
    card, read, stop, step = "", 0, "turns", 0
    try:
        for step in range(1, SCOUT_TURN_CAP + 1):
            if allowance.spent >= ceiling:
                stop = "spend"
                break
            # The last step, by turns or by reading, asks for the card itself:
            # stopping without one throws away everything that was read.
            closing = step == SCOUT_TURN_CAP or read >= SCOUT_READ_BUDGET
            if closing:
                messages.append({"role": "user", "content": SCOUT_CLOSING})
                reply = seat.ask(messages, SCOUT_EXTRA_TOOLS, tool_choice="required")
            else:
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
                served = clip(str(result), READ_OUTPUT_CAP)
                read += len(served)
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id") or "scout_%d_%d" % (step, index),
                                 "content": served})
            if finished:
                break
            if closing:
                stop = "budget" if read >= SCOUT_READ_BUDGET else "turns"
                break
            messages.append({"role": "user", "content": "Reading allowance: %d used, %d left. Record one grounded "
                             "card, or stop." % (read, max(0, SCOUT_READ_BUDGET - read))})
    except Exception as error:
        stop = "error"
        say("[SCOUT] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    beacon.fired("stopped=%s steps=%d read=%dc card=%dB" % (stop, step, read, len(card)))
    if card:
        say("[SCOUT] card %s" % card.replace("\n", " | ")[:SCOUT_CARD_CHARS])
    beacon.bill()
    return card

VERIFY_BRIEF = """You are reviewing a pull request another engineer opened on this repository. The change is
already applied in your own copy of the repository -- your working directory. Nothing you do here
reaches the author's copy, so build, run tests, add scratch files and programs, and query the database
freely.

Review it the way a careful reviewer does:
1. Say to yourself what the change alters: which functions and queries, and what they return. For a
   query, that is its result columns -- their names, how many, their order.
2. Find every caller and consumer of what changed -- search for the function, the query, and the struct,
   type or mapper that holds its rows -- and check each still works with the change. A result that
   gains, loses or renames a column breaks code that reads rows by name or by position.
3. Check each requirement in the task against the code as it stands.
4. Where you can, show it: build, run the narrowest relevant test, or run the statement or a small
   program, and read what comes back.

Report only problems you can show, each with its evidence: the command you ran and what it printed, or
the lines that show it. Style, naming and improvements the task does not ask for are not problems. If
the change does what the task asks and breaks nothing, approve it. End with the review tool."""

VERIFY_TOOL_NAMES = ("read_file", "search_text", "find_files", "bash", "bash_poll", "run_sql",
                     "create_file", "edit")
VERIFY_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "review",
        "description": "End the review: approve the change, or request changes with each problem shown.",
        "parameters": {
            "type": "object",
            "properties": {
                "approve": {"type": "boolean"},
                "problems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "problem": {"type": "string", "description": "What is wrong, in one or two sentences."},
                            "evidence": {"type": "string",
                                         "description": "What shows it: the command run and what it printed, or the lines."},
                            "where": {"type": "string", "description": "path:line in the repository."},
                            "task_quote": {"type": "string", "description": "The words of the task it breaks, if any."},
                        },
                        "required": ["problem", "evidence"],
                    },
                },
            },
            "required": ["approve"],
        },
    },
}
VERIFY_CLOSING = "The review has ended. Call review now with what you found."


def verify_tools() -> list[dict]:
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in VERIFY_TOOL_NAMES] + [VERIFY_REPORT_TOOL]


def grounded_problems(statement: str, tree: "Tree", problems: object) -> list:
    """The problems a review can show: evidence, and a quote of the task or a real file."""
    kept = []
    for item in problems if isinstance(problems, list) else []:
        if not isinstance(item, dict):
            continue
        text = one_line(str(item.get("problem") or ""))[:400]
        evidence = str(item.get("evidence") or "").strip()
        quote = str(item.get("task_quote") or "").strip()
        where = str(item.get("where") or "").strip()
        path = where.split(":", 1)[0].strip()
        shown = quoted_from(quote, statement) if quote else False
        if not shown and path:
            try:
                shown = os.path.isfile(tree.absolute(path))
            except ToolFault:
                shown = False
        if text and evidence and shown:
            kept.append({"problem": text, "evidence": clip(evidence, 600, "evidence"),
                         "task_quote": quote if quoted_from(quote, statement) else "",
                         "where": where[:120]})
    return kept[:VERIFY_PROBLEMS_MAX]


def review_copy(tree: "Tree", diff: str) -> str | None:
    """A checkout of the base with `diff` applied, sharing what git does not track.

    The project's dependencies and builds (deps, node_modules, a virtualenv, a
    build directory) are ignored by git and so absent from a fresh checkout;
    they are linked in from the live tree, so the copy builds and tests as the
    live one does.
    """
    where = os.path.join(tempfile.mkdtemp(prefix="review"), "tree")
    code, out = git(["worktree", "add", "--detach", where, tree.base or "HEAD"], tree.root, 60)
    if code != 0:
        return None
    code, out = git(["ls-files", "--others", "--ignored", "--exclude-standard", "--directory"],
                    tree.root, 30)
    tops = []
    for line in out.splitlines() if code == 0 else []:
        top = line.strip().rstrip("/").split("/", 1)[0]
        if top and top != ".git" and top not in tops:
            tops.append(top)
    for top in tops[:VERIFY_LINKS_MAX]:
        target = os.path.join(where, top)
        if not os.path.lexists(target):
            try:
                os.symlink(os.path.join(tree.root, top), target)
            except OSError:
                pass
    code, out = run_piped(["git", "apply", "--whitespace=nowarn", "-"], where, 60, stdin_text=diff)
    if code != 0:
        drop_review_copy(tree, where)
        return None
    return where


def drop_review_copy(tree: "Tree", where: str) -> None:
    try:
        git(["worktree", "remove", "--force", where], tree.root, 60)
    except BaseException:
        pass
    shutil.rmtree(os.path.dirname(where), ignore_errors=True)


def run_verifier(statement: str, tree: "Tree", pool: "ShellPool", allowance: "Allowance",
                 databases: list, beacon: Beacon) -> list | None:
    """A review of the change by a second model, in its own copy of the repository.

    Returns the problems it could show, [] when it approves, or None when it
    did not run or did not reach a verdict.
    """
    try:
        diff = tree.diff(20.0)
    except BaseException:
        diff = ""
    if not diff.strip():
        beacon.skipped("nothing to review")
        return None
    where = review_copy(tree, diff)
    if where is None:
        beacon.skipped("no copy of the repository to review in")
        return None
    copy = Tree(where)
    own = ShellPool(where)
    spent_at_entry, calls_at_entry = allowance.spent, allowance.calls
    ceiling = spent_at_entry + VERIFY_MAX_USD
    ends = time.monotonic() + VERIFY_CLOCK_SEC
    kit = Kit(copy, own, allowance, label="REVIEW", databases=list(databases or []))
    seat = Seat(allowance, models=[VERIFY_MODEL], patient=False, effort=VERIFY_EFFORT)
    seat.call_ceiling = VERIFY_CALL_SEC
    allowed = set(VERIFY_TOOL_NAMES)
    messages = [{"role": "system", "content": VERIFY_BRIEF},
                {"role": "user", "content": "Task:\n" + clip(statement, SCOUT_STATEMENT_CHARS, "task")
                 + "\n\nThe pull request:\n" + clip(diff, VERIFY_DIFF_CHARS, "diff")}]
    found = None
    try:
        for step in range(1, VERIFY_TURN_CAP + 1):
            if allowance.spent >= ceiling or allowance.clock_left() < VERIFY_MIN_LEFT_SEC / 2:
                break
            closing = step == VERIFY_TURN_CAP or time.monotonic() >= ends
            if closing:
                messages.append({"role": "user", "content": VERIFY_CLOSING})
            offer, choice = ([VERIFY_REPORT_TOOL], "required") if closing else (verify_tools(), "auto")
            # One dropped connection is no reason to lose the review: each
            # call gets a second try while there is time for it.
            for attempt in (1, 2):
                try:
                    reply = seat.ask(messages, offer, tool_choice=choice)
                    break
                except (Spent, SeatRefused) as error:
                    if attempt == 2 or time.monotonic() >= ends:
                        raise
                    say("[VERIFY] call failed, trying once more: %s" % str(error)[:120])
            raw = reply.get("tool_calls")
            calls = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
            entry = {"role": "assistant", "content": str(reply.get("content") or "")}
            if calls:
                entry["tool_calls"] = recorded_calls(calls)
            messages.append(entry)
            if not calls:
                break
            for index, call in enumerate(calls):
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                name = str(function.get("name") or "")
                try:
                    args = json.loads(function.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments were not an object")
                except Exception as error:
                    result = "could not read the arguments: %s" % error
                else:
                    if name == "review" and found is None:
                        found = [] if args.get("approve") is True and not args.get("problems") else \
                            grounded_problems(statement, copy, args.get("problems"))
                        result = "recorded"
                    elif name not in allowed:
                        result = "error: %s is not available in a review" % name
                    else:
                        try:
                            result = kit.run(name, args)
                        except (ToolFault, Finished) as fault:
                            result = "error: %s" % fault
                        except Exception as error:
                            result = "error: %s: %s" % (type(error).__name__, error)
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id") or "verify_%d_%d" % (step, index),
                                 "content": clip(str(result), READ_OUTPUT_CAP)})
            if found is not None or closing:
                break
    except Exception as error:
        say("[VERIFY] gave up: %s: %s" % (type(error).__name__, str(error)[:200]))
    finally:
        try:
            own.close()
        except BaseException:
            pass
        drop_review_copy(tree, where)
    beacon.calls = allowance.calls - calls_at_entry
    beacon.usd = allowance.spent - spent_at_entry
    if found is None:
        beacon.fired("no verdict after %d call(s)" % beacon.calls)
    else:
        beacon.fired("%s: %d problem(s) it could show" % ("changes requested" if found else "approved",
                                                         len(found)))
        for item in found:
            say("[VERIFY] %s | %s | %s" % (item["problem"][:200], item["where"],
                                           one_line(item["evidence"])[:160]))
    return found


VERIFY_ASK = (
    "Not handed in yet. A reviewer went over your change in its own copy of the repository, "
    "from a clean start -- it has not seen your reasoning, and it may be wrong -- and requested "
    "changes:\n\n%s\n\nCheck each one against the code. Fix what is real; for anything that is "
    "not, you need do nothing. Then hand in again."
)


SCOUT_HANDOFF = (
    "\n\nBefore any edit, a read-only pass over this repository looked for one concrete case on which the code as "
    "it stands and the task disagree, and left the card below. Its requirement quote was checked against the task "
    "and its code quotes against this repository; its account of the behaviour and the result it expects are "
    "hypotheses. Check them against the whole definition, its nearest caller, the schema and the tests, and try to "
    "break the case with the smallest probe you can before widening the change. Check the neighbouring case "
    "under change boundary too: the finished change gives the required result and keeps that one. One small probe "
    "covering both is best; a compatibility claim the repository does not establish is not a requirement. If the "
    "card contradicts the task or the code, set it aside rather than force it.\n\n")

def scout_handoff(card: str) -> str:
    return SCOUT_HANDOFF + card if (card or "").strip() else ""

def drive(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance,
          findings: "FindingMap | None" = None) -> None:
    seat = Seat(allowance)
    warden = Warden(tree, pool, allowance, statement)
    warden.arm()
    pins = SpecPins(statement)
    databases: list = []
    db_report = ""
    leftover = min(PROBE_BUDGET_SEC, max(8.0, allowance.clock_left() - 60.0))
    try:
        databases, db_report = probe_databases(tree.root, leftover)
        say("[DB] " + (", ".join(d.describe() for d in databases) or "none found"))
    except Exception as error:
        say("[DB] probe failed: %s: %s" % (type(error).__name__, error))
    kit = Kit(tree, pool, allowance, warden, findings=findings,
              databases=databases, pins=pins)
    kit.statement = statement
    locate = Beacon("prelocate")
    trim = Beacon("trim")
    sweep = Beacon("sweep")
    plan = Beacon("plan")
    locate.reached(0, allowance.spent, allowance.clock_left())
    if PRELOCATE:
        hints = candidate_files(tree, statement, locate)
    else:
        locate.skipped("not switched on for this run")
        hints = []
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
    if not FINISH_CONFORM:
        kit.conform.skipped("not switched on for this run")
    if findings is not None:
        findings.beacon.reached(0, allowance.spent, allowance.clock_left())
    else:
        Beacon("findings").skipped("not switched on for this run")
    card = ""
    try:
        card = run_scout(statement, tree, pool, allowance, Beacon("scout"), hints)
    except Exception as error:
        say("[SCOUT] skipped: %s: %s" % (type(error).__name__, str(error)[:160]))
    messages: list[dict] = [
        {"role": "system", "content": compose_brief()},
        {"role": "user", "content": opening_message(statement, tree, hints, db_report, pins)
         + scout_handoff(card)},
    ]
    cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
    say("[LOOP] transcript cap set for %s" % seat.current())
    blanks = 0
    pressed = 0
    wrapped_up = False
    editgate = Beacon("editgate")
    editgate.reached(0, allowance.spent, allowance.clock_left())
    if not EDIT_GATE:
        editgate.skipped("not switched on for this run")
    gate_fires = 0
    gate_closed = False
    reply_seconds: list[float] = []
    for turn in range(1, TURN_CEILING + 1):
        warden.collect()
        halt = allowance.halt_reason()
        if halt:
            say("[LOOP] stopping on %s at turn %d" % (halt, turn))
            return
        edit_due_by_time = (
            allowance.clock_left()
            <= allowance.run_window_sec * FIRST_EDIT_TIME_REMAINING_SHARE
        )
        if EDIT_GATE:
            first_edit_due = (
                turn > FIRST_EDIT_DEADLINE_TURN
                or allowance.elapsed()
                >= allowance.run_window_sec * FIRST_EDIT_WINDOW_SHARE
            )
            note_due = allowance.run_window_sec >= PLAN_NOTE_MIN_WINDOW_SEC
        else:
            first_edit_due = turn > FIRST_EDIT_DEADLINE_TURN or edit_due_by_time
            note_due = not edit_due_by_time
        if (allowance.edits == 0
                and first_edit_due
                and pressed < EDIT_PRESSES_MAX):
            pressed += 1
            say("[LOOP] %d turns without an edit; pressing for one (#%d)"
                % (turn - 1, pressed))
            press = (
                "No edit yet. Narrow the database contract to the exact production "
                "definition and take the next evidence-backed step. Before editing, "
                "identify the result grain, query-layer primitive, and repository "
                "example that supports the intended shape. Do not guess merely to "
                "create a diff, and do not finish while the tree is unchanged."
            )
            if pressed == 1 and note_due:
                note = run_plan(statement, tree, pool, allowance, plan, turn, databases)
                if note:
                    press += (
                        "\n\nA second agent read the repository and left this note. "
                        "It did not run anything and may be wrong -- check it against "
                        "the file before you act on it.\n\n" + note
                    )
            messages.append({"role": "user", "content": press})
        if TRANSCRIPT_CAP:
            shrink_transcript(messages, cap, trim)
        offer = TOOL_SCHEMAS
        if EDIT_GATE and not gate_closed:
            floor = allowance.run_window_sec * EDIT_GATE_FLOOR_SHARE
            if len(reply_seconds) >= EDIT_GATE_FLOOR_MIN_REPLIES:
                floor = max(floor,
                            EDIT_GATE_FLOOR_REPLIES * middle_value(reply_seconds))
            floor = min(floor,
                        allowance.run_window_sec * EDIT_GATE_FLOOR_CEILING_SHARE)
            below = allowance.clock_left() < floor
            if allowance.edits > 0 or (below and not tree_untouched(tree)):
                gate_closed = True
                if gate_fires:
                    editgate.skipped("a change has been made; the reading tools are "
                                     "offered again")
                else:
                    editgate.skipped("a change was made before the floor was reached")
            elif below:
                gate_fires += 1
                editgate.fired(
                    "reads withheld at clock_left=%.0fs edits=0 floor=%.0fs "
                    "reply_median=%.1fs"
                    % (allowance.clock_left(), floor, middle_value(reply_seconds)))
                before = editgate.artefact("before", tool_offer_image(offer))
                offer = acting_tool_schemas(offer)
                editgate.outcome(before, tool_offer_image(offer))
                editgate.bill()
                if gate_fires == 1:
                    messages.append({
                        "role": "user",
                        "content": "The reading tools are not available until a "
                                   "change has been made.",
                    })
        answering = seat.current()
        asked_at = time.time()
        reply = seat.ask(messages, offer)
        reply_seconds.append(max(0.0, time.time() - asked_at))
        if seat.current() != answering:
            cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
            say("[LOOP] seat changed under us; transcript cap set for %s"
                % seat.current())
        calls = reply.get("tool_calls") or []
        text = str(reply.get("content") or "")
        if calls and not PARALLEL_TOOLS:
            dropped = len(calls) - 1
            calls = calls[:1]
            if dropped:
                say("[BATCH] not switched on for this run, dropped %d call(s)" % dropped)
        normalised_ids = normalise_tool_call_ids(calls, turn)
        if normalised_ids:
            say("[IDNORM] turn %d: normalised %d tool-call id(s)"
                % (turn, normalised_ids))
        entry = {"role": "assistant", "content": text if calls else (text or "")}
        if calls:
            entry["tool_calls"] = recorded_calls(calls)
        messages.append(entry)
        if not calls:
            blanks += 1
            if not text.strip() and blanks >= BLANK_REPLY_CEILING:
                if seat.retire(seat.current()):
                    say("[LOOP] %d blank replies; changed seats" % blanks)
                    cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
                    say("[LOOP] transcript cap set for %s"
                        % seat.current())
                    blanks = 0
                    continue
                say("[LOOP] %d blank replies and no seat left" % blanks)
                return
            messages.append(
                {
                    "role": "user",
                    "content": "That reply carried no tool call. Take the next concrete step, "
                    "or call finish if the change is complete.",
                }
            )
            continue
        blanks = 0
        say("[LOOP] turn %d: %d tool call(s)" % (turn, len(calls)))
        for call in calls:
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            try:
                args = json.loads(function.get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments were not an object")
            except Exception as error:
                result = "could not read the arguments: %s" % error
            else:
                try:
                    result = kit.run(name, args)
                except Finished as done:
                    say("[LOOP] finish at turn %d: %s" % (turn, str(done)[:200]))
                    return
                except ToolFault as fault:
                    result = "error: %s" % fault
                    say("[TOOL] %s error: %s" % (name, one_line(str(fault))[:160]))
                except Exception as error:
                    result = "error: %s: %s" % (type(error).__name__, error)
                    say("[TOOL] %s error: %s: %s" % (name, type(error).__name__,
                                                      one_line(str(error))[:140]))
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id"), "content": clip(str(result), READ_OUTPUT_CAP)}
            )
        # Where the run stands, said with every turn's results: a model that
        # works in small steps otherwise has no sense of how far through it is.
        if messages and messages[-1].get("role") == "tool":
            messages[-1]["content"] += (
                "\n[turn %d, %.0fs of the run left, %d edit%s so far]"
                % (turn, max(0.0, allowance.clock_left()), allowance.edits,
                   "" if allowance.edits == 1 else "s"))
        if (not wrapped_up
                and (allowance.clock_left() < allowance.run_window_sec * WRAPUP_CLOCK_SHARE
                     or turn >= TURN_CEILING * WRAPUP_TURN_SHARE
                     or allowance.money_left() < allowance.soft_usd * 0.15)):
            wrapped_up = True
            messages.append(
                {
                    "role": "user",
                    "content": "You are near the end of the run. Finish the change you are on, "
                    "inspect the completed query or migration shape, run the narrowest "
                    "relevant check, review the final diff against the stated scope, and "
                    "call finish.",
                }
            )
    say("[LOOP] hit the turn ceiling")

PATCH_ENVELOPE = flag("RIDGES_PATCH_ENVELOPE")
ENVELOPE_JUNK = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache|\.tox|node_modules|\.cache|"
    r"\.DS_Store|nohup\.out)(/|$)|\.(pyc|pyo|pyd|orig|rej|bak|swp|log)$|(^|/)var/log/")

def sole_file(statement: str, root: str) -> str | None:
    """The one file the task lets production changes touch, when it names one."""
    if not EXCLUSIVE_FILE_RE.search(statement or ""):
        return None
    return declared_file(statement, root)

def envelope_trim(patch: str, beacon: "Beacon | None" = None,
                  only: str | None = None) -> str:
    if not PATCH_ENVELOPE or not (patch or "").strip():
        return patch
    sections = split_by_file(patch)
    if len(sections) < 2:
        return patch
    kept, dropped = [], []
    for section in sections:
        head = section.split("\n", 1)[0]
        path = head[len("diff --git "):].split(" b/", 1)[-1].strip().strip('"')
        # A file the run brought into being, when the task names the one file
        # it may change, is a scratch program or a check the run wrote for
        # itself -- written into the repository because that is where it
        # could import the code -- and left there when the run ended before
        # it could clear up.  It is not part of the answer, and it is the
        # answer's whole scope that the task set.  A file that was already
        # there is left alone: putting one back could undo what the change
        # needs, and the run was told to restore it itself.
        created = "\nnew file mode " in section.split("\n@@", 1)[0]
        if ENVELOPE_JUNK.search(path) or (only and created and path != only):
            dropped.append(path)
        else:
            kept.append(section)
    if not dropped or not kept:
        return patch
    if beacon is not None:
        beacon.fired("dropped %d of %d section(s): %s"
                     % (len(dropped), len(sections), ", ".join(dropped[:5])))
    return "".join(kept)

def produce(input: dict) -> str:
    """The run itself.  Guarded by `agent_main`, which cannot raise."""
    try:
        widen_path()
    except Exception:  # noqa: BLE001
        pass
    allowance = Allowance()
    root = os.getcwd()
    tree = Tree(root)
    pool = ShellPool(root)
    statement = str((input or {}).get("problem_statement") or "").strip()
    say("[RUN] budget=$%.3f clock=%.0fs"
        % (allowance.ceiling_usd, allowance.clock_left()))
    # Read before the run touches anything: it looks the file up on disk.
    only = None
    try:
        only = sole_file(statement, root)
    except Exception:  # noqa: BLE001 - the hand-in works without it
        pass
    findings = FindingMap(root) if FINDING_MAP else None
    if ELIXIR and elixir_project(root):
        say("[RUN] mix project: the project's own tests are read with `mix test`")
    bound = MemoryBound(pool)
    try:
        bound.arm()
    except BaseException as error:  # noqa: BLE001 - a watcher is never worth the run
        say("[RUN] the memory watch could not be armed: %s" % type(error).__name__)
    # Taking the answer out of the tree, putting the tree back and seeing
    # whether it applies all happen after this and all take real seconds.  A
    # writer bounded only by the run's own end takes those seconds too, and
    # then the run finishes inside a phase with no time to hand anything in --
    # which is how a long run comes back with nothing at all.
    kept = allowance.hold_back(TAIL_RESERVE_SEC)
    say("[RUN] the writer works to %.0fs, holding %.0fs back for the answer itself"
        % (allowance.clock_left(), TAIL_RESERVE_SEC))
    try:
        drive(statement, tree, pool, allowance, findings)
    except Spent as stop:
        say("[RUN] out of allowance: %s" % stop)
    except BaseException as error:
        import traceback
        traceback.print_exc()
        say("[RUN] crashed: %s: %s" % (type(error).__name__, error))
    # The hard stop guards the writing, not the hand-in: past this point the
    # tree is read and then put back, and a stop between the two would find it
    # already put back and hand in nothing.  Each step below bounds itself.
    disarm_hard_stop()
    # However the writing ended, the seconds held back are the run's again:
    # they were held back for what follows, and what follows is here.
    allowance.deadline = kept
    # What the run built to measure against goes with it.  Nothing reads the
    # scratch database, so leaving it costs nothing a check could see -- but a
    # run that builds a million rows on a server should not leave them there,
    # and it is one statement per connection that was written to.
    seen: set = set()
    for db in SCRATCH_MADE:
        if id(db) in seen:
            continue
        seen.add(id(db))
        try:
            db.run("DROP DATABASE IF EXISTS %s" % SCRATCH_DATABASE, timeout=10.0)
            say("[SQL] %s dropped on %s" % (SCRATCH_DATABASE, db.label))
        except BaseException:  # noqa: BLE001 - tidying up is never worth the run
            pass
    for closing in (bound.close, pool.close):
        try:
            closing()
        except BaseException:  # noqa: BLE001 - a watcher or a shell is never worth the run
            pass
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
    envelope = Beacon("envelope")
    envelope.reached(len(split_by_file(patch)), allowance.spent, allowance.clock_left())
    if not PATCH_ENVELOPE:
        envelope.skipped("not switched on for this run")
    else:
        before_patch = envelope.artefact("before", patch)
        try:
            patch = envelope_trim(patch, envelope, only)
        except Exception as error:
            envelope.skipped("the patch could not be read: %s" % type(error).__name__)
        envelope.outcome(before_patch, patch)
    envelope.bill()
    usable = None
    try:
        usable = tree.applies(patch, max(5.0, min(30.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:
        pass
    if usable is False and patch.strip():
        try:
            rescued = tree.salvage(patch, max(5.0, min(45.0, allowance.clock_left()
                                                      + WALL_RESERVE_SEC - 5)))
        except BaseException as error:
            say("[PATCH] salvage failed: %s" % type(error).__name__)
            rescued = ""
        if rescued:
            patch, usable = rescued, True
    if findings is not None:
        try:
            findings.report(patch)
        except BaseException:
            findings.beacon.skipped("the record could not be worked out")
    try:
        say("[SHAPE] " + patch_shape(patch))
    except BaseException:
        pass
    say(
        "[RUN] done in %.0fs, $%.4f over %d calls, %d edits, patch %dB, usable=%s"
        % (allowance.elapsed(), allowance.spent, allowance.calls, allowance.edits,
           len(patch), {True: "yes", False: "no"}.get(usable, "unknown"))
    )
    return patch


TEST_PATH_PATTERN = re.compile(
    # A test directory anywhere; a spec directory only at the root, where
    # RSpec keeps it, since `openapi/spec/` is a source directory.
    r"(?i:(^|/)(tests?|__tests__|test_?utils?)/|^specs?/)|(?i:(^|/)conftest\.py$|(^|/)test_[^/]*\.py$|"
    r"_test\.(py|go|exs|rb)$|_spec\.(rb|ex|exs)$|\.(test|spec)\.[cm]?[jt]sx?$)|"
    # `QueryTest.java`, `QueryTests.cs`: a capitalised name ending in Test.
    r"(^|/)[A-Z]\w*Tests?\.(cs|java|kt|scala|swift|php)$"
)


# Words only one of the two engines uses, for a file whose connection is not
# known.  Each is either a function the other does not have or a clause it
# does not take, so a file that writes one of them is writing for this
# engine whatever else is installed beside it.
_CLICKHOUSE_TONGUE_RE = re.compile(
    r"\bclickhouse\b|\btoStartOf\w+\s*\(|\btoDateTime64?\s*\(|\btimeSlots\s*\(|"
    r"\bngrambf_v1\s*\(|\bquantile(?:TDigest|Exact|GK)\w*\s*\(|\bargM(?:ax|in)\s*\(|"
    r"\bgroupArray\w*\s*\(|\bPREWHERE\b|\bSETTINGS\s+\w+\s*=|\bLIMIT\s+\d+\s+BY\b|"
    r"\bMergeTree\b|\bFINAL\b|\bintDiv\s*\(", re.I)


# == What the engine will not do ==
#
# Some mistakes in a query are not opinions about the task: the server simply
# will not do what the code now asks, or will do something other than what the
# code plainly expects.  A function that does not exist, a NULL test on a side
# of a join that never holds NULLs, a bucket rounded in the wrong clock.  These
# read the same as correct code and pass every check written against the
# ordinary case, so nothing catches them until the answer is wrong.
#
# They are checked here, against the lines the change added and nothing else,
# by code rather than by asking.  Code that knows the engine does not guess,
# does not cost anything, and does not fall silent when it is needed most.

ENGINE_FACTS = flag("RIDGES_ENGINE_FACTS")

_CALL_NAME_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_COMMENT_LINE_RE = re.compile(r"^\s*(?://|#|--|\*|/\*)")
# Names whose shape is unmistakably this engine's, so that an ordinary word
# followed by a bracket is never read as a query function.  Deliberately
# narrower than the engine's whole vocabulary: a miss says nothing, while a
# false complaint sends a correct change back to be rewritten.
_CH_FAMILY_RE = re.compile(
    r"^(?:quantiles?|median|uniq|argMin|argMax|groupArray|groupUniqArray|groupBit|any(?:Heavy|Last)|"
    r"topK|sumMap|minMap|maxMap|avgWeighted|histogram|sequence(?:Match|Count)|windowFunnel|retention|"
    r"simpleLinearRegression|stochastic|entropy|deltaSum|exponentialMovingAverage|sparkbar|"
    r"toStartOf|toRelative|toUnixTimestamp|toDateTime|toDate|toTimeZone|toIntervalp?|timeSlots?|"
    r"dateDiff|dateTrunc|addDays|addHours|addMinutes|subtractDays|arrayJoin|arrayMap|arrayFilter|"
    r"arrayReduce|JSONExtract|visitParam|bitmap|runningAccumulate|neighbor|lagInFrame|leadInFrame)")
# Longest first, and it matters: `Null` taken off `quantileOrNull` before
# `OrNull` leaves `quantileOr`, which is not a function, and a real name is
# reported as invented.
_CH_COMBINATORS = tuple(sorted(
    ("ArgMax", "ArgMin", "Array", "Distinct", "ForEach", "If", "Map", "Merge",
     "Null", "OrDefault", "OrNull", "Resample", "SimpleState", "State"),
    key=len, reverse=True))
_OUTER_JOIN_RE = re.compile(
    r"\b(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?\s+(?:ANY\s+|ALL\s+|ASOF\s+)?JOIN\b|"
    r"\b(?:leftJoin|rightJoin|fullJoin)\b", re.I)
# Only the forms that decide something.  `ifNull(x, 0)` and `coalesce(x, 0)`
# beside such a join are harmless: the column already holds the default, so
# they return the default either way and the code is right whether or not the
# author knew why.  Complaining about those asks for a guard to be taken out
# for a case that was never real, which is worse than the guard.  A branch is
# different: `isNull(x)` there is never true, and the code written for the
# missing row never runs at all.
_NULL_TEST_RE = re.compile(
    r"\b(?:isNull|isNotNull|assumeNotNull)\s*\(|\bIS\s+(?:NOT\s+)?NULL\b", re.I)
_JOIN_USE_NULLS_RE = re.compile(
    r"\bjoin_use_nulls\b['\"]?\s*(?:=>|=|:|,)\s*['\"]?(?:1|true)\b", re.I)
_TIME_SLOTS_RE = re.compile(r"\btimeSlots\s*\(")
_ZONE_WORD_RE = re.compile(r"toTimeZone|timezone|time_zone|\btz\b", re.I)
# name(a)(b)(c): a parametric aggregate takes the parameters and then the
# arguments, and nothing after that.
_CH_THREE_LISTS_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^()]*\)\s*\([^()]*\)\s*\(")
# An aggregate that is both DISTINCT and ordered, with what it aggregates and
# what it orders by.
# `/` on ClickHouse is Float64 division whatever it divides, and these
# functions take an integer there and refuse a float outright.
_CH_WANTS_INTEGER_RE = re.compile(
    r"\b(range|timeSlots|repeat|leftPad|rightPad|arraySlice|bitShiftLeft|bitShiftRight|"
    r"toFixedString)\s*\(([^()]*(?:\([^()]*\))?[^()]*)\)")
_BARE_DIVISION_RE = re.compile(r"[\w)\]]\s*/\s*[\w(]")
# A window over the whole result, beside a query that buckets its rows.
_EMPTY_WINDOW_RE = re.compile(r"\bOVER\s*\(\s*\)", re.I)
_BUCKETED_RE = re.compile(r"\b(?:GROUP\s+BY|toStartOf\w+|toStartOfInterval)\b", re.I)
# Keeping one row per key, and moving conditions to before the keeping.
_PICK_ONE_RE = re.compile(
    r"\brow_number\s*\(\s*\)\s*OVER\b|\bLIMIT\s+\S+\s+BY\b|\barg(?:Max|Min)\s*\(", re.I)
_PREWHERE_RE = re.compile(r"\bPREWHERE\b|optimize_move_to_prewhere\s*=\s*1", re.I)
# An n-gram Bloom filter whose grams are too short to be missing from anything.
_NGRAM_INDEX_RE = re.compile(r"\bngrambf_v1\s*\(\s*(\d+)", re.I)
# A quantile whose value moves with how the rows arrive.
_UNSTABLE_QUANTILE_RE = re.compile(
    r"\b(quantileTDigestWeighted|quantileTDigest|quantileGK|quantiles?|median)\s*\(")
_STABLE_QUANTILE_RE = re.compile(r"\bquantile(?:Exact|BFloat16)\w*\s*\(")
# Ecto checks a fragment's placeholder count when the module compiles.
_ECTO_FRAGMENT_RE = re.compile(r'''\bfragment\(\s*"((?:[^"\\]|\\.)*)"\s*(,.*)?\)''')

# Calls chained onto a query builder, each with the bracket depth it sits at,
# so that a call inside another call's arguments is not read as part of the
# same chain.
_CHAIN_CALL_RE = re.compile(r"\.\s*([A-Za-z_][A-Za-z0-9_]*[?!]?)")
_CHAIN_LIMITING = ("limit", "offset", "take", "first", "last", "Limit", "Offset")
_CHAIN_FILTERING = ("where", "rewhere", "filter", "exclude", "Where", "andWhere", "orWhere",
                    "whereIn", "having")
# A limit taken back off again is not a limit.
_CHAIN_CLEARED_RE = re.compile(r"\s*\(\s*(?:nil|None|null|0)\s*\)")
# Ruby reads the lines after a heredoc opener as its text, not as arguments.
_HEREDOC_OPENER_RE = re.compile(r"<<([~-]?)([\"'`]?)([A-Za-z_]\w*)\2")
_HEREDOC_ARGUMENT_RE = re.compile(r"^\s*[A-Za-z_@:][\w.:@!?\[\]()]*\s*[,)]\s*$")

_PG_DISTINCT_ORDER_RE = re.compile(
    r"\b(?:array_agg|string_agg|json_agg|jsonb_agg|sum|avg|count|min|max)\s*\(\s*DISTINCT\s+"
    r"(.+?)\s+ORDER\s+BY\s+(.+?)\)", re.I | re.S)

ENGINE_NOTES = {
    "ch_missing": (
        "`%s` is not a function on this ClickHouse server, so the statement fails the moment it "
        "runs. Look up what the server actually has -- `SELECT name FROM system.functions WHERE "
        "name ILIKE '%%part of the name%%'` -- and use one that exists. A combinator such as If, "
        "State, Merge or OrNull attaches to a real base name; it does not make one up."),
    "ch_lists": (
        "`%s` is given three or more argument lists. A ClickHouse parametric aggregate takes at "
        "most two -- name(parameters)(arguments) -- so the statement does not parse. Put every "
        "parameter in the first list."),
    "ch_outer_null": (
        "`%s` tests for NULL beside an outer join on ClickHouse. There a LEFT, RIGHT or FULL join "
        "fills the missing side's columns with the type's default -- 0, '', 1970-01-01 00:00:00 "
        "-- and not with NULL, unless join_use_nulls = 1 is set. So isNull(), ifNull() and "
        "coalesce() never see a NULL on that side and the branch meant for a missing row never "
        "runs. Put the join to the database on a key that exists on one side only and read back "
        "which value comes out, then test for that."),
    "ch_time_slots": (
        "`%s` builds buckets with timeSlots() in a statement that works in a named time zone. "
        "timeSlots() rounds each slot down to a multiple of its step in Unix time, not in that "
        "zone: with an hour step a zone offset such as +05:45 or +09:30 puts every bucket at :45 "
        "or :30 past the local hour. Build the buckets in the zone with toStartOfHour() and "
        "addHours(), or round afterwards, and check it against a zone whose offset is not a whole "
        "number of hours."),
    "ch_float_division": (
        "`%s` has a `/` inside an argument that has to be a whole number. On ClickHouse `/` "
        "returns Float64 whatever it divides -- two integers included -- and this function "
        "refuses a float there outright, so the statement fails the moment it runs. Divide with "
        "intDiv(a, b), or put toUInt32() or toInt64() round the quotient before it reaches the "
        "function."),
    "ch_window_bucket": (
        "`%s` is a window over every row of the result -- the brackets after OVER are empty -- "
        "in a statement that also puts its rows into buckets. A total meant for each bucket "
        "needs PARTITION BY the bucket expression; without it the same whole-result total is "
        "repeated against every bucket. Read the task again for which of the two it asks, then "
        "put the statement to the database and look at two buckets."),
    "ch_prewhere_pick": (
        "`%s` keeps one row for each key, and this statement also moves conditions to before "
        "the rows are read. A condition in the same SELECT as the pick runs on the raw rows, "
        "before the pick happens: where the rows sharing a key differ in the filtered column, a "
        "row that matches is kept instead of the one the pick would have chosen, so the "
        "condition stops testing the row that comes out. Keep beside the pick only conditions "
        "on columns every row of a key shares, and filter the rest outside it."),
    "ch_ngram_index": (
        "`%s` declares an n-gram Bloom filter on grams this short. A block is skipped only when "
        "a gram of the searched text is missing from that block's filter, and one filter covers "
        "thousands of rows: grams of three characters or fewer turn up somewhere in almost any "
        "such block, so almost nothing is skipped and the index costs space and writes for no "
        "reading. Use four or more."),
    "ch_quantile_unstable": (
        "`%s` estimates its quantile from however the rows happen to arrive, so the same rows "
        "can give different answers as the thread count, the block size or the parts on disk "
        "change. Where an exact value is being compared or asserted, use quantileExact or "
        "quantileExactWeighted, which answer the same way every time."),
    "ex_fragment_arity": (
        "`%s` has a different number of `?` placeholders than arguments after the string. Ecto "
        "counts them when the module is compiled and refuses the mismatch, so nothing in the "
        "module builds at all. Make the two counts the same."),
    "chain_filter_after_limit": (
        "`%s` filters the query after it has already been limited, on the same chain. The limit "
        "is applied first, so the filter picks over rows that were already cut down to the "
        "limit: the answer holds fewer rows than it should, and which rows it holds depends on "
        "the order the limit saw. Filter first and limit what is left."),
    "rb_heredoc_arguments": (
        "`%s` opens a heredoc on a line that ends in a comma, and the lines below it look like "
        "further arguments. Ruby reads everything down to the terminator as the heredoc's text, "
        "so those lines are part of the string and the call is made with fewer arguments than it "
        "appears to have. Close the call on the opening line and put the heredoc last, or bind "
        "it to a name first."),
    "pg_distinct_order": (
        "`%s` orders a DISTINCT aggregate by something other than what it aggregates. PostgreSQL "
        "refuses that outright -- \"in an aggregate with DISTINCT, ORDER BY expressions must "
        "appear in argument list\" -- so the statement never runs. Order by the aggregated "
        "expression itself, or drop DISTINCT and make the rows unique another way."),
}


def combinator_base(name: str) -> str:
    """The name with every combinator suffix taken off.

    Longest suffix first, and it matters: `Null` taken off `quantileOrNull`
    before `OrNull` leaves `quantileOr`, which is not a function, and a real
    name would be reported as invented.
    """
    current, changed = name, True
    while changed:
        changed = False
        for suffix in _CH_COMBINATORS:
            if current.endswith(suffix) and len(current) > len(suffix):
                current, changed = current[: -len(suffix)], True
                break
    return current


def clickhouse_names_used(diff: str) -> list:
    """The names in the lines this change added that could be functions here."""
    used: list = []
    for _, text in added_lines(diff):
        if _COMMENT_LINE_RE.match(text):
            continue
        for match in _CALL_NAME_RE.finditer(text):
            name = match.group(1)
            if _CH_FAMILY_RE.match(name) and name not in used:
                used.append(name)
    return used


# A name every server has.  It rides along in the question so that a reply
# which comes back empty for the wrong reason -- a client that printed nothing,
# an output cut short, a shape this code cannot read -- is told apart from one
# that came back empty because the names really are not there.  Without it a
# read that half worked would report every real function as invented, which is
# far worse than not checking at all.
_CH_CANARY = "count"
_CH_NAME_IN_JSON_RE = re.compile(r'"name"\s*:\s*"([A-Za-z_][A-Za-z0-9_]*)"')
_CH_BARE_NAME_RE = re.compile(r"^[ \t|]*([A-Za-z_][A-Za-z0-9_]*)[ \t|]*$", re.M)
CH_NAMES_ASKED_MAX = 60


def unknown_clickhouse_names(client: "SqlClient | None", used: list) -> set:
    """Which of these names this server does not have; empty when it cannot say.

    The server is asked about the handful of names the change actually wrote,
    rather than for its whole vocabulary: a list of everything comes back
    shortened, and a shortened list is indistinguishable from a server that is
    missing most of what it has.
    """
    if client is None or not used:
        return set()
    wanted: list = []
    for name in used[:CH_NAMES_ASKED_MAX]:
        for form in (name, combinator_base(name)):
            if form and form.isidentifier() and form not in wanted:
                wanted.append(form)
    asking = wanted + [_CH_CANARY]
    try:
        out = client.run("SELECT name FROM system.functions WHERE name IN (%s)"
                         % ", ".join("'%s'" % n for n in asking),
                         mode="query", limit=len(asking) + 10)
    except Exception:  # noqa: BLE001 - a server that will not answer is not a fault in the change
        return set()
    found = set(_CH_NAME_IN_JSON_RE.findall(out or ""))
    found |= set(_CH_BARE_NAME_RE.findall(out or ""))
    if _CH_CANARY not in found:
        say("[CREW] the server's function list could not be read; the names in the change "
            "are taken as written")
        return set()
    lowered = {n.lower() for n in found}
    missing = set()
    for name in used[:CH_NAMES_ASKED_MAX]:
        base = combinator_base(name)
        if not ({name, name.lower(), base, base.lower()} & (found | lowered)):
            missing.add(name)
    return missing


def added_lines(diff: str) -> list:
    """(line number in the file after the change, text) for each line the change added."""
    out: list = []
    number = 0
    for line in (diff or "").splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            number = int(match.group(1)) if match else 0
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            out.append((number, line[1:]))
            number += 1
        elif not line.startswith("-"):
            number += 1
    return out


def diff_hunks(diff: str) -> list:
    """Each hunk as (lines it added, every line in it), the second being context.

    The hunk is the unit because it is what sits together in the file.  A join
    at the top of a large file says nothing about an expression eight hundred
    lines below it, and reading the whole file for context turns every file
    that happens to contain one outer join into a file where no NULL test is
    allowed.
    """
    out: list = []
    added: list = []
    body: list = []
    number = 0
    started = False

    def close():
        if started:
            out.append((list(added), "\n".join(body)))

    for line in (diff or "").splitlines():
        if line.startswith("@@"):
            close()
            added, body = [], []
            match = re.search(r"\+(\d+)", line)
            number = int(match.group(1)) if match else 0
            started = True
            continue
        if line.startswith(("+++", "---")):
            continue
        if not started:
            continue
        if line.startswith("+"):
            added.append((number, line[1:]))
            body.append(line[1:])
            number += 1
        elif line.startswith("-"):
            body.append(line[1:])
        else:
            body.append(line[1:] if line.startswith(" ") else line)
            number += 1
    close()
    return out


def chain_calls(text: str) -> list:
    """(depth, name, where it ends) for each call chained in this text.

    Depth matters: `.where(` inside the brackets of another call is that
    call's argument, not the next link of the same chain.
    """
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
            match = _CHAIN_CALL_RE.match(text, index)
            if match:
                calls.append((depth, match.group(1), match.end()))
                index = match.end()
                continue
        index += 1
    return calls


def filtered_after_limit(text: str) -> str:
    """The filtering call that follows a limit on the same chain, or ""."""
    calls = chain_calls(text)
    for position, (depth, name, end) in enumerate(calls):
        if name not in _CHAIN_LIMITING or _CHAIN_CLEARED_RE.match(text, end):
            continue
        for later_depth, later, _ in calls[position + 1:]:
            if later_depth < depth:
                break
            if later_depth > depth:
                continue
            if later in _CHAIN_FILTERING:
                return later
    return ""


def heredoc_swallowed_arguments(lines: list) -> int | None:
    """The line of a heredoc opener that has eaten the arguments after it.

    A line that opens a heredoc and ends in a comma, with argument-shaped
    lines below it and the call's own bracket closing only after the
    terminator: everything between is the heredoc's text, so the call is made
    with fewer arguments than it reads as having.
    """
    for index, line in enumerate(lines):
        if _COMMENT_LINE_RE.match(line):
            continue
        opener = _HEREDOC_OPENER_RE.search(line)
        if not opener or not line.rstrip().endswith(","):
            continue
        terminator = opener.group(3)
        for ahead in range(index + 1, len(lines)):
            stripped = lines[ahead].strip()
            if stripped == terminator:
                return None
            if _HEREDOC_ARGUMENT_RE.match(lines[ahead]):
                return index
    return None


def engine_findings(diff: str, engine: str, missing: "set | frozenset | None" = None,
                    source: str = "") -> list:
    """(kind, name, line) for engine behaviour the lines this change added run into."""
    found: list = []
    if not ENGINE_FACTS or not (diff or "").strip():
        return found
    for added, context in diff_hunks(diff):
        added = [(number, text) for number, text in added
                 if not _COMMENT_LINE_RE.match(text)]
        if not added:
            continue
        # This one is read from the whole file: a setting written anywhere in
        # it makes every join in it return real NULLs, so a NULL test beside
        # one is right and must not be complained about.
        real_nulls = bool(_JOIN_USE_NULLS_RE.search(source or "")
                          or _JOIN_USE_NULLS_RE.search(context))
        outer_join = bool(_OUTER_JOIN_RE.search(context))
        zoned = bool(_ZONE_WORD_RE.search(context))
        found.extend(_hunk_findings(added, engine, missing, context,
                                    outer_join, real_nulls, zoned))
        # Read over the hunk's lines together: a heredoc opens on one line and
        # swallows the ones below it, so no single line shows the fault.
        where = heredoc_swallowed_arguments([line for _, line in added])
        if where is not None:
            found.append(("rb_heredoc_arguments", "a heredoc opened mid-call", added[where][0]))
    return found


def _hunk_findings(added: list, engine: str, missing, context: str, outer_join: bool,
                   real_nulls: bool, zoned: bool) -> list:
    found: list = []
    for number, text in added:
        if engine == "clickhouse":
            if missing:
                for match in _CALL_NAME_RE.finditer(text):
                    name = match.group(1)
                    if name in missing:
                        found.append(("ch_missing", name, number))
            for match in _CH_THREE_LISTS_RE.finditer(text):
                found.append(("ch_lists", match.group(1), number))
            test = _NULL_TEST_RE.search(text)
            if test and outer_join and not real_nulls:
                found.append(("ch_outer_null", test.group(0).rstrip("( "), number))
            if _TIME_SLOTS_RE.search(text) and zoned:
                found.append(("ch_time_slots", "timeSlots", number))
            for match in _CH_WANTS_INTEGER_RE.finditer(text):
                if _BARE_DIVISION_RE.search(match.group(2) or ""):
                    found.append(("ch_float_division", match.group(1), number))
            if _EMPTY_WINDOW_RE.search(text) and _BUCKETED_RE.search(context):
                found.append(("ch_window_bucket", "OVER ()", number))
            pick = _PICK_ONE_RE.search(text)
            if pick and _PREWHERE_RE.search(context):
                found.append(("ch_prewhere_pick", pick.group(0).rstrip("( "), number))
            for match in _NGRAM_INDEX_RE.finditer(text):
                if int(match.group(1)) <= 3:
                    found.append(("ch_ngram_index", "ngrambf_v1(%s" % match.group(1), number))
            loose_q = _UNSTABLE_QUANTILE_RE.search(text)
            if loose_q and not _STABLE_QUANTILE_RE.search(text):
                found.append(("ch_quantile_unstable", loose_q.group(1), number))
        else:
            later = filtered_after_limit(text)
            if later:
                found.append(("chain_filter_after_limit", later, number))
            for match in _ECTO_FRAGMENT_RE.finditer(text):
                holes = match.group(1).count("?")
                tail = (match.group(2) or "").strip().lstrip(",")
                if holes and tail:
                    # One level of brackets is enough for the shapes a
                    # fragment's arguments take; anything deeper is left alone
                    # rather than counted wrongly.
                    depth = given = 0
                    for ch in tail:
                        if ch in "([{":
                            depth += 1
                        elif ch in ")]}":
                            depth -= 1
                        elif ch == "," and depth == 0:
                            given += 1
                    given += 1
                    if depth == 0 and given != holes:
                        found.append(("ex_fragment_arity",
                                      "fragment with %d placeholder(s) and %d argument(s)"
                                      % (holes, given), number))
            for match in _PG_DISTINCT_ORDER_RE.finditer(text):
                argument = " ".join(match.group(1).split()).lower()
                terms = [re.sub(r"\s+(?:asc|desc)$", "", " ".join(t.split()).lower())
                         for t in match.group(2).split(",")]
                if any(term and term != argument for term in terms):
                    found.append(("pg_distinct_order", match.group(0)[:60], number))
    return found


def engine_text(found: list) -> list:
    """One note per kind, in the words the change can be rewritten from."""
    said, out = set(), []
    for kind, name, _ in found:
        if kind in said:
            continue
        said.add(kind)
        out.append(ENGINE_NOTES[kind] % name)
    return out


def chain_calls(text: str) -> list:
    """(depth, name, where it ends) for each call chained in this text.

    Depth matters: `.where(` inside the brackets of another call is that
    call's argument, not the next link of the same chain.
    """
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
            match = _CHAIN_CALL_RE.match(text, index)
            if match:
                calls.append((depth, match.group(1), match.end()))
                index = match.end()
                continue
        index += 1
    return calls


def filtered_after_limit(text: str) -> str:
    """The filtering call that follows a limit on the same chain, or ""."""
    calls = chain_calls(text)
    for position, (depth, name, end) in enumerate(calls):
        if name not in _CHAIN_LIMITING or _CHAIN_CLEARED_RE.match(text, end):
            continue
        for later_depth, later, _ in calls[position + 1:]:
            if later_depth < depth:
                break
            if later_depth > depth:
                continue
            if later in _CHAIN_FILTERING:
                return later
    return ""


def heredoc_swallowed_arguments(lines: list) -> int | None:
    """The line of a heredoc opener that has eaten the arguments after it.

    A line that opens a heredoc and ends in a comma, with argument-shaped
    lines below it and the call's own bracket closing only after the
    terminator: everything between is the heredoc's text, so the call is made
    with fewer arguments than it reads as having.
    """
    for index, line in enumerate(lines):
        if _COMMENT_LINE_RE.match(line):
            continue
        opener = _HEREDOC_OPENER_RE.search(line)
        if not opener or not line.rstrip().endswith(","):
            continue
        terminator = opener.group(3)
        for ahead in range(index + 1, len(lines)):
            stripped = lines[ahead].strip()
            if stripped == terminator:
                return None
            if _HEREDOC_ARGUMENT_RE.match(lines[ahead]):
                return index
    return None



class OutOfTime(BaseException):
    """Raised by the hard stop; a BaseException so that `except Exception` lets it by."""


def arm_hard_stop() -> bool:
    """Raise OutOfTime in the main thread shortly before the outer time limit, and keep
    raising it every few seconds, so a handler that swallows one cannot keep the run going."""
    if not hasattr(signal, "setitimer"):
        return False
    import threading
    if threading.current_thread() is not threading.main_thread():
        return False
    wall = num_env("AGENT_TIMEOUT", DEFAULT_WALL_SEC)
    after = max(HARD_STOP_FLOOR_SEC, wall - HARD_STOP_MARGIN_SEC)

    def stop(signum, frame):
        raise OutOfTime("the hard stop at %.0fs" % after)
    try:
        signal.signal(signal.SIGALRM, stop)
        signal.setitimer(signal.ITIMER_REAL, after, HARD_STOP_REPEAT_SEC)
    except (ValueError, OSError):
        return False
    return True


def disarm_hard_stop() -> None:
    try:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
    except (ValueError, OSError, AttributeError):
        pass


def agent_main(input: dict) -> str:
    """Hands back whatever the tree holds, and cannot do anything else.

    The one outcome worse than a poor change is no change: a run that ends in
    an exception hands back nothing, and nothing is worth nothing however much
    of the work was sound.  So this catches everything -- including what is
    raised before there is a tree to read, and what is raised while reading it
    -- tries once more for whatever the tree holds, and refuses to hand back
    anything that is not a string.
    """
    try:
        if arm_hard_stop():
            say("[RUN] hard stop armed %.0fs before the time limit" % HARD_STOP_MARGIN_SEC)
        patch = produce(input)
        disarm_hard_stop()
    except BaseException as error:  # noqa: BLE001
        disarm_hard_stop()
        import traceback

        traceback.print_exc()
        say("[RUN] the run itself failed: %s: %s" % (type(error).__name__, str(error)[:300]))
        patch = ""
        try:
            patch = Tree(os.getcwd()).diff(20.0)
        except BaseException:  # noqa: BLE001
            pass
    if not isinstance(patch, str):
        say("[RUN] the answer was %s, not a change" % type(patch).__name__)
        return ""
    return patch

_REPLICA_BUILD_STAMP = "d268c2"
