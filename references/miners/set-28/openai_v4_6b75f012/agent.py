from __future__ import annotations
import ast
import collections
import hashlib
import re
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
import importlib.machinery
import json
import os
import shlex
EMPTY_TIMEOUT_ROSTER_RESETS = 1
CALL_CLOCK_SHARE = 0.34
SEAT_RETRY_DECAY = 0.5
SEAT_RETRY_FLOOR_SEC = 20.0
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
SHELL_BUDGET_CEILING_SEC = 180.0
BACKGROUND_POLL_WAIT_SEC = 20.0
SQL_OUTPUT_CAP = 10_000
PROBE_BUDGET_SEC = 25.0
EMPTY_TIMEOUT_RESET_MIN_WALL_SEC = 180.0
SYNTAX_MARKERS = {
    ".ex": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
    ".exs": ("SyntaxError", "TokenMissingError", "MismatchedDelimiterError"),
}
CHARS_PER_TOKEN = 3.5
DEFAULT_WALL_SEC = 1500.0
COST_SHARE = 0.88
WALL_SHARE = 0.90
WALL_RESERVE_SEC = 45.0
PLAN_TURN_CAP = 40
TURN_CEILING = 150
TRANSCRIPT_FLOOR_CHARS = 40_000
DEFAULT_COST_LIMIT_USD = 0.29
UNKNOWN_CACHE_TERMS = (0.1000e-6, 131_072)
PLAN_MODEL = os.getenv("RIDGES_PLAN_MODEL", "openai/gpt-5.6-luna")
DRIVER_MODEL = os.getenv("RIDGES_AGENT_MODEL", "~openai/gpt-luna-latest")
RELIEF_MODEL = os.getenv(
    "RIDGES_RELIEF_MODEL", "deepseek/deepseek-v4-pro-0813"
)
FIRST_EDIT_DEADLINE_TURN = 5
SEAT_CACHE_TERMS = {
    "xiaomi/mimo-v2.5-pro": (0.0050e-6, 262_144),
    "xiaomi/mimo-v2.5": (0.0050e-6, 262_144),
    "minimax/minimax-m2.5": (0.0500e-6, 204_800),
    "minimax/minimax-m3": (0.0750e-6, 204_800),
    "deepseek/deepseek-v4-pro": (0.0036e-6, 1_048_576),
    "deepseek/deepseek-v4-pro-0813": (0.0220e-6, 1_048_576),
    "openai/gpt-5.6-luna": (0.0200e-6, 400_000),
    "~openai/gpt-luna-latest": (0.0200e-6, 400_000),
    "qwen/qwen3.8-2.4t-a95b": (0.2500e-6, 1_000_000),
    "@preset/qwen38-24t-lowthink": (0.2500e-6, 1_000_000),
    "openai/gpt-5.6-terra": (0.2000e-6, 400_000),
    "google/gemini-3.7-flash": (0.0375e-6, 1_048_576),
    "deepseek/deepseek-v4-flash-0731": (0.0280e-6, 1_048_576),
    "tencent/hy3": (0.0330e-6, 262_144),
}
FIRST_EDIT_TIME_REMAINING_SHARE = 0.80
BLANK_SUBMIT_MIN_WALL_SEC = 90.0
UNKNOWN_TOKEN_PRICE = (1.0e-6, 4.0e-6)
TRANSCRIPT_SPEND_SHARE = 0.35
TURNS_PLANNED = 50
FALLBACK_BASE_URL = "https://openrouter.ai/api/v1"
PLAN_READ_BUDGET = 150_000
PLAN_SPEND_SHARE = 0.75
PLAN_NOTE_CHARS = 4_000
MODEL_PRICING = {
    "qwen/qwen3.8-2.4t-a95b": (2.000e-6, 6.000e-6),
    "@preset/qwen38-24t-lowthink": (2.000e-6, 6.000e-6),
    "xiaomi/mimo-v2.5-pro": (0.600e-6, 1.201e-6),
    "xiaomi/mimo-v2.5": (0.140e-6, 0.280e-6),
    "minimax/minimax-m2.5": (0.150e-6, 0.900e-6),
    "minimax/minimax-m3": (0.375e-6, 1.500e-6),
    "deepseek/deepseek-v4-pro-0813": (0.660e-6, 1.980e-6),
    "~openai/gpt-luna-latest": (0.200e-6, 1.200e-6),
    "openai/gpt-5.6-luna": (0.200e-6, 1.200e-6),
    "openai/gpt-5.6-terra": (2.000e-6, 12.000e-6),
    "google/gemini-3.7-flash": (0.375e-6, 1.875e-6),
    "deepseek/deepseek-v4-flash-0731": (0.440e-6, 1.320e-6),
    "tencent/hy3": (0.132e-6, 0.528e-6),
}

WRAPUP_TURN = TURN_CEILING // 5
EDIT_PRESSES_MAX = 3
BLANK_REPLY_CEILING = 3
REPEAT_READ_CEILING = 2
REPLY_TOKEN_CEILING = 8000
REQUEST_ATTEMPTS = 4
INFLIGHT_RETRIES = 6
INFLIGHT_BACKOFF_SECONDS = (8.0, 16.0, 30.0, 45.0, 60.0, 60.0)
SEAT_REFUSED_WAIT_SEC = 20.0
SEAT_CALL_TIMEOUT_SEC = 90.0
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

REASONING_CONFIG = {"effort": "high", "exclude": True}

def one_line(value: object) -> str:
    """Whatever it was, on one line.

    Everything here writes one record per line and everything that reads it
    back splits on newlines, so a value that arrives with a newline in it does
    not make a long record -- it makes two, and the second is indistinguishable
    from a record this program wrote.  Anything reaching a record from outside
    goes through here first.
    """
    return " ".join(str(value or "").split())

def reply_fingerprint(message: dict) -> str:
    """A short name for what a reply decided, so two replies can be compared.

    Identical bytes given identical inputs is what a temperature of zero is
    for, and whether it holds is not otherwise visible: the log records what
    each call led to, never whether two calls said the same thing.  What is
    hashed is the decision -- the calls asked for and their arguments -- rather
    than the prose around them, because the prose can differ while the step
    taken is the same and the step is what the run turns on.
    """
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
    """How many tokens went on thinking before the reply, or -1 if unsaid.

    Whether a reply was thought about, and for how long, is chosen per call by
    whatever serves it and is not a setting this end holds.  Two runs of one
    file over one input can therefore have had different amounts of it, which
    makes it the first candidate whenever they diverge -- and it is reported in
    the usage of every call already, unread.
    """
    details = (usage or {}).get("completion_tokens_details")
    value = details.get("reasoning_tokens") if isinstance(details, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -1
    return int(value)
def flag(name: str, default: str = "1") -> bool:
    """Read a mechanism switch. Nothing in the environment sets these, so the default
    written here is the configuration that ships."""
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
LEDGER_READBACK = flag("RIDGES_LEDGER_READBACK")
MOVE_VERBATIM = flag("RIDGES_MOVE_VERBATIM", "0")
SUBMIT_CONFORM = flag("RIDGES_SUBMIT_CONFORM", "1")
PLAN_SEAT = flag("RIDGES_PLAN_SEAT", "0")
# The project's own suite, asked for narrowly rather than whole.
SUITE_SCOPE = flag("RIDGES_SUITE_SCOPE")
SUITE_IMPORTLIB = flag("RIDGES_SUITE_IMPORTLIB", "0")
SUITE_SHIM = flag("RIDGES_SUITE_SHIM")
NETWORK_FENCE = flag("RIDGES_NETWORK_FENCE")
SEARCH_LIMIT = flag("RIDGES_SEARCH_LIMIT", "0")
OUTLINE = flag("RIDGES_OUTLINE", "0")
FINDING_MAP = flag("RIDGES_FINDING_MAP", "0")
ELIXIR = flag("RIDGES_ELIXIR")
def num_env(name: str, default: float) -> float:
    try:
        value = float((os.getenv(name) or "").strip())
    except (TypeError, ValueError):
        return default
    return value if value == value and value not in (float("inf"), float("-inf")) else default
def say(message: str) -> None:
    """Best effort, and never a reason for anything else not to happen.

    Every mechanism in here books its state and then says what it did, in that
    order, because a line describing something that did not happen is worse
    than no line.  But the writing can fail on its own -- a closed pipe, a full
    disk -- and when it raises from there, the refusal that was about to be
    returned is not returned: the state is spent, the message never goes back,
    and the hand-in that a check was holding is waved through.  Telemetry does
    not get to decide that.
    """
    try:
        print(message, flush=True)
    except (OSError, ValueError):
        pass
class Beacon:
    """One mechanism's telemetry: reached, skipped, fired, artefact before and
    after, cost. The before/after pair reports whether the mechanism changed
    anything at all."""
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
    """Raised when neither budget can pay for another call."""
class Allowance:
    """The run's two hard walls, and the arithmetic that keeps us inside them."""
    def __init__(self) -> None:
        self.started = time.time()
        wall = num_env("AGENT_TIMEOUT", DEFAULT_WALL_SEC)
        self.ceiling_usd = num_env("RIDGES_MAX_COST_USD", DEFAULT_COST_LIMIT_USD)
        self.soft_usd = self.ceiling_usd * COST_SHARE
        self.run_window_sec = max(30.0, wall * WALL_SHARE - WALL_RESERVE_SEC)
        self.deadline = self.started + self.run_window_sec
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
        """Book one call. The endpoint's own figure wins when it sends one; the
        local table is an estimate and drifts from what is actually billed."""
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
    """The reply's tool calls in the shape they may be written back down.

    Arguments that are not JSON are answered in words by the dispatch below,
    but written back verbatim they stay in the history, and an endpoint that
    validates the history then refuses every later request rather than only
    the next.  An empty object in their place keeps the record valid and the
    turn unchanged: the call keeps its id and its name, so the result that
    follows still refers to a call that exists.
    """
    kept = []
    for call in calls:
        function = dict(call.get("function") or {})
        written = function.get("arguments")
        try:
            if not isinstance(written, str) or not written.strip():
                raise ValueError("nothing was written")
            # An object, not merely valid JSON.  `[]`, `null` and `1` all parse
            # and are all refused by an endpoint that requires the arguments to
            # be an object -- which is the same refusal this exists to prevent,
            # and it is the dispatch's own rule a few hundred lines below.
            if not isinstance(json.loads(written), dict):
                raise ValueError("not an object")
        except Exception:  # noqa: BLE001 - any unwritable form becomes empty
            function["arguments"] = "{}"
        kept.append({"id": call.get("id"), "type": "function", "function": function})
    return kept


def normalise_tool_call_ids(calls: list, turn: int) -> int:
    """Replace opaque provider IDs in one driver turn, in place.

    The same call objects feed both the assistant history and their following
    tool-result messages, so rewriting once before either is constructed makes
    a mismatched pair structurally impossible.  Dispatch does not read IDs; it
    continues to use only each call's function object.
    """
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
    """How much history this model can afford to re-read every turn, derived from
    its cache price so a costlier seat automatically runs leaner."""
    cache_price, window = SEAT_CACHE_TERMS.get(model, UNKNOWN_CACHE_TERMS)
    affordable = (ceiling_usd * TRANSCRIPT_SPEND_SHARE) / (TURNS_PLANNED * cache_price)
    tokens = min(affordable, window * 0.6)
    return int(max(TRANSCRIPT_FLOOR_CHARS, tokens * CHARS_PER_TOKEN))


# == The seat ==


# The reply endings this file knows how to act on.  Anything else is reported
# as "other": the field is filled in by whatever answered the request, and a
# log line is not the place for text this program never checked.
FINISH_REASONS = ("stop", "length", "tool_calls", "content_filter", "error", "")


def foreign(text: str) -> str:
    """A response body's size, in place of the body.

    What comes back from an endpoint that refused a request is text of
    unbounded length written by something on the other side of the network.
    Copying it into this program's output puts bytes nothing here has checked
    into a file that is read afterwards, and the status code printed beside it
    already says which kind of failure it was, so the size is the rest of what
    is worth keeping.
    """
    # `text or ""` would ask the object whether it is true, and an exception
    # is free to answer that however it likes -- including by raising, which
    # would lose the diagnostic this line exists to give.  Only None is absent.
    body = "" if text is None else str(text)
    return "%dB" % len(body.encode("utf-8", "replace")) if body else "empty"


class SeatRefused(Exception):
    """The endpoint will not serve this model at all."""


class SeatTimedOut(SeatRefused):
    """The seat did not answer inside the time this call was given.

    A refusal, because the answer is the same -- try the other seat -- and a
    distinct one, because a wall that says 403 is the endpoint's state while a
    seat that goes quiet is the seat's, and only the second is worth judging a
    seat on.  Before this existed a timeout ended the run outright, so the
    relief seat sitting on the roster was reachable only through a 403.
    """


def base_urls() -> list[str]:
    out = []
    for candidate in (
        (os.getenv("OPENROUTER_BASE_URL") or "").strip().rstrip("/"),
        FALLBACK_BASE_URL,
    ):
        if candidate and candidate not in out:
            out.append(candidate)
    proxy = (os.getenv("SANDBOX_PROXY_URL") or "").strip().rstrip("/")
    if proxy:
        for suffix in ("/api/v1", "/v1"):
            if proxy + suffix not in out:
                out.append(proxy + suffix)
    return out


class Seat:
    """The model, its fallback, and the accounting around one request."""

    # Class-level so a test double built with __new__ inherits an empty
    # roster instead of an attribute error.
    roster: list = []

    # Class-level so a test double built with __new__ inherits the run's own
    # behaviour rather than an attribute error.
    patient = True

    def __init__(self, allowance: Allowance, models: list | None = None,
                 patient: bool = True) -> None:
        self.allowance = allowance
        self.patient = patient
        if models:
            # A seat can be asked for by name, which is how a second one is
            # seated beside the driver without a second copy of the request
            # path: the refusal ladder, the retirement grades and the booking
            # are properties of a seat, not of which model is in it.
            self.models = list(models)
        else:
            self.models = [DRIVER_MODEL]
            if RELIEF_MODEL and RELIEF_MODEL != DRIVER_MODEL:
                self.models.append(RELIEF_MODEL)
        self.roster = list(self.models)
        self.original_models = list(self.models)
        self.empty_timeout_roster_resets = 0
        # How many calls each seat has lost to timeouts.  A seat is benched on
        # the first, because one slow call says nothing about the next; it is
        # retired on the second, because the restore that follows a bench
        # would otherwise put it straight back and the run can cycle between a
        # seat that will not answer and a wait for it to start.
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
        """Drop a model for good. Returns False when none are left.

        Off the roster too, so a refusal wall that later restores the roster
        cannot bring back a seat already judged on the quality of its answers.
        """
        if self.allowance.edits or not timeout_recovery:
            # Once a writer has changed the tree, a blank answer is a reason
            # to preserve its work, not to give the half-written change to a
            # different model. Before an edit, ordinary blank replies likewise
            # follow the scored parent's single-writer path: provider handoff
            # is reserved strictly for an observed transport timeout.
            return False
        if model in self.models and len(self.models) > 1:
            self.models.remove(model)
            if model in self.roster:
                self.roster.remove(model)
            say("[SEAT] retired %s, now on %s" % (model, self.models[0]))
            return True
        return False

    def ask(self, messages: list[dict], tools: list[dict] | None) -> dict:
        """One completion. Returns the assistant message, already booked."""
        # The share belongs to the completion, not to each seat that tries for
        # it.  Held per attempt, a bench hands the next seat a fresh allowance
        # off a clock the first one has already spent from, and two seats each
        # inside the bound are outside it together.
        budget = self._budget()
        # Shared by every model and every restored roster in this completion.
        # Without one shared counter, each bench/reset grants the same upstream
        # congestion a fresh retry ladder and can spend almost the whole run
        # waiting without ever reaching an edit.
        inflight_state = {"retries": 0}
        while True:
            model = self.current()
            try:
                return self._attempt(model, messages, tools, budget,
                                     inflight_state=inflight_state)
            except SeatRefused as refusal:
                say("[SEAT] %s refused: %s" % (model, str(refusal)[:200]))
                if self.allowance.edits:
                    # Once there is a diff, a second writer is more likely to
                    # disturb proved work than to rescue it. Pin the current
                    # writer so an ordinary refusal follows the scored
                    # parent's same-seat wait path. A timeout cannot benefit
                    # from that wait, so hand the current tree back directly.
                    self.models = [model]
                    self.roster = [model]
                    if isinstance(refusal, SeatTimedOut):
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
                    # Benched, not retired: a refusal is the endpoint's state,
                    # so the seat stays on the roster for a later restore.
                    self.models.remove(model)
                    say("[SEAT] benched %s, now on %s" % (model, self.models[0]))
                    if isinstance(refusal, SeatTimedOut):
                        # The timed-out request normally consumes its entire
                        # CALL_CLOCK_SHARE. Reusing that exhausted share makes
                        # the relief model present in the roster but impossible
                        # to call. A fresh share remains bounded by the current
                        # wall and is granted only while the tree is empty.
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
                    # The wait below is for a wall that may be lifted.  Silence
                    # is not a wall: nothing is going to be lifted, the roster
                    # is already exhausted, and this call has already spent its
                    # share of the clock going quiet.  Restoring the roster and
                    # asking the same seat again is the loop this whole change
                    # exists to remove, one level up.
                    raise Spent("every seat went quiet: %s" % refusal)
                # Nobody left to bench.  A seat somebody is waiting on does
                # not get to sit one out: the wait below is right for the run
                # itself, which has nothing else to do, and wrong for a seat
                # the run called into, which is spending the caller's clock.
                if not self.patient:
                    raise
                # While the clock can afford a wait, sit one out and put the
                # roster back; only the clock and the budget may end a run
                # that still has both.
                wait = min(SEAT_REFUSED_WAIT_SEC,
                           self.allowance.clock_left() - WALL_RESERVE_SEC - 60.0)
                if wait <= 0:
                    raise Spent("no seat will serve this run")
                say("[SEAT] every seat refused; asking again in %.0fs" % wait)
                time.sleep(wait)
                self.models = list(self.roster)
                # A deliberate wait for a wall to lift is not part of the share
                # the requests are held to, and the roster it restores is a
                # fresh set of seats to try.  Everything after it is a new
                # completion in all but name, so it is given a new allowance.
                budget = self._budget()

    def _budget(self):
        """How much of what is left one completion may spend asking.

        Returned as a pair of readings rather than a deadline, because the two
        clocks that matter can disagree: the wall says how long we have really
        been here, and the allowance is the one the run is held to.  Whichever
        has moved further is the honest one.
        """
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
        # A seat somebody is waiting on gets one sweep and a short one.  The
        # figures below are right for a run retrying on its own behalf, where
        # the only alternative to waiting is stopping; they are wrong for a
        # seat that was called into, because there the alternative is handing
        # control straight back, and every second spent here is spent out of
        # the caller's own remaining time.
        attempts = REQUEST_ATTEMPTS if self.patient else 1
        ceiling = SEAT_CALL_TIMEOUT_SEC if self.patient else 60.0
        # What this whole completion, retries and any seat after this one
        # included, may spend asking.  A plain share of what is left, with no
        # floor under it: a floor set at one full wait is not a bound at all
        # near the end of a run, where it lets a single request take most of
        # what remains and leaves nothing to hand in with.  When the share is
        # too small to wait usefully the sweep below stops instead.
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
            # The ladder, not the ceiling: every silence so far shortens what
            # the next attempt is granted.
            granted = max(SEAT_RETRY_FLOOR_SEC,
                          ceiling * (SEAT_RETRY_DECAY ** timed_out))
            for base in self.bases:
                room = min(share - spent_share(),
                           self.allowance.clock_left() - 10)
                if room < SEAT_RETRY_FLOOR_SEC:
                    # Too little left for an answer to arrive in.  Asking
                    # anyway spends what is needed to finish on a request that
                    # cannot come back in time, so the sweep stops here and the
                    # run gets to hand in what it has.
                    break
                asked += 1
                try:
                    request = urllib.request.Request(
                        base + "/chat/completions", data=payload, headers=headers
                    )
                    with urllib.request.urlopen(request, timeout=min(granted, room)) as response:
                        parsed = json.loads(response.read().decode("utf-8", "replace"))
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
                        # Stable dispersion prevents identical validator workers
                        # from returning on the same instant without making two
                        # identical runs choose different paths.
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
                        # The upstream request was rejected before generation;
                        # give the replacement request its own bounded call share.
                        return self._attempt(model, messages, tools, None,
                                             inflight_state)
                    if error.code == 403:
                        # The next base may carry its own credentials, so the
                        # sweep goes on; a sweep that met a refusal counts
                        # once, and one napped retry separates a wall that
                        # outlives a request from one that outlives the seat.
                        walled += 1
                        continue
                    if error.code in (400, 402, 413):
                        raise Spent("endpoint refused the request: " + sweep[-1])
                    if error.code == 429 and ("budget" in detail.lower() or "cost" in detail.lower()):
                        raise Spent("allowance exhausted upstream")
                except Exception as error:  # noqa: BLE001 - any transport fault retries
                    # A read that ran out raises the timeout itself; a connect
                    # that ran out arrives wrapped, with the timeout as the
                    # reason.  Both are the same event and only one of them
                    # looks like one.
                    reason = getattr(error, "reason", None)
                    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
                        timed_out += 1
                        quiet += 1
                        sweep.append("timed out after %.0fs" % min(granted, room))
                    else:
                        # The type, which is ours to read, and a description of
                        # the rest, which came from somewhere else.
                        sweep.append("%s: %s" % (type(error).__name__, foreign(error)))
            # Silence outranks a refusal.  A 403 says a door was shut; a
            # timeout says something was reached and did not answer, which is
            # a fact about the seat and the only one worth acting on.  The
            # ordering matters because the last base in this list is a local
            # fallback that refuses every request it is ever given: a rule of
            # "some base said 403" is therefore true of every sweep that fails
            # for any reason at all, and would report a seat that had simply
            # gone quiet as one that had been turned away.  A wall is a sweep
            # where a door was shut and nothing went quiet.
            if asked and walled and not quiet:
                refused_sweeps += 1
                refusal = " | ".join(sweep)
                if refused_sweeps >= 2:
                    raise SeatRefused(refusal)
            if attempt + 1 >= attempts or spent_share() >= share:
                # Nothing follows this sweep, so there is nothing for a wait to
                # help: the nap before giving up is time spent on a retry that
                # will not happen.
                break
            nap = min(backoff, max(0.0, self.allowance.clock_left() - 5),
                      max(0.0, share - spent_share()))
            if nap <= 0:
                break
            time.sleep(nap)
            backoff *= 2
        # Every base in the last sweep, in order, rather than whichever spoke
        # last: keeping only the last lets the local fallback's standing
        # refusal overwrite the real fault, naming the base that was never
        # going to work instead of the one that failed.
        said = " | ".join(sweep) or "no base was asked"
        if timed_out:
            # A seat that will not answer inside the time it has is one this
            # run cannot use, and there is a second on the roster.  Ending here
            # instead leaves that second seat reachable only through a refusal,
            # which is the wrong door: silence is the commoner way for a seat
            # to become unusable.
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
        # Which machine answered, which is not the same question as which one
        # was asked for.  A seat name is a request; what serves it is chosen
        # per call from a pool whose members differ in quantisation and in
        # whether they reason before answering, and neither of those is
        # anything this end selects or is told.  Two runs of identical bytes
        # over identical inputs can therefore have been answered by different
        # machines, which is the first thing to rule out when they disagree.
        # Recorded rather than acted on: nothing below reads it.
        served = one_line(parsed.get("provider") or parsed.get("served_by"))
        answered = one_line(parsed.get("model"))
        aside = ""
        if served:
            aside += " via=%s" % served[:40]
        if answered and answered != model:
            # The name that came back is not always the name that went out --
            # a dated id can fall through to whatever its prefix matches, and
            # the report would go on saying what was asked for.
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
            # Reported by its category and not by its wording: the field is the
            # far end's to fill and it is free to fill it with the request.
            named = finish if finish in FINISH_REASONS else "other"
            # A reply cut off mid-sentence is indistinguishable, further down,
            # from a seat that simply had little to say: both arrive as a short
            # message.  Whether that is happening at all is a property of the
            # seat and its token ceiling, so it is reported where the seat is.
            say("[SEAT] %s reply ended on %s after %d token(s)"
                % (model, named, int(usage.get("completion_tokens") or 0)))
        return message


# == The tree we are allowed to break and must hand back intact ==


# What this helper returns when the command did not finish, as opposed to
# finishing badly.  The two want opposite answers from a caller that is deciding
# whether something is true: a command that failed said no, and a command that
# ran out of time said nothing at all.
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
    except Exception as error:  # noqa: BLE001
        return 1, "%s: %s" % (type(error).__name__, error)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def run_piped(
    command: list[str],
    cwd: str,
    timeout: float = 60,
    stdin_text: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a command, optionally feeding stdin. Used by run_sql."""
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
        )
        return completed.returncode, completed.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as expired:
        partial = (expired.stdout or b"").decode("utf-8", errors="replace")
        return 124, "%s\n[timed out after %.0fs]" % (partial, timeout)
    except FileNotFoundError as missing:
        return 127, "command not found: %s" % missing
    except Exception as error:  # noqa: BLE001
        return 1, "%s: %s" % (type(error).__name__, error)


class Tree:
    """The checkout. The diff is read straight off it, so finishing costs no
    inference, and both the diff and the restore are anchored to the commit the
    run started on, so a commit or a stash made along the way cannot move the
    baseline out from under either one."""

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
        """Everything that changed since the run began, binaries included."""
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
        """Cheap tri-state probe: True/False, or None when git cannot tell."""
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
        """Does the diff we are about to hand in actually apply to a clean tree?

        Run after the restore, so the tree is the one the answer will be applied
        to.  A diff read off a working tree can still be unusable -- a path the
        run created and then removed, a binary hunk, a file the restore put back
        differently -- and an unusable diff is indistinguishable from no diff at
        all unless something says which of the two happened.
        """
        if not patch.strip():
            say("[PATCH] empty: the run finished without changing a line")
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="ridges-patch-", suffix=".diff")
        except OSError as error:
            # Not a pass.  Saying yes here would put "usable=yes" on a diff
            # nobody checked, which is the one thing this line exists to stop.
            say("[PATCH] could not be written out for checking: %s" % error)
            return None
        # Once the file exists, everything that could fail is inside the try:
        # a write that stops partway leaves it behind otherwise.
        try:
            with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(patch)
            code, out = git(["apply", "--check", path], self.root, budget)
        except OSError as error:
            # Worded apart from the line above it on purpose: the two failures
            # are a file that could not be made and a file that could not be
            # filled, and the errno they carry is routinely the same, so the
            # sentence is the only thing that tells them apart afterwards.
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
            # A check that ran out of time did not answer, and an answer is
            # what everything downstream of here reads this for: rebuilding
            # the diff out of the sections that "apply" would be rebuilding it
            # on the strength of a check that never finished.
            say("[PATCH] could not be checked in time")
            return None
        say("[PATCH] will not apply: %s" % out.strip()[:200])
        return False

    def salvage(self, patch: str, budget: float = 45.0) -> str:
        """The parts of the answer that still apply, when the whole does not.

        The runtime applies what comes back and rejects the whole answer when
        it does not apply, so a run that did the work scores exactly what a run
        that changed nothing scores.  The check above already says which of the
        two happened; a check that is right about the answer and changes
        nothing about it is worth no more than no check.

        Split out of the diff rather than taken from the tree, because by the
        time this is asked the tree has been put back and there is nothing left
        in it to diff.  Split per file, because what breaks a diff of this kind
        is a header rather than something spread across it; the files whose own
        section applies are the work that can still be handed in, and dropping
        the rest is weakly better than handing in nothing, which is what an
        unusable diff already amounts to.  Nothing here decides which file
        matters -- every section that applies is kept.
        """
        # One deadline for the rebuild rather than a fresh allowance per
        # section.  A section is checked with the same command as the whole
        # was, so a diff over many files could otherwise spend that allowance
        # once per file, and the seconds it spends here are the last ones the
        # run has: an answer that arrives after the run is killed scores what
        # no answer scores.
        deadline = time.time() + max(1.0, budget)
        parts = split_by_file(patch)
        if len(parts) < 2:
            # One section, or none that can be told apart: there is no subset
            # to fall back to, and re-checking the whole of it would only
            # repeat the answer that brought us here.
            say("[PATCH] nothing to salvage: %d section(s)" % len(parts))
            return ""
        kept, dropped, unread = [], 0, 0
        for part in parts:
            left = deadline - time.time()
            answer = self.applies_quietly(part, left) if left > 0 else None
            if answer is None:
                # Out of time, or a check that could not be run.  Whatever is
                # left is unread rather than refused, and nothing after this
                # will be quicker, so the rest goes unread with it.
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
            # Never handed back on a check that did not finish: the one thing
            # this must not do is put a diff nobody checked in place of one
            # that was checked and refused.
            # Not "in time": the quiet check answers unknown for a file it
            # could not write as well as for one it could not finish checking,
            # and a line that names only the clock sends a full disk to the
            # wrong place.
            say("[PATCH] salvage could not re-check its %d section(s)"
                % len(kept))
            return ""
        if not whole:
            # Each part applied and the whole does not, so the fault is not in
            # any one of them and this has nothing left to offer.
            say("[PATCH] salvage kept %d section(s) that will not apply together"
                % len(kept))
            return ""
        say("[PATCH] salvaged %d of %d section(s), dropped %d, unread %d"
            % (len(kept), len(parts), dropped, unread))
        return joined

    def applies_quietly(self, patch: str, budget: float) -> bool | None:
        """`git apply --check` with nothing said about it.

        Its own method rather than a flag on the one above, because the one
        above is a record of the answer and this is a step inside working one
        out: a salvage that printed a line per path would bury that record in
        its own workings.

        Three-valued for the same reason as the one above: a check that ran out
        of time did not say no, it said nothing, and a caller that reads it as
        no drops work over a question nobody answered.
        """
        if not patch.strip():
            return False
        try:
            handle, path = tempfile.mkstemp(prefix="ridges-part-", suffix=".diff")
        except OSError:
            return None
        # Everything after the file exists goes through the removal, including
        # the writing: a write that fails partway leaves the file behind, and
        # this is called once per section, so a full disk would be met by
        # leaving one file per section on it.
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
        """Put the tree back exactly as it was found, whoever changed it and by
        whatever means. Anything untracked before the run started is left alone."""
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
    """A tool refused its arguments. The model sees the text and tries again."""


CLIP_NOTE = "\n... [%d characters of %s elided] ...\n"


def bounded_output_file(path: str, cap: int, label: str = "output") -> str:
    """Read at most ``cap`` bytes while retaining both diagnostic ends.

    Small outputs are returned byte-for-byte after UTF-8 decoding. For large
    outputs the beginning preserves command context and the end preserves the
    verdict or traceback, matching ``clip`` without first allocating the
    discarded middle.
    """
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
    """At most `cap` characters back, the note about the cut included.

    Every tool result is cut twice at this size -- once here, once by the loop
    that appends it.  With the note outside the budget the first cut returns
    more than the budget, so the second lands on the first one's own words: the
    count is then of the middle of the middle, and the label names what the
    outer caller held.  Counting it in makes the second cut a no-op.
    """
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
    """One line per command: what was asked, and what came back.

    Almost everything this program learns, it learns from a command: which
    check it ran last, whether that check was clean, whether the project's
    tests pass.  None of that is in the reply text and none of it is in the
    branch names, so a log without it records what the program decided and
    nothing about what it was deciding on.

    The last non-empty line is kept because tools put their verdict there: a
    count of findings, a count of passing tests, a traceback's final line.  It
    is one line and it is clipped, so the cost is bounded and the log stays
    readable.
    """
    tail = ""
    for line in reversed((out or "").splitlines()):
        # The marker a command that has not finished carries is not something
        # it said; picking it up reports every unfinished command as having
        # produced nothing but that.
        if line.strip() and line.strip() != STILL_RUNNING:
            tail = line.strip()
            break
    say("[SHELL] %.1fs %dc :: %s :: %s"
        % (time.time() - job.started, len(out or ""),
           " ".join(job.command.split())[:SHELL_REPORT_CAP],
           tail[:SHELL_REPORT_CAP]))


# == Where the check said the findings were, and where the patch went ==


FINDING_CHECK = re.compile(r"^\s*ruff\s+check\b")
# Where the checker puts a line number, in each of the two shapes it prints.
# The full report -- what it gives when nothing asks otherwise -- points at the
# site with an arrow on a line of its own; the concise one puts the same three
# numbers at the head of the line.  Both are anchored, and neither is looked
# for in anything but the output of a check, so nothing else carrying a colon
# and a digit can get in.
FINDING_ARROW = re.compile(r"^\s*-->\s+(\S+?):(\d+):\d+\s*$", re.M)
FINDING_CONCISE = re.compile(r"^(\S+?):(\d+):\d+:\s", re.M)
HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def path_tail(name: str, root: str = "") -> str:
    """A path in the form a diff writes it, whatever form it arrived in.

    The check names files from wherever it was run, a diff names them from the
    top of the repository, and the two have to be the same key or every lookup
    misses and every patch reads as landing in a file nothing was reported on.
    """
    text = str(name or "").replace("\\", "/")
    base = str(root or "").replace("\\", "/").rstrip("/")
    if base and text.startswith(base + "/"):
        text = text[len(base) + 1:]
    while text.startswith("./"):
        text = text[2:]
    # A path from somewhere else keeps its leading separator.  Dropping it
    # would turn an absolute path this repository does not contain into a
    # relative one that looks as though it does.
    return text


def findings_from_text(out: str, root: str = "") -> dict:
    """path -> the line numbers a check's own output reports on it.

    What is read is the output the command already produced.  Nothing is run a
    second time: the checker has flags that rewrite the tree it is checking --
    one of them inserts suppression comments, and how many of those a file
    carries has to stay where it was -- and it reads argument files, so no
    reading of the command line can promise that repeating it only reports.  A
    copy that writes would put a different file in front of the command that
    follows it, which is the one thing a record is not allowed to do.
    """
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
    """path -> the line numbers the check reported on it."""
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
    """One entry per file section of a unified diff.

    A header is a line beginning `diff --git ` at column zero.  Anything
    inside a hunk carries a leading space, plus or minus, so the same words in
    the body of a change cannot be mistaken for the start of a section.
    """
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
    """path -> the numbers of the original lines a patch changes.

    The lines it removes, and the line an insertion sits in front of.  A hunk
    header covers its context as well, and counting context reports every edit
    as having reached wherever the surrounding three lines happened to begin.
    """
    out: dict = {}
    where = ""
    came_from = ""
    old = 0
    left = 0
    right = 0
    for line in (patch or "").splitlines():
        if left <= 0 and right <= 0:
            # Outside a hunk, and only outside a hunk, a leading marker names a
            # file.  Inside one it is the first character of a line of the file,
            # and a removed line whose own text begins with two dashes reads as
            # a header to anything that looks for headers everywhere.
            if line.startswith("diff "):
                # A new file begins here whether or not it goes on to name
                # itself, so nothing from the last one is carried into it.
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
    """The path a diff header names, or "" when it names no file at all."""
    text = name.strip()
    if text == "/dev/null" or not text:
        return ""
    if text.startswith(prefix):
        text = text[len(prefix):]
    return path_tail(text)


def finding_distances(findings: dict, touched: dict) -> list:
    """For every changed line, how far away the nearest reported finding is.

    A file the check reported nothing on is left out rather than counted as
    infinitely far: some of what a change needs is in files the check never
    named, and giving those a distance would report each of them as the worst
    case this measurement has.  They are counted separately instead.
    """
    out = []
    for where in sorted(touched):
        rows = findings.get(where)
        if not rows:
            continue
        for line in sorted(touched[where]):
            out.append(min(abs(line - row) for row in rows))
    return out


def finding_record(findings: dict, touched: dict) -> str:
    """One line: how far from what the check reported the patch landed."""
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
    """The line numbers the run's own check gave, kept for the first reading only.

    The check is run again after every edit, and from the second reading on its
    line numbers are the edited file's while a patch is written in the
    original's.  Keeping a later reading would put two coordinate systems side
    by side and call the difference between them a distance.
    """

    def __init__(self, root: str) -> None:
        self.root = root
        self.rows: dict = {}
        self.reads = 0
        self.beacon = Beacon("findings")

    def observe(self, command: str, out: str) -> None:
        """Read a check's own output.  Nothing is run and nothing is written."""
        text = one_line(command)
        if not FINDING_CHECK.match(text):
            # Not a check at all, and so not in this condition's population; a
            # line here would be one line per command the run makes.
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


class Shell:
    """A command that may outlive the turn that started it, so a slow test suite
    runs while the loop keeps reading code.

    Output goes to a file rather than a pipe: a pipe holds about 64KB before the
    writer blocks, and a test suite that fills it while nobody is reading stops
    dead. It also gets its own process group, so stopping it stops the whole
    tree of processes it started and not just the shell."""

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
        )

    def _text(self) -> str:
        try:
            self.sink.flush()
            return bounded_output_file(self.sink.name, TOOL_OUTPUT_READ_CAP, "tool output")
        except OSError:
            return ""

    def wait(self, timeout: float) -> tuple:
        """Returns (finished, output so far)."""
        try:
            self.process.wait(timeout=max(1.0, timeout))
            return True, self._text()
        except subprocess.TimeoutExpired:
            return False, self._text()

    def finished(self) -> bool:
        """Whether it is over, asked without waiting even a moment for it.

        ``wait`` has a one-second floor, which is the right shape for a caller
        that wants the answer and the wrong one for a caller that only wants to
        know whether to look.
        """
        return self.process.poll() is not None

    def drain(self) -> str:
        if self.process.poll() is None:
            return self._text() + "\n" + STILL_RUNNING
        return self._text()

    def stop(self) -> None:
        if self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    self.process.kill()
                except Exception:  # noqa: BLE001
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
            except Exception:  # noqa: BLE001
                pass
        self.jobs.clear()


# == Tools ==

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
                "ClickHouse, schema inspection, and trying a query. Wrap write "
                "experiments in BEGIN; ... ROLLBACK; on PostgreSQL."
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
            "name": "submit",
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


# The switch below changes what a tool offers, not only what it does.
# Declaring a parameter the run then ignores is worse than not offering it: the
# model spends a call setting it and reads the result as though it had.
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


# git subcommands that move history or throw work away. The diff is taken
# against the commit the run started on, so a commit no longer loses it, but a
# stash moves the change out of the tree and the patch comes back empty.
HISTORY_GIT = re.compile(
    r"\bgit\s+(?:-[^\s]+\s+)*(commit|stash|checkout|switch|restore|reset|clean|revert|rebase|merge|cherry-pick|push)\b"
)
# Reaching outside the container.  The task is answered entirely from the tree,
# so a command that fetches is either a way to read the change from the project
# it was taken from -- which is the answer, not the work -- or a way to spend
# the run waiting on a network that is not there.
#
# Anchored on the command rather than on the text of the argument: a run that
# greps its own sources for a URL, or reads a lint message that quotes one, is
# doing neither of those things, and a fence that stops it has cost a real
# reading to prevent an imaginary one.
NETWORK_COMMAND = re.compile(
    r"(?:^|[|&;]|\$\(|`)\s*(?:sudo\s+)?"
    r"(curl|wget|nc|ncat|telnet|ssh|scp|rsync|ftp|"
    r"git\s+(?:fetch|pull|clone|remote|ls-remote|submodule))(?![\w-])"
)
# Package installers are deliberately not on that list.  They are the one
# outward-looking family that is also a plausible repair: a project whose own
# suite will not import is often a project that was never installed into the
# environment, and installing it is the repair.  Nothing they can fetch is the
# answer to the task, so the leak this fence exists to close is not open
# through them, and an install with nothing to reach fails on its own in
# seconds.


# == What the task asks for, checked before the answer is handed back ==

# A path holding a test rather than the code under repair.  Editing one is not
# a fix, it is a change to the thing that decides whether the fix worked.
TEST_PATH = re.compile(
    r"(^|/)conftest\.py$|(^|/)tests?(/|$)|(^|/)test_[^/]*\.py$|_test\.py$")
NOQA_DIRECTIVE = re.compile(r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b", re.I)
# pytest's own summary of what went wrong, and of how much went right.
FAILED_TEST = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)
PASSED_COUNT = re.compile(r"(\d+) passed")
# What pytest says when it could not even collect, and why.  The names come
# from the short summary; the reason comes from the one-line tracebacks, and
# without it a reading that fails to start says only that it did not.
# The task names the file it is about inside the command it tells the run to
# satisfy, so the scope is read off that line rather than off the statement at
# large.
RUFF_COMMAND_LINE = re.compile(r"^.*\bruff\b[^\n]*$", re.M)
SOURCE_PATH_IN_TEXT = re.compile(
    r"[\w][\w./-]*\."
    r"(?:py|pyi|sql|go|rs|java|kt|kts|scala|rb|php|cs|js|jsx|ts|tsx|"
    r"c|cc|cpp|cxx|h|hh|hpp|hxx|sh)",
    re.I,
)
# A production-file restriction is stronger evidence than a path mentioned by
# a test or lint command.  It is deliberately anchored to restrictive wording
# and a backtick-delimited Python path, so prose that merely discusses a file
# cannot redirect the run's scope.
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
# What actually went wrong, as opposed to where.  The frame of an import
# failure is always the importer and never the import, so a record built from
# frames reads the same for a missing package, a syntax error and a circular
# import -- three faults that want three different answers.  The exception line
# is preferred; the frame stays as the fallback for a failure with no exception
# to name.
#
# The name is allowed dots and a tail, because a raised class arrives written
# however its module writes it -- `requests.exceptions.ConnectionError` and
# `ExceptionGroup` are both ordinary and neither is a bare word ending in
# `Error`.  The run of blank is spelled out rather than left as `\s`, which
# matches a newline and would let the search run past the end of the line it
# is reading.
SUITE_FAULT = re.compile(r"^E[ \t]+([\w.]*(?:Error|Exception)\w*)\b(.*)$", re.M)
SUITE_TIERS = ("", " --noconftest", " --noconftest --import-mode=importlib")

MISSING_MODULE = re.compile(r"ModuleNotFoundError: No module named '([A-Za-z_][A-Za-z_0-9.]*)'")
MISSING_DIST = re.compile(
    r"^(?:E[ \t]+)?(?:[\w.]+\.)?PackageNotFoundError: "
    r"No package metadata was found for "
    r"([A-Za-z0-9](?:[\w.-]*[A-Za-z0-9])?)[ \t]*$", re.M)
# How many stand-ins one run may write.  A project missing more than a handful
# is not a project with a gap, it is a project whose environment is absent, and
# a reading assembled out of that many stand-ins describes the stand-ins.
SUITE_SHIM_LIMIT = 6
SUITE_SHIM_MIN_GREEN = 0.5
# What a stand-in answers with.  Anything that can be called, subclassed,
# iterated, indexed or tested for truth, because a module that merely mentions
# the missing one while being imported does all of those.
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
    """Whether the interpreter can already find a module by this name.

    A message saying a name is missing is not the same as the name being
    missing: a package raises that message about itself from inside its own
    import when one of *its* dependencies is absent.  Standing in for such a
    name replaces a package that is installed and working with an empty one --
    and this import path is searched ahead of the standard library, so the name
    to be careful about includes every name the standard library has.
    """
    try:
        import importlib.util

        return importlib.util.find_spec(name) is not None
    except BaseException:  # noqa: BLE001 - a name that cannot even be looked up is left alone
        return True


def missing_modules(out: str) -> list:
    """The top-level names a reading says it could not import.

    Only top-level ones, and only ones the interpreter really cannot find.  A
    dotted name is a module inside a package that may itself be installed, and
    a stand-in for the package would shadow the real one rather than fill the
    gap in it; a name that resolves is one the message was raised *about* from
    inside, not one that is absent.
    """
    seen = []
    for name in MISSING_MODULE.findall(out or ""):
        if "." in name:
            continue
        if name not in seen and name.isidentifier() and not resolvable(name):
            seen.append(name)
    return seen


def missing_dists(out: str) -> list:
    """The distributions a reading says have no installed record."""
    seen = []
    for name in MISSING_DIST.findall(out or ""):
        # `dist-info` names normalise to this, and anything that does not fit
        # would be a directory name taken from a message rather than a name.
        if name not in seen and re.fullmatch(r"[A-Za-z0-9._-]+", name):
            seen.append(name)
    return seen


def inside(path: str, root: str) -> bool:
    """Whether `path` is the same place as `root` or somewhere under it.

    Both sides are resolved first, so a temporary directory reached through a
    link that lands in the tree answers yes.  It answers rather than raising,
    because it is asked from inside the one rung whose failure the caller
    handles and an exception out of it loses the run's baseline for a reason
    that has nothing to do with the project -- and where it cannot tell, it
    answers yes, because the cost of the two mistakes is not the same: a
    stand-in written somewhere safe and refused costs a reading, and one
    written into the tree costs the hand-in.
    """
    try:
        path, root = os.path.realpath(path), os.path.realpath(root)
        if (os.path.splitdrive(path)[0].lower()
                != os.path.splitdrive(root)[0].lower()):
            # Nothing in common at the very top, which is the one way of being
            # unrelated that the comparison below reports by raising rather
            # than by answering.
            return False
        return os.path.commonpath([path, root]) == root
    except (ValueError, OSError, TypeError):
        # What this decides is whether something may be written into the tree
        # that gets handed in, so not being able to tell is answered the same
        # way as being able to tell that it is inside.
        return True


def write_dist_records(names: list, where: str) -> list:
    """The smallest thing `importlib.metadata` accepts as an installed record.

    A directory and one file.  It answers `version()` and nothing else, which
    is all that is being asked: the question is not what the project's version
    is, it is whether the import gets past the line that asks.
    """
    made = []
    for name in names:
        try:
            # The directory carries the escaped form and the file carries the
            # name as asked for.  A record written under the name verbatim is
            # not found under it: the reader splits the directory on the first
            # hyphen to separate name from version, so `demo-project-0.0.0`
            # answers to `demo` -- which is both a miss on what was asked and a
            # record standing in for something nobody named.
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
    """Write one stand-in per name into `where`. Returns the ones written.

    As a package rather than as a module, because the import that failed is as
    often `from x.y import z` as it is `import x`, and a module file called
    `x.py` cannot carry a `y`.  A package whose `__init__` answers for its own
    subtree can.
    """
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

# Long-run cap. Allowance scales this to one third of a shorter usable
# window, with a floor that still lets an ordinary focused suite complete.
SUITE_BASELINE_SEC = 300.0
SUITE_RECHECK_SEC = 240.0
# How long the hand-in may be held for a baseline that is merely slower than
# the run that started it.  Sized above what a reading that is going to land
# takes rather than as a share of anything: a window that ends before the
# ordinary case only ever catches the projects that were never going to answer.
SUITE_SETTLE_SEC = 90.0
# How many times the run may be sent back.  Unbounded, a check that the run
# cannot satisfy becomes a loop that spends the rest of the budget arguing; at
# zero it is not a check at all.
WARDEN_REFUSALS_MAX = 3
# How many changed-side names are asked about a second time.  A second run of
# hundreds of them is not a cheap question, and a handful is enough to say what
# broke.
CONFIRM_MAX = 12
# Below this there is no time to act on a refusal, and refusing anyway converts
# a flawed answer into no answer.
WARDEN_RELEASE_SEC = 150.0
# What ANY rung needs before it may start a reading: a refusal's worth, and on
# top of it the longest the hand-in will wait for what it starts.  A rung that
# only checks the refusal's worth can start a reading, have the hand-in wait
# out that wait, and leave less than a refusal needs -- at which point the
# checks that need no reading at all, a dropped definition or an added
# suppression comment, are released unasked.  One rule for every rung rather
# than one per rung: they all spend the clock the same way.
RUNG_MIN_WALL_SEC = WARDEN_RELEASE_SEC + SUITE_SETTLE_SEC
# Added to the refusal a broken suite produces, and to that one only.  A run
# that is told which tests broke still has to work out why, and the why is
# almost always the same shape: a value the original branch handled one way is
# handled another way now.  Asked as an open invitation to review, that
# question gets answered "something is wrong here" about answers that were
# right; asked about a suite that is already red, it has a right answer and
# the evidence to check it against.  Costs no turn and no call: it is text on
# a refusal that was going out regardless.
WARDEN_QUESTION = (
    " Before changing anything, name it: which kind of input that this file "
    "already handles does the patched code treat differently from the "
    "original, and on which line? If nothing does, the cause is not the "
    "change in behaviour and the named tests are where to look."
)
# The pause before the hand-in needs strictly more than the warden's release:
# whatever the pause buys still has to fit a model turn, the edits it asks for,
# and the warden's own re-check of them.  Equal thresholds would let the pause
# consume exactly the seconds the re-check was promised.
CONFORM_MIN_WALL_SEC = 300.0
# What bounds writing stand-ins and reading again.  Deliberately not a count of
# attempts: an interpreter reports an unresolved import one at a time, and the
# next name is only raised once the import ahead of it has succeeded, so an
# environment missing three things needs three readings to name all three.  A
# fixed number of attempts stops short of recovering exactly the environments
# that are most absent, which are the ones this rung exists for.  What bounds
# it instead is the shim budget -- an attempt may only run if it has something
# new to write, so there cannot be more attempts than there are names allowed
# -- and the clock.
#
# Strictly more than the pause before the hand-in needs.  A chain as long as the
# environment is broken could otherwise walk straight through the seconds a
# check that needs no reading at all was going to run on, and silence it.  One
# rule: a source of readings may not spend another check's allowance.
STANDIN_MIN_WALL_SEC = CONFORM_MIN_WALL_SEC + SUITE_SETTLE_SEC


LEDGER_BULLET = re.compile(r"^[-*][ \t]+(.*)$")
LEDGER_FENCE = re.compile(r"^[ \t]*(?:```|~~~)")
# Three, not two.  Picking the list by shape rather than by heading means the
# longest run wins, and in a statement that has no clause list at all the
# longest run is whatever else happens to be bulleted -- the files that may be
# touched, a two-line aside.  Two bulleted lines are as likely an aside as a
# list; a run of three is committed to being one.
LEDGER_MIN = 3
# Its own bound, not the warden's. The refusal budget is shared, and a source
# that spends all of it leaves the two that are there to catch a broken suite
# or an edited test with nothing left to refuse with -- for the rest of a run
# in which they have not fired once.
LEDGER_MAX_ASKS = 2


def bullet_runs(text: str) -> list[list[str]]:
    """Every unbroken run of top-level bullets, in the order they appear.

    Fenced blocks are skipped whole: an example of a list is not a list.  A
    line indented under a bullet continues it, and any other prose ends the
    run, because the paragraph after a list is commentary on it.
    """
    runs: list[list[str]] = []
    current: list[str] = []
    fenced = False
    for line in (text or "").splitlines():
        if LEDGER_FENCE.match(line):
            # A block quoted at the left margin is not part of a list; it is
            # something shown between two of them.  Skipping it without ending
            # the run sews two unrelated lists into one, and the sewn pair can
            # be longer than the list that matters.  A fence indented under a
            # bullet belongs to that bullet and ends nothing.
            # `not fenced`, so this is the opening of a block rather than the
            # close of one.  A block opened under a bullet and closed at the
            # margin is ordinary, and treating that close as an opening cuts
            # the list in half at the bullet that carried the example.
            if current and not fenced and not line[:1].isspace():
                runs.append(current)
                current = []
            fenced = not fenced
            continue
        if fenced:
            continue
        # Matched against the line as written, not against it stripped: an
        # indented bullet is a note under the entry above it, and counting it
        # as an entry of its own inflates a two-line aside into something that
        # can outrank the list this is looking for.
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
    """What the statement asks for, in its own words, one entry each.

    Read with no judgement at all, and that is the point.  A run can end
    without solving the task because it believes it is finished rather than
    because anything ran out, and what it believes is finished can still be
    missing something the statement named outright -- there is nothing between
    that belief and the hand-in that would notice.  Independent runs of one
    task take different paths from the first reply onwards, but the statement
    they are given is the same text, so a list taken off it without asking
    anybody is the same list on every one of them, character for character.
    Anything decided by a model here would be one more thing for them to
    differ over.

    Found by shape rather than by heading.  A statement introduces its clause
    list with whatever sentence suits it, so there is no wording to key on, and
    a reader that waits for one particular heading answers "nothing was asked"
    for every statement that phrases the introduction differently -- which is
    indistinguishable, from here, from a statement that really asks nothing.
    What a clause list does have, whatever introduces it, is that it is a run
    of top-level bullets and that it is the longest such run in the statement:
    anything else bulleted there is an aside.  So take the longest run; whether
    it is long enough to be a list at all is held to a floor by the caller.
    """
    runs = bullet_runs(text)
    if not runs:
        return []
    return max(runs, key=len)


LEDGER_GUARD = re.compile(
    r"\b(preserve|preserves|keep|keeps|retain|retains|remain|remains|"
    r"continue|continues|unchanged|intact|still|do not|don't|must not|"
    r"never|leave|leaves|untouched)\b", re.I)


def wants_an_edit(item: str) -> bool:
    """Whether this asks for something to be done or for something to survive.

    Counted for the record only.  Acting on the difference would mean deciding
    which half of the list to withhold, and the whole list costs nothing to
    show.
    """
    return not LEDGER_GUARD.search(item or "")


def read_back(items: list[str]) -> str:
    """The refusal: the statement's own list, put back in front of the run.

    It names nothing the run did and passes judgement on nothing it wrote.
    That restraint is what keeps it from being a review: an invitation to
    re-examine work produces objections to work that was right, since the same
    reading that made the change is the one asked to doubt it. An omission is a
    different kind of thing -- it is visible only against the list it was
    omitted from, and reading that list needs no opinion about anything that
    was written.
    """
    lines = "\n".join("  %d. %s" % (n + 1, item) for n, item in enumerate(items))
    return ("Before this goes in, put the diff beside what the task asked for. "
            "These are its own words:\n%s\n"
            "Anything on that list with nothing in the diff answering for it "
            "is not done yet; do those now. Where the list asks that existing "
            "behaviour be kept, leaving that code alone is how it is met. If "
            "every item already has something answering for it, hand in again "
            "-- this is asked once." % lines)


def importable(path: str) -> bool:
    """Can anything reach this file by name?

    Asked of the interpreter rather than answered with a literal, because the
    set of things it will load is its property and not this program's opinion.
    A file it will not load carries no callable name however it happens to
    parse, so a note or a template that reads as valid source is still a note.
    """
    return any(path.endswith(suffix) for suffix in importlib.machinery.SOURCE_SUFFIXES)


# The one directory below the top that projects put their own code in.  Named,
# and the naming is the point of the note below.
NESTED_SOURCE = "src"


def package_roots(root: str) -> list[str]:
    """The directories to import this copy of the project from.

    Deliberately just two: the tree, and the one place below it that projects
    conventionally keep their own code.

    The general version of this -- every directory below the top that holds
    something importable -- was written, run, and withdrawn.  It also picks up
    the directories holding tests, examples and benchmarks, and putting those
    on the import path lets a helper of theirs shadow a module of the standard
    library -- a file named for what it helps with, sitting in a directory that
    is now searched first, and the interpreter finds it instead of the module
    the project meant.  A reading taken through that is not a reading of the
    project, and the failure arrives as the standard library importing itself
    halfway through, which names nothing that would lead back here.

    So the narrow rule is kept and its hole is stated rather than papered over:
    a project that keeps its code somewhere else again, and is installed in
    development mode, will be read through the pointer that install leaves
    behind, which addresses the live tree.  That makes the baseline agree with
    the end of the run and the difference find nothing -- less than this could
    have found, never something it should not have found.
    """
    nested = os.path.join(root, NESTED_SOURCE)
    return [root, nested] if os.path.isdir(nested) else [root]


def declared_file(statement: str, root: str) -> str | None:
    """The one file the task is about, read off the command it hands the run.

    Taken from the line carrying that command rather than from the statement at
    large.  A burndown statement also names the test files the answer must not
    touch, and often the module they cover; a scope taken from the first path
    anywhere in the text is as likely to be one of those, and a suite scoped to
    the tests it was told to leave alone is a suite that cannot see the change.
    """
    explicit = DECLARED_FILE_SCOPE_RE.search(statement or "")
    if explicit:
        candidate = explicit.group("path")
        if (not TEST_PATH.search(candidate)
                and os.path.isfile(os.path.join(root, candidate))):
            return candidate

    # An Elixir statement names its file the same way and its test files with
    # the suffix mix reserves for them.  Asked before the lint-target walk
    # below, which is about a Python formatter and answers nothing here.
    if ELIXIR:
        for candidate in ELIXIR_PATH_IN_TEXT.findall(statement or ""):
            if candidate.endswith("_test.exs"):
                continue
            if os.path.isfile(os.path.join(root, candidate)):
                return candidate

    # Fold shell continuation lines before looking for a lint target.  A
    # formatter commonly prints ``ruff ... \\`` and the path on the following
    # line; treating physical lines as commands loses the only source path.
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
ELIXIR_PATH_IN_TEXT = re.compile(r"(?<![\w/])((?:[\w.\-]+/)+[\w.\-]+\.exs?)(?![\w])")
DECLARED_DEFINITION_RE = re.compile(
    r"\bspecifically\s+`?(?:(?P<owner>[A-Za-z_]\w*)\.)?"
    r"(?P<name>[A-Za-z_]\w*)\(\)`?",
    re.I,
)
EXCLUSIVE_FILE_RE = re.compile(
    r"\b(?:edit only|may edit only|only edit|limit (?:production )?changes to|"
    r"production changes (?:are )?limited to|change only|touch only|modify only|"
    r"changes? (?:must be |are )?(?:limited|confined|restricted) to)\b",
    re.I,
)
METHOD_TICK_RE = re.compile(r"`((?:[A-Za-z_][\w]*\.)*)([A-Za-z_]\w*)\(\)`")
FUNCTION_ARITY_RE = re.compile(r"`((?:[A-Z]\w*\.)*)([a-z_]\w*[!?]?)/(\d+)`")
CONSTRUCT_BAN_RE = re.compile(
    r"no python loops|plain orm expressions|no python loops, comprehensions", re.I
)
IMPORTS_FROZEN_RE = re.compile(
    r"including imports|only names the file already imports|do not (?:add|change) imports",
    re.I,
)
SIGNATURE_FROZEN_RE = re.compile(
    r"keep (?:its|the|the method) signature|signature (?:unchanged|intact|the same)",
    re.I,
)
REST_FROZEN_RE = re.compile(
    r"rest of (?:its|the|that) file (?:unchanged|as it is|exactly)|"
    r"everything else in (?:that|the) file|all unrelated source|"
    r"unrelated (?:source|code) (?:unchanged|as it is)",
    re.I,
)


def declared_definition(statement: str) -> tuple[str | None, str] | None:
    """The class/method scope the statement explicitly names, if any.

    Prefers the word ``specifically``, then a unique backticked ``Owner.name()``
    or ``name()``.  Same contract the warden later enforces; never a guess
    among several named methods.
    """
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
    """Find exactly one explicitly named function or method."""
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
    """Return everything outside the target plus its callable signature."""
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
    """Why the answer above was the answer, in one line.

    Finding nothing sends the reading at the whole repository, and "found
    nothing" covers four faults that want four different fixes: the statement
    never carries the command at all, it carries it with the path on a
    continuation line, the path is on the line but is not a file at this root,
    or the only path there is one the test filter drops.  From the outside all
    four look the same, and the statement itself is not written down anywhere
    afterwards -- so the run has to say which one it met while it still has it.

    Counts only, never the paths themselves.  It reads nothing the answer above
    did not already read, and decides nothing.
    """
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
    """Which of the project's tests to read, narrowest first.

    The task asks a scoped question -- what it refuses names one suite of the
    project, not all of them -- and asking the whole repository instead is
    worse in both directions.  It is slower, which is why
    a project whose suite outlasts the run leaves the condition never armed at
    all; and it is a different question, so an answer that does arrive is not
    the one the task asked about.

    Everything returned is relative to the repository, because the same list is
    rendered against two roots: the separate checkout the baseline is read
    from, and the working tree the re-check runs in.  An absolute path would
    quietly point the second one at the first.

    An empty list means the whole repository, which is what this did before and
    is still the right answer when nothing narrower can be named.
    """
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
    # Then a file named after the module, or after one of its directories.
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
    """The size and the make-up of a diff, in one line.

    Size alone cannot tell a move from a rewrite: taking a span out and
    putting the same span back somewhere else, and taking it out and writing
    something new in its place, are the same count of lines either way.  So
    the removed lines are matched against the added ones and reported as two
    numbers rather than one -- how many came back, and how many did not.

    Whitespace at either end is not part of the match.  A block that moves
    into or out of a loop is reindented by the move itself, and counting that
    as a change would call every move a rewrite, which is the distinction
    being drawn; trailing whitespace goes the same way, and a line whose only
    change is at its ends is reported as having come back.

    A removed line carrying nothing but brackets, commas or a colon is left
    out of the pair entirely rather than counted on either side: it matches
    something in almost any body of code, so counting it would say more about
    how common it is than about this diff.  The two numbers therefore need
    not add up to the removed count.

    Which lines count is decided by where they are rather than by how they
    start: a file's own header lines begin with the same two characters a
    changed line does, and a removed line whose text happens to start with
    `--` is indistinguishable from a header until the position is used.  So
    only what follows a hunk header is content, up to the next file.  That
    framing is the one `git diff` produces over a working tree, which is
    where this is called from; a merge's combined form marks its files and
    hunks differently and is read here as carrying neither.
    """
    files = hunks = 0
    added: list = []
    removed: list = []
    inside = False
    for line in (patch or "").split("\n"):
        if line.startswith("diff --git "):
            # Counted per stanza rather than per distinct path: two stanzas
            # are two files even when a copy leaves them sharing a source.
            files += 1
            inside = False
        elif line.startswith("@@ "):
            hunks += 1
            inside = True
        elif inside and line.startswith("+"):
            added.append(line[1:].strip())
        elif inside and line.startswith("-"):
            removed.append(line[1:].strip())
    # Counted as a multiset: a line taken out twice and put back once came
    # back once, and calling that "carried" would hide the half that did not.
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
    """The definitions a reader of the module can name, as a sorted multiset.

    Definitions nested inside a function body are deliberately not counted:
    lifting a block into a local helper is the ordinary way to reduce a
    function's complexity and must stay allowed, while moving a method out of
    its class changes the name it is carried under and is how a refactor
    quietly deletes an interface.
    """
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
    """Where each definition begins and ends, in the order the file has them.

    Reading a file a window at a time is what stops one call from returning
    everything, but it also makes the first window a guess: a reader who does
    not know which lines hold the function cannot ask for them.  This answers
    that for one call and no reading at all.

    Nested definitions are kept here, unlike the multiset above.  There the
    name a method is carried under is the whole question; here the only
    question is which range to ask for next, and a helper buried inside a long
    function is exactly what a reader is trying to find.

    Raises SyntaxError, which is the caller's to report: a file that does not
    parse has no index, and saying so is more use than an empty one.
    """
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
                # A definition under an `if` or a `try` at the top of a module
                # is still one of the module's own, so the depth it is shown at
                # follows the definitions it is nested in and nothing else.
                walk(child, depth)

    walk(ast.parse(source), 0)
    rows.sort()
    return ["%5d-%-5d %s%s" % (start, end, "  " * depth, name)
            for start, end, depth, name in rows]


class Warden:
    """The task's own conditions, settled here rather than left to chance.

    A refactoring task states what must still hold when it is done: the
    project's tests keep passing, the definitions it started with are still
    there, the check is satisfied rather than silenced, the tests themselves are
    left alone.  Each of those is a property of the tree and of the commit this
    run started on, so each can be settled here for the price of a subprocess
    and no inference at all -- unlike the behaviour the task cares about, which
    can only be reasoned about.

    Doing it at the end is what makes it worth doing.  The loop stops when the
    model says it is finished, which is a judgement about the work rather than
    about the budget, so there is usually a great deal of both left; being sent
    back is therefore paid for out of an allowance that would not have been
    spent.

    Everything here is a *difference* against the state the run was handed
    rather than a judgement about the state it ends in.  A project whose tests
    were already failing, or which already carried suppression comments, is not
    this run's doing and must not become this run's problem; the only thing
    that counts is what this run changed.
    """

    # What it took to get a reading at all, and therefore what every later
    # reading has to ask for too: a difference is only a difference if both
    # sides are the same question.  Set once, when the first attempt comes
    # back with nothing in it.
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 statement: str = "") -> None:
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.declared = declared_file(statement, tree.root)
        # Which runner reads this project, decided once from the project's own
        # manifest.  Once, because a condition that read its baseline with one
        # runner and its re-check with the other would be comparing two
        # questions and calling the difference a regression.
        self.kind = "mix" if (ELIXIR and elixir_project(tree.root)) else "pytest"
        # Where the baseline was read.  A mix project that cannot be built in
        # a separate checkout is read from the live tree instead, and which of
        # the two it was is part of what the reading means.
        self.site = "worktree"
        self.retried_live = False
        self.declared_target = declared_definition(statement)
        self.exclusive_file = bool(EXCLUSIVE_FILE_RE.search(statement or ""))
        # Kept only so the fallback can say why it fell back; never read
        # anywhere the answer depends on.
        self.statement = statement
        self.ledger = Beacon("ledger")
        self.read_back_at: str | None = None
        self.read_backs = 0
        # Distribution records written, kept apart from the module stand-ins
        # because the admission check below counts stand-in MODULES: a record
        # replaces nothing and answers nothing, so a reading recovered by one
        # is a reading of the project as the project wrote it.
        self.records: list = []
        self.beacon = Beacon("warden")
        self.job: Shell | None = None
        self.started = time.time()
        self.before: tuple[set, int] | None = None
        self.refusals = 0
        self.stood_down = False
        self.where: str | None = None
        # Which rung of the ladder is being asked, and therefore what every
        # later reading has to ask for too: a difference is only a difference
        # if both sides are the same question.  Per instance rather than per
        # class -- shared between two wardens, one run's fallback becomes
        # another's starting question and neither says so.
        self.tier = 0
        # Relative to the repository, because the same list is rendered against
        # two roots: the separate checkout the baseline is read from, and the
        # working tree the re-check runs in.
        self.scope: list[str] = []
        self.armed_after: float | None = None
        # Stand-ins for distributions the image does not carry, and where they
        # live.  Written once and kept, so that the baseline and the re-check
        # are read against the same import path.
        self.shims: list = []
        self.shim_dir = ""
        self.stood_in = 0

    # -- the project's own tests -------------------------------------------

    def suite_command(self, root: str | None = None) -> str:
        """Let the test runner find the tests, and take two things away from it.

        The project's own default options go, because a project that turns on
        coverage or a random ordering plugin by default reports failures that
        are about the options rather than about the change.

        A file that will not import stops being fatal, because otherwise it is
        fatal to the whole reading: a project is free to carry a test module
        that needs an optional dependency, and a single one of those anywhere
        under the root ends collection for every other test in the tree.
        Reported as errors they land on both sides of the difference and
        cancel; treated as a reason to stop, they leave the change unchecked.

        The hash seed is pinned, and that one is about the difference rather
        than about either reading.  The two readings are separate processes, so
        anything that varies between processes -- an unordered set's iteration
        order, a dict built from one, a test that happens to depend on either --
        varies between the baseline and the re-check for a reason that has
        nothing to do with the patch.  A test that flips that way is read as a
        test the change broke, and refusing on it is a refusal aimed at a
        correct answer.  Pinning costs nothing and removes the commonest source
        of it.

        Compiled bytecode goes somewhere new every time, and that one is not a
        nicety.  Python decides a cached module is still current by comparing
        the source's modification time *in whole seconds* and its size; an edit
        made within the same second that happens to leave the file the same
        length is invisible to that test, and the run is then handed the
        behaviour of the code as it was before the edit.  The check would pass,
        the tree would be broken, and the answer would go back with a clean
        bill of health.  A directory nothing has written to yet cannot hold a
        stale answer, and one is made per call rather than per run so that two
        readings taken close together cannot end up sharing one.
        """
        root = root or self.tree.root
        if self.kind == "mix":
            return self.mix_command(root)
        # The import path is named rather than left to be guessed, because the
        # reading has to come from the copy this call names and not from
        # wherever a previously installed copy of the same project lives -- a
        # project installed in development mode leaves a pointer to the live
        # tree in the interpreter's own search path, and whichever entry comes
        # first wins.
        #
        # Which directories to name is worked out from the tree rather than
        # from a list of conventional names: a package can sit at the top, or
        # one level down in a directory the project chose the name of, and a
        # layout whose name is not on the list is exactly the case where the
        # pointer to the live tree wins and the reading quietly describes the
        # wrong copy.
        # The stand-ins go last.  Ahead of the tree they would shadow a real
        # package with an empty one; behind it they are reached only for a name
        # nothing else answers, which is the only case they are for.
        path = os.pathsep.join(package_roots(root) + ([self.shim_dir] if self.shim_dir else []))
        # One place renders it, and the three things that make this reading
        # what it is -- the rung, the scope, the root -- are arguments to that
        # one place.  Kept as four call sites each remembering to carry them,
        # the baseline would be read from the separate checkout and the
        # re-check from the working tree with different questions, and the
        # difference between them would be about the questions.
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
        """The project's own tests, asked for the way mix asks for them.

        Three things are taken away from the default and one is pinned, for
        the same reasons the pytest command does it.

        Colour goes, because escape codes around a test's name make the same
        failure read as two different strings to whatever parses it.

        The seed is pinned, and that one is about the difference rather than
        about either reading.  ExUnit shuffles every run by default; the two
        readings are separate processes, so a test that depends on order flips
        between them for a reason that has nothing to do with the patch, and a
        test that flips that way is read as a test the change broke.

        MIX_ENV is named rather than left to the project, because `mix test`
        sets it itself but a project is free to have already exported
        something else into this shell, and a reading taken in the wrong
        environment is a reading of a different application.

        The scope is rendered here, from the same field the baseline and the
        re-check both read, so the two cannot end up asking different
        questions.
        """
        root = root or self.tree.root
        where = " ".join(shlex.quote(rel) for rel in self.scope)
        return (
            "cd %s && MIX_ENV=test mix test --no-color --seed 0%s%s"
            % (shlex.quote(root), MIX_TIERS[self.tier], (" " + where) if where else "")
        )

    def mix_escalate(self) -> bool:
        """The one rung mix has: stop it refusing over a dependency lock.

        A separate checkout given the live tree's own `deps` can carry a lock
        digest that does not match what was fetched into them, and mix answers
        that by refusing to do anything at all -- including run a test that
        would have passed either way.  `--no-deps-check` asks the same
        question without that refusal.

        There is no wider rung, and the pytest ladder's note says why: a wider
        question is not a fallback for a narrow one that came back empty, it
        is a different question with more places to go blind.
        """
        if self.tier >= len(MIX_TIERS) - 1:
            return False
        if self.allowance.clock_left() < self.allowance.rung_min_wall_sec:
            self.beacon.skipped("below what a rung needs; not reading again")
            return False
        self.tier += 1
        self.beacon.fired("reading again at rung %d of %d" % (self.tier + 1, len(MIX_TIERS)))
        try:
            self.job = self.pool.start(self.mix_command(self.where or self.tree.root))
        except Exception as error:  # noqa: BLE001 - an unarmed warden is survivable
            self.beacon.skipped("could not restart the baseline reading: %s" % error)
            return False
        return True

    def mix_retry_live(self, out: str, elapsed: float) -> bool:
        """Read the live tree instead when the separate checkout was never built.

        A mix project that cannot resolve its dependencies exits in under a
        second, with a line about them and not one test in the output.  That
        is a reading of the checkout, not of the project, and recording it
        would arm a comparison against a baseline in which nothing ran: every
        test failing at the start is every test exempt from the difference
        from then on.

        Told apart from a project whose tests genuinely all fail by the two
        things that are true only of the first: nothing ran at all, and it
        took no time.  Either one alone is ambiguous.
        """
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
        except Exception as error:  # noqa: BLE001 - an unarmed warden is survivable
            self.beacon.skipped("could not restart the baseline reading: %s" % error)
        return True

    def pristine(self) -> str | None:
        """A second checkout of the commit this run started on.

        Starting the baseline before the first edit is not the same as reading
        the state before the first edit, and the difference is the whole
        mechanism.  The reading is a subprocess that imports each module as it
        reaches it, and on a project of any size that takes tens of seconds --
        by which time the first edit has usually happened.  What comes back is
        then a mixture: the modules imported early as they were, the ones
        imported late as they have become, and a file caught mid-write as a
        syntax error.  Every one of those makes something look already-broken
        that this run broke, and a difference against an already-broken
        baseline is a difference that finds nothing.

        A separate checkout has no such window.  It is the commit, it cannot be
        edited from here, and it can be read at any pace.  If one cannot be
        made, the caller falls back to reading the live tree and starts early,
        which is weaker in exactly the way described and still better than
        nothing.
        """
        # Inside a directory nobody else has, so that two of these in one run
        # cannot collide on a name the checkout tool refuses to reuse.
        where = os.path.join(tempfile.mkdtemp(prefix="start"), "tree")
        code, out = git(["worktree", "add", "--detach", where, self.tree.base or "HEAD"],
                        self.tree.root, 60)
        if code != 0:
            self.beacon.skipped("no separate checkout to read: %s" % out.strip()[:120])
            return None
        return where

    def arm(self) -> None:
        """Start the baseline reading before anything has been edited.

        In the background, because the run has better things to do than wait
        for it while there is still work to do.  Once there is not -- once the
        answer is ready and this is the only thing missing -- the hand-in is
        held for it instead; see ``settle``.
        """
        if not SUBMISSION_WARDEN:
            self.beacon.skipped("not switched on for this run")
            return
        self.beacon.reached(0, self.allowance.spent, self.allowance.clock_left())
        try:
            self.where = self.pristine()
            if self.kind == "mix":
                # A separate checkout of a mix project has the source and no
                # build.  mix will not run a test until it has its fetched
                # dependencies and somewhere to compile to, and asked to run
                # without them it tries to fetch -- which the fence refuses
                # and the image has no network for.  The baseline would then
                # come back as a project whose every test errored, which reads
                # as a project this run broke before it touched anything.
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
        except Exception as error:  # noqa: BLE001 - an unarmed warden is survivable
            self.beacon.skipped("could not start the baseline reading: %s" % error)

    def escalate(self) -> bool:
        """Ask the same question again, more narrowly, when nothing came back.

        mix has a ladder of its own with one rung on it; the rest of this
        docstring is about pytest's.

        A project is installed here for what it needs to run, not for what it
        needs to test itself, and its fixture module is free to import a
        library that only the test extra would have brought.  One import error
        there is not one test lost: the fixture file is loaded before anything
        under it is collected, so the whole directory goes, and the reading
        comes back with nothing in it at all.  Leaving the fixtures out gets
        the tests that do not need them back.

        And leaving them out is not always enough.  A project whose layout
        cannot be resolved from the import path alone comes back from that with
        every single test module in error at once, in a fraction of a second,
        and identically each time.  Nothing that selective can be at fault; what fails that
        fast and that completely is the import itself.  The project's own pytest options are
        dropped here on purpose, and a project whose layout needs
        `--import-mode=importlib` loses it along with them, which is what the
        last rung was for.  It is off by default now, because the answer it
        buys is worth less than no answer: see the switch.

        Each rung is narrower than the last, never different: whatever it took
        to get an answer is carried into every later reading, because a
        difference between two runs of one command is only a difference if both
        sides asked the same thing.  The scope is part of that question and is
        therefore fixed for the whole run, not relaxed when a rung comes back
        empty.
        """
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
        except Exception as error:  # noqa: BLE001 - an unarmed warden is survivable
            self.beacon.skipped("could not start the second reading: %s" % error)
            return False
        return True

    def stand_in(self, out: str) -> bool:
        """Answer the imports the image never installed, and read again.

        Asked after the ladder, and only once it has no rung left: it is the
        one rung that changes what is installed rather than what pytest is
        told, so ahead of the others it would spend the retry that
        `--noconftest` needed and then hold every later reading to its own
        admission check.
        Nothing is written into the tree: the stand-ins sit in a directory of
        their own at the end of the import path, so a name the project really
        has still comes from the project.
        """
        if self.kind == "mix":
            return False
        if not SUITE_SHIM or self.where is None:
            if not SUITE_SHIM:
                self.beacon.skipped("standing in is not switched on for this run")
            return False
        wanted = [n for n in missing_modules(out) if n not in self.shims]
        # The same rung answers both shapes of absence, because they are the
        # same fault seen at two different moments: something the reading needs
        # is not installed.  One is answered with a module, the other with a
        # distribution record, and a project can meet both at once, so
        # answering only the first can leave the reading exactly as lost as
        # before.
        records = [n for n in missing_dists(out) if n not in self.records]
        # One budget across both shapes and across the whole run, because the
        # reason for a limit is how much of this reading is made of things this
        # run wrote, and that depends on neither which shape each one took nor
        # which attempt it was written in.  Counted against what is already
        # there, so a second attempt cannot start a fresh allowance.
        room_left = max(0, SUITE_SHIM_LIMIT - len(self.shims) - len(self.records))
        if (wanted or records) and not room_left:
            # The budget is what stops the chain, so it is what has to say so.
            # Silence here reads afterwards as an environment that named
            # nothing more, which is the opposite of what happened.
            self.beacon.skipped("%d stand-in(s) over %d attempt(s) and the "
                                "reading still names more"
                                % (len(self.shims + self.records), self.stood_in))
            return False
        # Shared by turns rather than by kind.  Giving one of them the budget
        # first needs an invariant that it always costs more, and there is
        # none: an absent record stops the package's own `__init__`, and an
        # absent module imported by a top-level conftest stops collection of
        # everything under it.  Taking turns leaves neither able to crowd the
        # other out of a reading that named both.
        #
        # Which one takes the first turn is decided by what has already been
        # written rather than fixed, because the turns only run inside one
        # reading: an attempt that starts with the same kind every time hands
        # the last seat of the budget to that kind whatever came before it,
        # and with one seat left the other kind can never be written at all.
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
            # Strictly more than a refusal needs, not merely as much.  This rung
            # is reached last, so the seconds it spends are the last ones there
            # are; started with only a refusal's worth left, a reading that then
            # records nothing still takes the wait with it, and the checks
            # that need no reading at all -- a dropped definition, an added
            # suppression comment -- are released unasked.  A quick reading
            # could still have landed in that band; giving it up is the trade,
            # taken because those checks cost nothing and hold whatever the
            # suite is doing.
            #
            # The floor is the pause before the hand-in plus a window, not a
            # refusal plus a window, because this chain is now as long as the
            # environment is broken: bounded by a refusal's worth it could walk
            # a five-name chain straight through the seconds the pause needed
            # and silence a check that costs nothing and was already there.
            self.beacon.skipped("too little of the run left to read the suite again")
            return False
        if not self.shim_dir:
            try:
                room = tempfile.mkdtemp(prefix="standin")
            except OSError as error:
                self.beacon.skipped("nowhere to write a stand-in: %s" % error)
                self.shim_dir = ""
                return False
            # Where the temporary directory lands is the environment's choice,
            # and one of its answers is the working directory.  Anything
            # written inside the tree is in the diff that gets handed in, and a
            # hand-in carrying a directory the task never asked for fails on
            # its scope before anything else about it is read.  A rung that
            # cannot run somewhere else does not run.
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
        # Back to the project's own pytest options for this reading.  What the
        # ladder narrowed, it narrowed because an import was failing, and the
        # stand-in is the answer to that import -- carrying `--noconftest` into
        # this reading would drop the fixtures the project's tests are written
        # against, and would then read the suite as unable to pass for the
        # very reason the stand-in had just answered.
        #
        # What is installed and what pytest is told are two questions, not two
        # phases of one.  So this puts the second back to the project's own
        # answer and leaves the ladder free to climb again over the top of it:
        # a project missing a distribution AND needing an import mode is a real
        # combination, and treating the two as exclusive loses it.  The climb
        # is bounded as it always was, and so is this rung: by the budget on
        # how much of a reading may be made of things this run wrote.
        self.tier = 0
        try:
            self.job = self.pool.start(self.suite_command(self.where))
        except Exception as error:  # noqa: BLE001 - an unarmed warden is survivable
            self.beacon.skipped("could not start the reading again: %s" % error)
            return False
        # Recorded here and not before the writing, because what the count and
        # the two lists are for is the reading that is now running: incremented
        # up front, an attempt that wrote nothing or could not start anything
        # spends its turn and a share of the budget on a reading that does not
        # exist, and the next attempt -- the one this attempt's answer makes
        # possible -- is refused on the strength of it.
        self.stood_in += 1
        self.shims.extend(made)
        self.records.extend(kept)
        return True

    def settle(self, reserve_sec: float | None = None) -> None:
        """Hold the hand-in for a baseline that has not landed yet.

        Called once, where the answer is ready and the reading is not -- the
        one moment waiting is right.  The run stopped because the model judged
        the work finished rather than because anything ran out, so the wait is
        paid out of an allowance that would go back unused; and the alternative
        is not a later check but no check, since the difference this reading is
        one side of cannot be taken once the answer is gone.

        Bounded twice: by a window, so a suite that was never going to answer
        costs a fixed amount; and by what a refusal needs afterwards, because a
        reading bought with the seconds that were going to act on it has bought
        nothing.

        The loop is over rungs rather than one wait.  A reading that comes back
        empty starts the next rung, and that one exists because the first came
        back empty -- sharing a window gives it all to the attempt that failed.
        """
        # One turn per reading a run can take: a pass of the tiers, and then
        # another pass over the top of each attempt at standing in.  The first turn
        # is spent waiting rather than collecting and the last reading is
        # picked up by the collect below the loop, so the two cancel and this
        # is the count.  Taken from how many attempts there may be rather than
        # written out, because a count sized for one of them and left behind when another
        # second was allowed does not loop for ever -- it stops one pass short,
        # which leaves the answer handed in with the reading still running and
        # nothing to compare it against.  That is the failure the rung exists
        # to prevent, arrived at by widening the rung.
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
        """Pick the baseline up once it is there, without ever waiting on it.

        A project whose tests do not finish inside the window gets the
        condition switched off rather than a longer wait: the job is holding a
        process group that competes with the rest of the run for the machine,
        and nobody is ever going to read its answer.
        """
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
                # How long it was given is a threshold of ours; that it ran
                # out is the reading.
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
        """The test tool's own count, in its own words."""
        if self.kind == "mix":
            lines = [line.strip() for line in (out or "").splitlines()
                     if "failure" in line and MIX_COUNT.search(line)]
            return lines[-1] if lines else "no tally"
        found = SUITE_TALLY.findall(out or "")
        return found[-1].strip() if found else "no tally"

    def reason(self, out: str) -> str:
        """The first thing that actually went wrong.

        One line per error is asked for rather than none, because the names of
        the modules that failed say nothing about whether the failure was this
        run's doing, a missing test dependency, or the project not importing at
        all -- and those want three different answers.

        Which is only true of a line that names the fault.  The frame is not
        one: every import failure is raised from inside the same importer, so a
        record built out of frames says the same thing about all of them and
        distinguishes none.  With one line per failure the frame is printed
        first and the exception after it, so taking the first match takes the
        wrong one.  The distinct faults are counted alongside the first,
        because one missing package behind every module and a different fault
        per module produce the same count and are not the same problem.
        """
        faults = SUITE_FAULT.findall(out or "")
        if faults:
            kinds = len({name for name, _ in faults})
            said = ("%s%s" % faults[0]).strip()[:140]
            return said if kinds == 1 else "%s (+%d other kinds)" % (said, kinds - 1)
        found = SUITE_REASON.findall(out or "")
        return found[0].strip()[:160] if found else "no reason given"

    def read_suite(self, out: str) -> tuple[set, int]:
        """What failed and how much passed, read with the runner that produced it."""
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
        """Ask again about the ones that changed side, and believe the answer.

        A test can go from passing to failing for reasons that have nothing to
        do with the work: an ordering plugin that reseeds itself every run, a
        clock, a port, eight containers competing for one machine.  Sending the
        run back over one of those costs a whole answer, and the price of being
        sure is a second run of a handful of names rather than of everything.
        Anything that will not fail twice is not something to refuse over.

        The names are handed to the same command the reading was taken with,
        and are therefore an addition to its scope rather than a replacement:
        both sides stay one question, at the price of collecting the scope
        again alongside the handful being asked about.
        """
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

    # -- the change itself --------------------------------------------------

    def changed_paths(self) -> list[str]:
        code, out = git(["diff", "--name-only", self.tree.base or "HEAD"],
                        self.tree.root, 30)
        paths = [p for p in out.splitlines() if p.strip()] if code == 0 else []
        return paths + sorted(self.tree._untracked() - self.tree.untracked_at_start)

    def original(self, path: str) -> str | None:
        code, out = git(["show", "%s:%s" % (self.tree.base, path)], self.tree.root, 30)
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
            # No filter on what kind of file this is.  A source it cannot read
            # as a program yields no definitions on either side and so raises
            # nothing, which is the same answer a check on the name would give
            # and does not need a list of which names count.
            faults.extend(self.file_faults(path))
        return faults

    def file_faults(self, path: str) -> list[str]:
        before = self.original(path)
        if before is None:
            return []
        # Two different questions, and running them together got one of them
        # wrong.  Whether this file is one the conditions apply to at all is
        # decided by whether anything can load it: a note or a template that
        # happens to parse is still a note, and a project is free to be asked
        # to drop a stale one.  Whether it owes any *names* is a separate
        # matter, and a file can be under repair while carrying none -- a
        # module of top-level statements owes no interface but may still not be
        # silenced.
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
        # A multiset, not a set.  Two definitions can share a qualified name --
        # the same function defined on either side of a conditional is the
        # common case -- and losing one of the two is still losing one.
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
        """A short stand-in for the state of the change, or None if it could
        not be taken.

        None rather than a hash of nothing.  Asking git what changed can fail
        on its own -- a timeout, a lock held elsewhere -- and that answer folds
        to an empty list, which hashes to a perfectly good value that differs
        from the one before it.  Read as a mark, a probe that recovered between
        two hand-ins says the work moved when nothing moved, and a check that
        only asks once is spent on a message nobody read.
        """
        code, out = git(["diff", "--name-only", self.tree.base or "HEAD"],
                        self.tree.root, 30)
        if code != 0:
            return None
        # Its own probe rather than the tree's, because the tree's folds a
        # failure into "no untracked files" -- and a file that was in the first
        # mark and absent from the second because the probe fell over reads as
        # work that moved, which is the one answer that must not be guessed at
        # here.
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
        """Ask once, before the first hand-in, that the statement be re-read.

        Placed after the other two on purpose: those name something wrong with
        the change, and a run told to go back over the requirements while a
        test it broke is still red would be sent to the wrong place.  This one
        fires only when nothing is wrong, which is the moment this is for: a
        hand-in that no check objects to is the one place where a run that has
        missed something still goes out.
        """
        if not LEDGER_READBACK:
            self.ledger.skipped("not switched on for this run")
            return []
        items = stated_requirements(self.statement)
        if len(items) < LEDGER_MIN:
            self.ledger.skipped("%d item(s), below the floor" % len(items))
            return []
        # Whether it has been asked is decided by whether the work has moved
        # since it was asked, not by a flag set when the refusal was written.
        # One reply can carry two hand-ins; the first would set the flag and
        # the second would sail through, and the refusal would be read by
        # nobody -- the run ends before the message it is part of goes back.
        mark = self.work_mark()
        if mark is None:
            # No reliable answer about whether anything moved. Treating that as
            # movement closes this for the rest of the run; treating it as
            # stillness costs at most one more ask, which its own bound covers.
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
            # Refused, not waved through, so it is not a skip: one reply can
            # carry two hand-ins, and the second arriving with the work exactly
            # as it was means the first refusal has not been read yet.
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

    # -- the decision -------------------------------------------------------

    def verdict(self, reserve_sec: float | None = None) -> list[str]:
        """Reasons not to hand this in yet. Empty means hand it in.

        An empty answer comes in two kinds, and ``stood_down`` tells them
        apart: a hand-in this actually checked, and a hand-in waved through
        because the refusals ran out or the clock did.  A waved-through answer
        must not invite anything that produces further edits -- nothing is
        left that would check them.
        """
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
    """The model called submit."""
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
    "prod.exs",
    "config.exs",
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
    ("Ecto", re.compile(r"(^|/)mix\.exs$|(^|/)lib/.*/repo\.ex$|(^|/)priv/repo/")),
    ("Phoenix", re.compile(r"(^|/)lib/.*_web/|(^|/)lib/.*_web\.ex$")),
    ("SQL files", re.compile(r"\.sql$")),
)
_MIGRATION_PATH = re.compile(
    r"(^|/)migrations?(/|$)|(^|/)alembic(/|$)|(^|/)db/migrate(/|$)|(^|/)priv/repo/migrations(/|$)")

_PY_PG_RUNNER = r"""
import sys
url, query = sys.argv[1], sys.argv[2]
conn = None
try:
    import psycopg
    conn = psycopg.connect(url, connect_timeout=8, autocommit=True)
except ImportError:
    try:
        import psycopg2 as psycopg
        conn = psycopg.connect(url, connect_timeout=8)
        conn.autocommit = True
    except ImportError:
        import asyncio
        import asyncpg

        async def run():
            c = await asyncpg.connect(url, timeout=8)
            try:
                for statement in [s for s in query.split(";") if s.strip()]:
                    rows = await c.fetch(statement)
                    if rows:
                        print(" | ".join(rows[0].keys()))
                    for row in rows:
                        print(" | ".join(str(v) for v in row.values()))
            finally:
                await c.close()
        asyncio.run(run())
        sys.exit(0)
cur = conn.cursor()
cur.execute(query)
try:
    rows = cur.fetchall()
    if cur.description:
        print(" | ".join(d[0] for d in cur.description))
    for row in rows:
        print(" | ".join(str(v) for v in row))
except Exception as error:
    print(cur.statusmessage if hasattr(cur, "statusmessage") else str(error))
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
    """Split a SQL script on semicolons that sit outside quotes and comments."""
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
class Database:
    """One way of reaching a database the repository talks to."""
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

    def run(self, query: str, database: str = "", timeout: float = 60.0, cwd: str = ".") -> tuple[int, str]:
        if self.engine == "postgresql":
            url = self.url
            if database:
                url = re.sub(r"/[^/?]*(\?|$)", "/" + database + r"\1", url, count=1)
            if shutil.which("psql"):
                return run_piped(
                    ["psql", url, "-X", "-v", "ON_ERROR_STOP=1", "-P", "pager=off", "-f", "-"],
                    cwd,
                    timeout,
                    stdin_text=query,
                    extra_env={"PGCONNECT_TIMEOUT": "8"},
                )
            return run_piped([sys.executable, "-c", _PY_PG_RUNNER, url, query], cwd, timeout)
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
    def http(self, query: str, database: str, timeout: float) -> tuple[int, str]:
        port = self.port if self.port and self.port != 9000 else 8123
        params = {"database": database, "default_format": "PrettyCompactMonoBlock"}
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
            try:
                request = urllib.request.Request(url, data=statement.encode("utf-8"), headers=headers)
                with urllib.request.urlopen(request, timeout=left) as response:
                    body = response.read().decode("utf-8", "replace")
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
    """Find how the repository reaches its database(s) and whether they answer."""
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
    # A repo with many copied settings files can yield dozens of lookalikes;
    # verifying more than a handful spends the probe budget on noise.
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
    """Cheap, token-free sketch of which query layer this repository uses."""
    rows: list[str] = []
    for name, pattern in _LAYER_MARKERS:
        hits = [p for p in files if pattern.search(p)]
        if hits:
            rows.append(f"{name} ({hits[0]})")
    migrations = [p for p in files if _MIGRATION_PATH.search(p)]
    if migrations:
        rows.append(f"{len(migrations)} migration files, e.g. {migrations[-1]}")
    return "; ".join(rows[:8])
def pick_database(databases: list[Database], url: str = "", engine: str = "") -> Database | None:
    """The connection a run_sql call means: a given URL, else the best verified candidate."""
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
    """Hard fences the statement states: named method, frozen imports, no loops."""

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
        lines = ["Hard constraints the statement states (enforced at submit):"]
        if self.methods:
            def render(prefix: str, name: str) -> str:
                arity = self.arities.get(name)
                if arity is not None:
                    return "`%s.%s/%s`" % (prefix, name, arity) if prefix else "`%s/%s`" % (name, arity)
                return "`%s.%s()`" % (prefix, name) if prefix else "`%s()`" % name

            names = ", ".join(render(p, n) for p, n in self.methods)
            lines.append("  Named target(s): %s. Change that definition in place." % names)
        flags = []
        if self.constructs_banned:
            flags.append("plain query-layer expressions only (no loops, comprehensions, lambdas, "
                         "try/except, with -- in Elixir: no Enum/Stream, no for, fn, case, cond, with or try)")
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
    """Refuse a change that violates the statement's AST / import / signature fences."""
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
            # Asked of the text rather than of a parse tree, because there is
            # no Elixir parser in this process.  Whether the file still parses
            # is not asked here at all: the edit that wrote it already put that
            # question to Elixir itself, which is a better answer than any
            # shape read off the lines.
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


class Kit:
    """Tool dispatch. A read-only call repeated with identical arguments is
    refused rather than served."""

    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 warden: Warden | None = None, label: str = "",
                 findings: "FindingMap | None" = None,
                 databases: list | None = None,
                 pins: "SpecPins | None" = None) -> None:
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.warden = warden
        self.findings = findings
        self.databases = list(databases or [])
        self.pins = pins
        self.seen: dict[str, int] = {}
        self.edit_all = Beacon("editall")
        self.bg = Beacon("bgshell")
        self.conform = Beacon("conform")
        self.fence = Beacon("fence")
        self.ecto = Beacon("ecto")
        self.ecto_noted: set = set()
        # Which seat is reading.  Two of them share this dispatcher, and a
        # reading with no name on it cannot be told from the other seat's.
        self.label = label
        self.conform_state = "armed" if SUBMIT_CONFORM else "off"
        self.conform_edits = 0
        self.blank_submit_refusals = 0

    def note_findings(self, command: str, out: str) -> None:
        """Hand a check's output to the record, and never let that cost the run.

        It is a record, and a record is worth nothing beside the command the
        model asked for: anything raised here would reach the model as that
        command having failed.
        """
        if self.findings is None:
            return
        try:
            self.findings.observe(command, out)
        except BaseException:  # noqa: BLE001 - a record is never worth the run
            self.findings.beacon.skipped("the output could not be read")

    def note_read(self, what: str) -> None:
        """What a reading asked for and what it cost, one line per call.

        Without it the only record of a seat's reading is the total it spent,
        and a total cannot say whether that went on the file it needed or on
        four it did not -- which is the difference between a seat that reads
        badly and one that is asked to read too much.
        """
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
        # A count of nothing is not a request for nothing.  Asked for zero or
        # fewer, the arithmetic below runs backwards and hands back an empty
        # body under a header that says a range was served, which spends a call
        # and reads like a file with nothing in it.
        wanted = int(count) if count and int(count) > 0 else 0
        asked = min(len(lines), first + wanted - 1) if wanted else len(lines)
        # Whole lines up to the budget, then stop -- not the whole range with
        # its middle removed.  The numbering either side of a hole is still
        # true, so nothing says which side a definition fell on, and a reader
        # that cannot tell carries on as though the gap said what it expected.
        # A shorter run is all true, and the header says where to start again.
        rows, used, last = [], 0, first - 1
        for n in range(first, asked + 1):
            row = "%6d\t%s" % (n, lines[n - 1])
            if rows and used + len(row) + 1 > READ_OUTPUT_CAP:
                break
            # A generated file is one line and can be any size, so the rule
            # above lets the first row in whatever it costs or such a file is
            # unreadable.  Inside one line there are no numbers either side to
            # be believed, so cutting its middle is safe.
            if not rows:
                row = clip(row, READ_OUTPUT_CAP, "line")
            rows.append(row); used += len(row) + 1; last = n
        # The header goes into the conversation too, so it comes out of the
        # same budget: left outside, the answer is longer than the budget says
        # and the caller cuts it again at that size -- the head-and-tail cut
        # this shape exists to avoid, back on the reads that filled it.
        # Nothing to serve is said as nothing rather than as a range that runs
        # backwards.  A header whose end precedes its start is not a span
        # anybody was given, and a caller that reads it as one has been told
        # the file has a hole in it where it has an edge.
        if not rows:
            served = ("%s is empty" % path if not lines
                      else "%s has %d line(s); start=%d is past the end"
                      % (path, len(lines), first))
            self.note_read("read_file %s:%d- of %d -> %dc"
                           % (path, first, len(lines), len(served)))
            return served
        while True:
            head = "%s lines %d-%d of %d" % (path, first, last, len(lines))
            # Only where the budget cut it short of what was asked for.  A
            # caller that named a range and got that range was not cut, and
            # telling it where to read on is then a line of text on every
            # ranged read, carried by every turn after it, saying nothing.
            if last < asked:
                head += " -- pass start=%d to read on" % (last + 1)
            if len(head) + 1 + used <= READ_OUTPUT_CAP:
                break
            if len(rows) > 1:
                used -= len(rows.pop()) + 1
                last -= 1
                continue
            # One line that will not fit beside its own header: cut the line
            # rather than serve nothing, for the same reason as above.
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
        self.allowance.edits += 1
        if before:
            self.edit_all.outcome(before, updated)
        note = self.compile_check(path) + self.ecto_note(path)
        return "edited %s (%d occurrence%s)%s" % (path, hits if every else 1, "" if hits == 1 else "s", note)

    def do_create_file(self, args: dict) -> str:
        path = str(args.get("path") or "")
        self.tree.write(path, str(args.get("content") or ""))
        self.allowance.edits += 1
        return "wrote %s%s%s" % (path, self.compile_check(path), self.ecto_note(path))

    def compile_check(self, path: str) -> str:
        # No parser for this file's language means no check, not a guessed one.
        suffix = os.path.splitext(path)[1].lower()
        if suffix in (".ex", ".exs") and not ELIXIR:
            return ""
        argv = SYNTAX_CHECKS.get(suffix)
        if not argv or not shutil.which(argv[0]):
            return ""
        full = self.tree.absolute(path)
        # Two shapes of check, and the difference matters.  Most of these
        # binaries take the file as their last argument; Elixir takes a
        # program, and the path belongs inside it as a literal.  Rendered with
        # json.dumps because that is the quoting Elixir's own string syntax
        # shares with JSON, so a path with a space or a backslash in it
        # arrives as one string rather than as two arguments.
        if any("{path}" in part for part in argv):
            argv = [part.replace("{path}", json.dumps(full)) for part in argv]
        else:
            argv = argv + [full]
        # Bounded, because a parser that hangs takes the turn with it, and an
        # unbounded wait here is a wait nothing ever collects.
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
            # It exited non-zero for something that is not the file.  Saying
            # "the file no longer parses" about that is a claim this check
            # cannot support.
            return ""
        return "\n\nWARNING: the file no longer parses:\n" + clip(done.stderr or "", 1200, "error")

    def ecto_note(self, path: str) -> str:
        """A fragment the Elixir compiler will reject, named at the edit that wrote it.

        Ecto counts a fragment's ? placeholders against its arguments when the
        module compiles, and refuses the module when they differ.  Without
        this the run learns that at the next compile, which on a project of
        any size is the test command -- minutes later, with the reason buried
        in a compile error about a file the run has since moved on from.
        Reported once per finding, because a note the run has already acted on
        is just something else in the transcript.
        """
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
        except Exception:  # noqa: BLE001 - a note is never worth the edit
            return ""
        if not diff:
            # A file this run created has no diff against the commit; the
            # whole of it is the addition.
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
        except Exception as error:  # noqa: BLE001 - a note is never worth the edit
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
        want_bg = bool(args.get("background")) and ASYNC_SHELL
        asked = float(args.get("timeout") or 120)
        # Two bounds, and both are needed.  The ceiling is a constant so that
        # a long command is not cut short on a slow machine and allowed on a
        # fast one, which would put a different tool result in front of the
        # model on each.  The deadline is still respected on top of that,
        # because a wait that outlives the run takes the diff and the restore
        # with it -- and a run that cannot hand back its work has lost more
        # than a run whose transcript varies.
        room = self.allowance.clock_left() - WALL_RESERVE_SEC
        if room < 5.0:
            # Refusing is the honest answer.  Clamping up to a floor would put
            # the wait back over the deadline that the clamp existed to respect,
            # and a command that returns after the run has had to hand back its
            # work has not helped anybody.
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
            return clip(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)"
        # Still running at the deadline. Killing it throws away whatever work it
        # has already done, so it keeps going and the turn moves on.
        self.bg.fired("kept %s alive past %.0fs: %s" % (job.name, budget, command[:120]))
        return (
            clip(out, SHELL_OUTPUT_CAP, "partial output")
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
        code, out = db.run(query, database=database, timeout=room, cwd=self.tree.root)
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
                code, out = db.run(query, database=database, timeout=room, cwd=self.tree.root)
        say("[SQL] %s via %s rc=%s %dc :: %s"
            % (db.engine, db.label, code, len(out), one_line(query)[:100]))
        head = db.engine + " via " + db.label + ((" database=" + database) if database else "")
        body = clip(out, SQL_OUTPUT_CAP, "rows") if out else "(no output)"
        return head + "\n" + body + (("\n[exit code %s]" % code) if code else "")

    def do_submit(self, args: dict) -> str:
        """Finishing is a request, not a fact.

        Handing in is the only irreversible thing the run does, and it is the
        one step that used to take no account of whether the work was finished
        in the sense the task asked for.  So the conditions the task states are
        settled here, while there is still an allowance to act on them, and a
        failure comes back as a tool result -- the run carries on from where it
        was rather than starting over.  It is bounded on both sides: at most a
        few refusals, and none at all once there is too little of the run left
        to do anything about one.
        """
        # An empty tree needs a production edit, not a baseline wait or
        # an abstract final review. Check it before either can spend the
        # corrective exchange this guard is trying to preserve.
        if self.blank_submit_refusals < 2 and self.allowance.clock_left() >= BLANK_SUBMIT_MIN_WALL_SEC:
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
                    "run a focused check, and call submit again."
                )
        if (self.pins is not None and self.pins.active
                and self.allowance.clock_left() >= BLANK_SUBMIT_MIN_WALL_SEC):
            try:
                shape = audit_shape(self.tree, self.pins)
            except BaseException:  # noqa: BLE001
                shape = []
            if shape:
                return (
                    "Not handed in. The statement's own patch-shape rules are "
                    "not met yet:\n\n"
                    + "\n\n".join(shape[:4])
                    + "\n\nThere is budget left. Fix the shape and call submit again."
                )
        # Before the one-time conformance pause, Warden waits and rechecks
        # against the pause's larger reserve. On the return trip the pause is over,
        # so the same work may use the ordinary refusal reserve to check new edits.
        reserve = (self.allowance.conform_min_wall_sec
                   if (self.conform_state == "armed" and
                       self.allowance.clock_left() >=
                       self.allowance.conform_min_wall_sec) else
                   self.allowance.warden_release_sec)
        faults = self.warden.verdict(reserve) if self.warden else []
        if not faults:
            # Only a hand-in the warden actually checked is worth pausing:
            # this order keeps every non-empty submit checked, so a run that
            # dies after the pause still holds a checked tree.
            if self.warden is None or not self.warden.stood_down:
                note = self.conform_note()
                if note:
                    return note
            raise Finished(str(args.get("summary") or ""))
        return ("Not handed in. The task states conditions this run can "
                "check itself, and they are not met yet:\n\n"
                + "\n\n".join(faults[:3])
                + "\n\nThere is budget left. Fix this and call submit again.")

    def conform_note(self) -> str | None:
        """One pause, once per run, before the first hand-in.

        The statement is the task's own list of requirements, and a detail it
        spells out holds to the letter.  So the first submit comes back with a
        request to read those details off the statement once more -- not a
        judgement, no model is asked anything, and the second submit is never
        paused again.
        """
        if self.conform_state == "asked":
            self.conform_state = "done"
            self.conform.fired("resubmitted after %d further edit(s)"
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
                "call submit again.")


# == Elixir: mix projects, Ecto queries ==

# What decides the runner.  A repository is a mix project when it carries the
# manifest mix itself looks for, and nothing else here guesses at it: a file
# suffix says what a file is, not what the project's own tests are run with.
MIX_MANIFEST = "mix.exs"
# The two rungs this runner has.  The first is the project's own settings; the
# second stops mix refusing to run at all because the dependency lock in a
# separate checkout does not match what was fetched into the tree this run
# started from.  There is no wider rung on purpose -- the pytest ladder's note
# applies here unchanged: a wider question is not a fallback for a narrow one
# that came back empty, it is a different question with more places to go
# blind.
MIX_TIERS = ("", " --no-deps-check")
# A mix project that has to compile before it can test is slower to read than
# an interpreted one, and the compile happens once.  The baseline is given
# room for it; the re-check runs against a tree that is already built.
MIX_BASELINE_SEC = 420.0
MIX_RECHECK_SEC = 300.0
# What a mix project needs beside the source before `mix test` will run at all.
# Linked rather than copied: they are build output, they can be large, and the
# separate checkout is read-only in practice.
MIX_BUILD_DIRS = ("deps", "_build")
# How long a baseline that fails instantly is taken to mean "this checkout
# cannot be built" rather than "the project's tests fail".  A mix project that
# cannot resolve its dependencies exits in under a second with no test in the
# output at all.
MIX_FAST_FAIL_SEC = 30.0
# Lines of context asked for when reading this run's change to one Elixir
# file.  Enough to carry a fragment that was already there and is now given a
# different number of arguments; not so much that an untouched query two
# functions away is read as this run's.
ECTO_DIFF_CONTEXT = 3
# Below this there is no room to act on a note, and a note nothing can be done
# about is just something else in the transcript.
ECTO_NOTE_MIN_SEC = 90.0


def elixir_project(root: str) -> bool:
    """True when the repository is a mix project."""
    try:
        return os.path.isfile(os.path.join(root, MIX_MANIFEST))
    except OSError:
        return False


def mix_ready(where: str, live: str) -> bool:
    """Give a separate checkout the build output mix needs, without copying it.

    A checkout of the commit has the source and nothing else: no fetched
    dependencies and no compiled beams.  `mix test` in it would try to fetch,
    which the fence refuses and the image has no network for anyway, and the
    baseline would come back as a project whose every test errored -- which
    reads as a project this run broke before it touched anything.

    Each directory is linked from the tree the run started in.  A link is not
    a copy: `_build` is written to by whichever reading runs, so the two
    readings share one build, which is exactly what makes the second one fast
    and is safe because they are the same commit's sources until the first
    edit -- and the first edit happens in the live tree, whose own `_build` is
    this same directory, so the re-check rebuilds what changed and the
    baseline has already been taken by then.
    """
    ok = True
    for name in MIX_BUILD_DIRS:
        source = os.path.join(live, name)
        target = os.path.join(where, name)
        if not os.path.isdir(source):
            # Not every project has both, and a project that vendors nothing
            # needs no link.  Missing at the source is not a failure here; it
            # becomes one only if mix then cannot run, which the fast-fail
            # retry below reads and answers by going to the live tree.
            continue
        if os.path.exists(target):
            continue
        try:
            os.symlink(source, target)
        except OSError:
            ok = False
    return ok


def mix_scope(root: str, declared: str | None) -> list[str]:
    """Which of a mix project's tests to read, narrowest first.

    Same contract as ``suite_scope`` and for the same reasons: everything
    returned is relative to the repository, because the list is rendered
    against both the separate checkout and the working tree; and an empty list
    means the whole project, which is the right answer when nothing narrower
    can be named.

    The mapping is the one mix itself documents.  ``lib/my_app/accounts.ex``
    is covered by ``test/my_app/accounts_test.exs``; an umbrella keeps the
    same shape one level down, under ``apps/<app>/``.  A file that is already
    a test file names itself.
    """
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
    # An umbrella application keeps its own test directory.  Reading the
    # umbrella's whole test tree for a change inside one application is the
    # wide question this is here to avoid.
    if len(parts) > 2 and parts[0] == "apps":
        prefix, inner = parts[:2], parts[2:-1]
    # `lib`, `src` and `web` name where the source lives, not what the tests
    # mirror: the test tree starts one level in from them.
    if inner and inner[0] in ("lib", "src", "web"):
        inner = inner[1:]
    tries: list[str] = []

    def under(*bits: str) -> None:
        path = "/".join([b for b in list(prefix) + list(bits) if b])
        if path and path not in tries:
            tries.append(path)

    # The file's own suite, in the directory that mirrors its path, then with
    # outer segments dropped: a project that keeps the whole path and one that
    # keeps only the part that names something are the same walk.
    for cut in range(len(inner) + 1):
        under("test", *inner[cut:], "%s_test.exs" % base)
    # Then the directory that mirrors it, same order.
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


# `mix test` names a failure over two lines: the ordinal and the test's own
# name on the first, the file and line it is written at on the second.  The
# second is what is kept, because it is the identifier `mix test` itself
# accepts back -- which is what the confirming re-run needs.
MIX_FAILURE = re.compile(
    r"^[ \t]*\d+\)[ \t]+(?P<name>.+?)[ \t]*\((?P<mod>[A-Za-z0-9_.]+)\)[ \t]*\r?\n"
    r"[ \t]*(?P<at>[^\s:]+\.exs:\d+)",
    re.M,
)
# The same thing where the location line did not come (a doctest raised from
# inside the module it documents, most often).  Name and module then, which
# cannot be re-run but can still be counted and reported.
MIX_FAILURE_LOOSE = re.compile(
    r"^[ \t]*\d+\)[ \t]+(?P<name>.+?)[ \t]*\((?P<mod>[A-Za-z0-9_.]+)\)[ \t]*$", re.M
)
# What `mix test` will take back as an argument: a test file and the line its
# test is written at.  Anything else read out of a failure report is a name.
MIX_LOCATION = re.compile(r"^[^\s:]+\.exs:\d+$")
MIX_COUNT = re.compile(
    r"(\d+)\s+(doctests?|properties|property|tests?|failures?|excluded|skipped|invalid)"
)
# Why a reading came back with nothing in it.  mix says each of these on its
# own line and then stops, and a condition that records only that it did not
# arm cannot be repaired from its own record.
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
    """(failing test identifiers, passing count) from `mix test` output.

    ExUnit reports how many ran and how many failed; it never reports how many
    passed.  The difference is worked out here, and the same function works
    out both readings -- so whatever this undercounts, it undercounts on both
    sides, and the difference between them still means what it meant.
    """
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
        # An umbrella prints one of these per application, so they add up
        # rather than replace each other.
        ran += counts.get("test", 0) + counts.get("doctest", 0) + counts.get("property", 0)
        failed += counts["failure"]
        away += counts.get("skipped", 0) + counts.get("excluded", 0) + counts.get("invalid", 0)
    return names, max(0, ran - failed - away)


# == Ecto: what the compiler will not accept ==


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
    """(first post-image line, added lines with their offsets, all post-image lines) per hunk."""
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
    """(kind, name, line) for an Ecto fragment whose ? placeholders and arguments differ in number.

    Read off the post-image rather than the added lines alone, and reported
    only when the call overlaps something this run added: a fragment that was
    already wrong is not this run's, and a fragment whose string is untouched
    but whose arguments moved is.
    """
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
                # A fragment whose first argument is not a literal string is
                # checked by the compiler against whatever that expression
                # turns out to be, which is not knowable from here.
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


# == Elixir: the fences the statement states ==

# A definition head.  Every form that opens one is listed, because a fence
# that watches `def` and not `defp` watches the half of a module that is not
# usually where the work is.
ELIXIR_DEF = re.compile(
    r"^(?P<indent>[ \t]*)(?:def|defp|defmacro|defmacrop|defdelegate|defguard|defguardp)"
    r"\s+(?P<name>[a-z_]\w*[!?]?)\b"
)
# What a module pulls in.  The analogue of Python's import block, and compared
# the same way: as a list, in order, so a reordering is a change.
ELIXIR_HEADER = re.compile(r"^[ \t]*(?:alias|import|require|use|@behaviour|@impl)\b.*$", re.M)
# Forms an "Ecto expression only" statement forbids.  Word-bounded and read
# off the body text rather than a parse tree, because there is no Elixir
# parser in this process; what that costs is a fence that can be fooled by the
# same word inside a string, and what it buys is a fence at all.
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
    """The alias/import/require/use lines of a module, in order."""
    return [line.strip() for line in ELIXIR_HEADER.findall(text or "")]


def elixir_def_spans(text: str, name: str) -> tuple | None:
    """(first line, last line) of every clause of one function, 1-based and inclusive.

    Elixir's own formatter puts the closing `end` at the definition's own
    indentation, and a project that runs `mix format` -- which is nearly all
    of them -- therefore makes that a reliable close.  A one-line `do:` clause
    is its own span.  Several clauses of one name are read as one region,
    because a fence that took only the first would call the second one's body
    "outside the function".
    """
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
            # A short clause, possibly continued onto the next lines until the
            # indentation returns to the head's own.
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
    """The statement's fences, applied to one Elixir file.

    The Python side of this reads an AST; there is no Elixir parser in this
    process, so the same questions are asked of the text.  Every answer is
    therefore a shape rather than a parse, and each one is only reported when
    the shape is unambiguous: a named function that can be located in both
    versions, a header block that is a list of lines, a body that either does
    or does not contain a word.  Where the shape cannot be read the fence says
    nothing, because a fence that guesses sends a correct answer back.
    """
    problems: list = []

    def said(name: str) -> str:
        """The function as the statement wrote it: with its arity when one was given."""
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
        # Nothing the statement named is in this file.  That is the ordinary
        # case for every other file in the change, and saying anything about
        # it here would refuse a run for editing a file the statement never
        # mentioned -- which the scope gate, not this, is for.
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


# == Opening frame ==

WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
QUOTED_RE = re.compile(r"[`'\"]([A-Za-z_][A-Za-z0-9_.]{2,})[`'\"]")

COMMON_WORDS = frozenset(
    """the this that with from when what which should would could have been
    test tests file files line lines code error errors return returns value
    values method function class module import python true false none self
    argument arguments result results object objects string strings expected""".split()
)


def candidate_files(tree: Tree, statement: str, beacon: Beacon) -> list[str]:
    """Rank tracked files by the rare identifiers from the problem they carry.
    Costs no inference: each term is weighted by its own scarcity, and a term the
    problem quoted counts for more than one it merely mentioned."""
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
    """A deterministic first look, so the opening turns are not spent on it."""
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
    for marker in ("pyproject.toml", "setup.cfg", "tox.ini", "Makefile",
                   "manage.py", "pytest.ini", "conftest.py"):
        if os.path.isfile(os.path.join(tree.root, marker)):
            parts.append("Present: " + marker)
    if os.path.isfile(os.path.join(tree.root, "manage.py")):
        parts.append(
            "Django app: run Python through this project's interpreter, not "
            "plain `python`. Prefer manage.py shell / test for ORM probes."
        )
    parts.append("This process Python: " + sys.version.split()[0])
    return "\n".join(parts)


BRIEF = """You are implementing a production database-query change in a checked-out repository. You have shell access
and file tools. When you are done, the working tree is the answer: your changes are read
straight off it, so leave the fix in place and call submit.

Work inside the repository as it is. Do not add dependencies and do not rewrite
unrelated code. Implement the stated query semantics at the repository's existing
abstraction level. Do not weaken tests or hard-code examples from the statement.
Prove the fix against the data and the query plan, not only the visible tests.
Never special-case a fixture or memorize an expected value.

CRITICAL - spend turns carefully. Every reply costs one exchange with the model, and
exchanges are the scarcest thing you have. Put every tool call that does not depend on another one into the
SAME reply. Reading four files is four calls in one reply, not four replies. Searching for
three patterns is three calls in one reply. Only wait for a result when the next thing you
do genuinely depends on it.

Do not sit idle while a slow command runs. Start a test suite with background=true, keep
reading code, and collect it with bash_poll when you need the answer.

Use the repository's own runner. A project with a mix.exs is an Elixir project: its tests
are `mix test`, narrowed to a file or to `path/to/file_test.exs:LINE`, with MIX_ENV=test
already set for you by mix. Do not reach for pytest in it, do not run `mix deps.get`
(nothing here can reach the network; whatever the project needs is already fetched), and
do not run `mix format` over files the task did not ask you to touch -- a reformatted file
is a diff outside the scope you were given.

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
   In an Ecto project the query layer is the `from`/`where`/`select` expression and the
   schema module beside it, not Elixir that runs over what a query already returned: a
   change expressed with Enum after a Repo.all has moved the work out of the database,
   which is the opposite of what these tasks ask for.

IMPLEMENT AND VALIDATE

Make the smallest patch that satisfies the complete contract. Inspect its query shape for
accidental row multiplication, eager materialisation, per-row queries, engine-incompatible
constructs, or a migration state mismatch. Reproduce the wrong count, value, or plan
before editing: Django uses str(queryset.query), CaptureQueriesContext /
assertNumQueries, or queryset.explain(analyze=True, buffers=True); a live engine
uses run_sql with EXPLAIN (ANALYZE, BUFFERS). Run a cheap syntax or
query-construction check first, then the narrow repository tests that cover the
changed path. Do not keep polling a hung database command; use its failure mode
to refine the query or choose a cheaper check. For an optimization, re-measure
statement count or buffers and confirm the work dropped.

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

BEFORE YOU SUBMIT

Read the final diff hunk by hunk. Confirm every changed line is inside the allowed scope,
the query preserves required multiplicity and laziness, imports and signatures obey the
statement, and unrelated behavior is untouched. Call submit with a one-line summary."""


def without_sweep(brief: str) -> str:
    """The brief minus the repeated-defect section, for the switched-off arm."""
    start = brief.find("WHEN THE SAME DEFECT")
    end = brief.find("BEFORE YOU SUBMIT")
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
   EXPLAIN (ANALYZE, BUFFERS); on ClickHouse use EXPLAIN indexes=1 and after a
   real run SYSTEM FLUSH LOGS plus system.query_log (read_rows / read_bytes).
   Wrap write experiments in BEGIN; ... ROLLBACK;. If the configured database
   is empty, the project's test database (often kept by --keepdb) is the ready
   schema once a named test has run once. Do not start a second suite against
   the same --keepdb database while one is still running.
8. Ecto, when that is the query layer. Compose on the queryable rather than replacing it:
   `from q in query, where: ...` and the `|>` pipeline keep the result a query, and a
   query stays lazy until a Repo call runs it, which is the laziness contract above in
   Ecto's own terms. Repo.all / Repo.one / Repo.aggregate are where the work happens;
   everything before them is composition and everything after them is Elixir. Bind
   variables with `^` -- an unbound value in a query expression is a compile error, not a
   runtime one. A fragment is checked when the module compiles: its ? placeholders must
   match the arguments after the string exactly, in order. Prefer `select_merge`,
   `subquery/1` and named bindings (`as: :name`, `[{^binding, q}]`) over reshaping the
   result in Elixir. Watch the same shapes as everywhere else in this section: a join
   that multiplies rows unless it is `distinct` or grouped, a preload that turns into
   N+1 when it is done per row instead of in one query, `Repo.aggregate(:count)` over a
   join counting join rows rather than entities, and `limit` applied before an order that
   was going to decide which rows those are. Migrations live under priv/repo/migrations
   and are not the place to fix a query.
9. If the file already uses RawSQL / text() / a SQL string, write one
   correlated raw subquery per annotation rather than a tower of
   OuterRef/Subquery/Exists that needs new imports. Watch integer vs numeric
   division (100 -> 100.0 rather than importing Cast), DISTINCT double-counting
   across joins, NULL-safe equality, and N+1. On ClickHouse filter on the
   ORDER BY / partition key so PREWHERE and pruning work; avoid SELECT * and
   FINAL unless required. Helpers and new import lines are not free when the
   statement freezes the rest of the file: stay inside the named method."""


def compose_brief() -> str:
    """The database system prompt, assembled from DB-compatible sections only."""
    text = BRIEF
    if MOVE_VERBATIM:
        marker = "BEFORE YOU SUBMIT"
        text = (text.replace(marker, RESTRUCTURE + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + RESTRUCTURE)
    if INVARIANT_BRIEF:
        marker = "BEFORE YOU SUBMIT"
        text = (text.replace(marker, INVARIANTS + "\n\n" + marker, 1)
                if marker in text else text + "\n\n" + INVARIANTS)
    marker = "BEFORE YOU SUBMIT"
    text = (text.replace(marker, DATABASE_QUERY_ENGINEERING + "\n\n" + marker, 1)
            if marker in text else text + "\n\n" + DATABASE_QUERY_ENGINEERING)
    return text


def declared_scope_excerpt(statement: str, tree: Tree) -> str:
    """Imports and exact definition named by the task, without inference."""
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
    if ELIXIR and elixir_project(tree.root):
        blocks.append(
            "\nThis is a mix project. Its tests are `mix test` (add a path, or "
            "`path/to/file_test.exs:LINE`, to narrow it); `mix compile` is the cheap "
            "check that the module still builds, and an edit to a .ex or .exs file is "
            "parsed back for you as soon as you write it."
        )
    if db_report.strip():
        blocks.append(
            "\nLive database, probed before the first turn (no tokens). "
            "Use run_sql against a reachable engine; wrap writes in "
            "BEGIN; ... ROLLBACK; on PostgreSQL:\n" + db_report
        )
    return "\n".join(blocks)


# == The loop ==


def shrink_transcript(messages: list[dict], cap: int, beacon: Beacon) -> bool:
    """Bring the transcript under ``cap`` by blanking the oldest bulky results.
    Content is replaced in place rather than removed, which leaves the provider's
    prefix cache intact."""
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
                           "is good enough; there is no reward for spending the whole budget.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

def plan_tools() -> list[dict]:
    """The read-only subset, plus the note and the exit.

    Built here rather than filtered into the module-level list, so that the two
    tools that only make sense to this seat cannot reach the driver's.
    """
    return [s for s in TOOL_SCHEMAS
            if s["function"]["name"] in PLAN_TOOL_NAMES] + PLAN_EXTRA_TOOLS

def run_plan(statement: str, tree: Tree, pool: ShellPool, allowance: Allowance,
             beacon: Beacon, turn: int, databases: list | None = None) -> str:
    """One rescue: a second seat reads, writes a note, and hands it back.

    Everything that ends it is a property of the trajectory or of the money --
    never of the clock.  Machines differ in speed, so a branch taken on elapsed
    time is taken at a different point in the conversation on each of them,
    and the same task then follows a different path depending on where it ran.

    Returns the note, or "" -- and "" is a full answer.  A rescue that fails is
    a rescue that did not happen; the caller carries on as it would have.
    """
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
                except Exception as error:  # noqa: BLE001
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
                        except Exception as error:  # noqa: BLE001
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
    except Exception as error:  # noqa: BLE001
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
    except Exception as error:  # noqa: BLE001 - a probe must never end the run
        say("[DB] probe failed: %s: %s" % (type(error).__name__, error))
    kit = Kit(tree, pool, allowance, warden, findings=findings,
              databases=databases, pins=pins)
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
    if not SUBMIT_CONFORM:
        kit.conform.skipped("not switched on for this run")
    if findings is not None:
        findings.beacon.reached(0, allowance.spent, allowance.clock_left())
    else:
        Beacon("findings").skipped("not switched on for this run")
    messages: list[dict] = [
        {"role": "system", "content": compose_brief()},
        {"role": "user", "content": opening_message(statement, tree, hints, db_report, pins)},
    ]
    cap = transcript_cap_chars(seat.current(), allowance.ceiling_usd)
    say("[LOOP] transcript cap set for %s" % seat.current())
    blanks = 0
    pressed = 0
    wrapped_up = False
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
        if (allowance.edits == 0
                and (turn > FIRST_EDIT_DEADLINE_TURN or edit_due_by_time)
                and pressed < EDIT_PRESSES_MAX):
            pressed += 1
            say("[LOOP] %d turns without an edit; pressing for one (#%d)"
                % (turn - 1, pressed))
            press = (
                "No edit yet. Narrow the database contract to the exact production "
                "definition and take the next evidence-backed step. Before editing, "
                "identify the result grain, query-layer primitive, and repository "
                "example that supports the intended shape. Do not guess merely to "
                "create a diff, and do not submit while the tree is unchanged."
            )
            if pressed == 1 and not edit_due_by_time:
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
        answering = seat.current()
        reply = seat.ask(messages, TOOL_SCHEMAS)
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
                    "or call submit if the change is complete.",
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
            except Exception as error:  # noqa: BLE001
                result = "could not read the arguments: %s" % error
            else:
                try:
                    result = kit.run(name, args)
                except Finished as done:
                    say("[LOOP] submit at turn %d: %s" % (turn, str(done)[:200]))
                    return
                except ToolFault as fault:
                    result = "error: %s" % fault
                except Exception as error:  # noqa: BLE001
                    result = "error: %s: %s" % (type(error).__name__, error)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id"), "content": clip(str(result), READ_OUTPUT_CAP)}
            )

        if (not wrapped_up
                and (turn >= WRAPUP_TURN
                     or allowance.money_left() < allowance.soft_usd * 0.15)):
            wrapped_up = True
            messages.append(
                {
                    "role": "user",
                    "content": "You are near the end of the run. Finish the change you are on, "
                    "inspect the completed query or migration shape, run the narrowest "
                    "relevant check, review the final diff against the stated scope, and "
                    "call submit.",
                }
            )
    say("[LOOP] hit the turn ceiling")

def agent_main(input: dict) -> str:
    """Every path out of this function returns whatever the tree holds."""
    allowance = Allowance()
    root = os.getcwd()
    tree = Tree(root)
    pool = ShellPool(root)
    statement = str((input or {}).get("problem_statement") or "").strip()
    say("[RUN] budget=$%.3f clock=%.0fs build=24-elixir90800hj8asd"
        % (allowance.ceiling_usd, allowance.clock_left()))
    findings = FindingMap(root) if FINDING_MAP else None
    if ELIXIR and elixir_project(root):
        say("[RUN] mix project: the project's own tests are read with `mix test`")
    try:
        drive(statement, tree, pool, allowance, findings)
    except Spent as stop:
        say("[RUN] out of allowance: %s" % stop)
    except BaseException as error:  # noqa: BLE001 - a crash must still hand back the tree
        import traceback

        traceback.print_exc()
        say("[RUN] crashed: %s: %s" % (type(error).__name__, error))
    pool.close()
    patch = ""
    try:
        patch = tree.diff(max(5.0, min(60.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:  # noqa: BLE001
        import traceback
        traceback.print_exc()
    try:
        tree.restore(max(5.0, min(60.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:  # noqa: BLE001
        pass
    usable = None
    try:
        usable = tree.applies(patch, max(5.0, min(30.0, allowance.clock_left() + WALL_RESERVE_SEC - 5)))
    except BaseException:  # noqa: BLE001
        pass
    if usable is False and patch.strip():
        try:
            rescued = tree.salvage(patch, max(5.0, min(45.0, allowance.clock_left()
                                                      + WALL_RESERVE_SEC - 5)))
        except BaseException as error:  # noqa: BLE001 - never worth the run
            say("[PATCH] salvage failed: %s" % type(error).__name__)
            rescued = ""
        if rescued:
            patch, usable = rescued, True
    if findings is not None:
        try:
            findings.report(patch)
        except BaseException:  # noqa: BLE001 - a record is never worth the patch
            findings.beacon.skipped("the record could not be worked out")
    try:
        say("[SHAPE] " + patch_shape(patch))
    except BaseException:  # noqa: BLE001 - a record is never worth the patch
        pass
    say(
        "[RUN] done in %.0fs, $%.4f over %d calls, %d edits, patch %dB, usable=%s"
        % (allowance.elapsed(), allowance.spent, allowance.calls, allowance.edits,
           len(patch), {True: "yes", False: "no"}.get(usable, "unknown"))
    )
    return patch