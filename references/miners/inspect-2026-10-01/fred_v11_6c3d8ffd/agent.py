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
}
DRIVER_MODEL = os.getenv("RIDGES_AGENT_MODEL", "~openai/gpt-luna-latest")
RELIEF_MODEL = os.getenv(
    "RIDGES_RELIEF_MODEL", "deepseek/deepseek-v4-pro-0813"
)
PLAN_MODEL = os.getenv("RIDGES_PLAN_MODEL", "~openai/gpt-luna-latest")
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
UNKNOWN_CACHE_TERMS = (0.1000e-6, 131_072)
MODEL_PRICING = {
    "qwen/qwen3.8-2.4t-a95b": (2.000e-6, 6.000e-6),
    "@preset/qwen38-24t-lowthink": (2.000e-6, 6.000e-6),
    "xiaomi/mimo-v2.5-pro": (0.600e-6, 1.201e-6),
    "xiaomi/mimo-v2.5": (0.140e-6, 0.280e-6),
    "minimax/minimax-m2.5": (0.150e-6, 0.900e-6),
    "minimax/minimax-m3": (0.375e-6, 1.500e-6),
    "deepseek/deepseek-v4-pro-0813": (0.660e-6, 1.980e-6),
    "openai/gpt-5.6-luna": (0.200e-6, 1.200e-6),
    "~openai/gpt-luna-latest": (0.200e-6, 1.200e-6),
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
TURN_CEILING = 150
FIRST_EDIT_DEADLINE_TURN = 5
FIRST_EDIT_TIME_REMAINING_SHARE = 0.80
BLANK_SUBMIT_MIN_WALL_SEC = 90.0
PLAN_READ_BUDGET = 150_000
PLAN_TURN_CAP = 40





PLAN_SPEND_SHARE = 0.75
PLAN_NOTE_CHARS = 4_000
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
EMPTY_TIMEOUT_ROSTER_RESETS = 1
EMPTY_TIMEOUT_RESET_MIN_WALL_SEC = 180.0
CALL_CLOCK_SHARE = 0.34
SEAT_RETRY_DECAY = 0.5
SEAT_RETRY_FLOOR_SEC = 20.0
SHELL_BUDGET_CEILING_SEC = 180.0
BACKGROUND_POLL_WAIT_SEC = 20.0
SQL_OUTPUT_CAP = 10_000
PROBE_BUDGET_SEC = 25.0
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
REASONING_CONFIG = {"effort": "xhigh", "exclude": True}

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
LEDGER_READBACK = flag("RIDGES_LEDGER_READBACK")
MOVE_VERBATIM = flag("RIDGES_MOVE_VERBATIM")
SUBMIT_CONFORM = flag("RIDGES_SUBMIT_CONFORM", "1")
PLAN_SEAT = flag("RIDGES_PLAN_SEAT", "0")
SUITE_SCOPE = flag("RIDGES_SUITE_SCOPE")
SUITE_IMPORTLIB = flag("RIDGES_SUITE_IMPORTLIB", "0")
SUITE_SHIM = flag("RIDGES_SUITE_SHIM")
NETWORK_FENCE = flag("RIDGES_NETWORK_FENCE")
SEARCH_LIMIT = flag("RIDGES_SEARCH_LIMIT", "0")
OUTLINE = flag("RIDGES_OUTLINE", "0")
FINDING_MAP = flag("RIDGES_FINDING_MAP", "0")

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

    def ask(self, messages: list[dict], tools: list[dict] | None) -> dict:
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
        attempts = REQUEST_ATTEMPTS if self.patient else 1
        ceiling = SEAT_CALL_TIMEOUT_SEC if self.patient else 60.0
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
            backoff *= 2
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
            handle, path = tempfile.mkstemp(prefix="ridges-patch-", suffix=".diff")
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
            handle, path = tempfile.mkstemp(prefix="ridges-part-", suffix=".diff")
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
        )

    def _text(self) -> str:
        try:
            self.sink.flush()
            return bounded_output_file(self.sink.name, TOOL_OUTPUT_READ_CAP, "tool output")
        except OSError:
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

def declared_file(statement: str, root: str) -> str | None:
    explicit = DECLARED_FILE_SCOPE_RE.search(statement or "")
    if explicit:
        candidate = explicit.group("path")
        if (not TEST_PATH.search(candidate)
                and os.path.isfile(os.path.join(root, candidate))):
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
EXCLUSIVE_FILE_RE = re.compile(
    r"\b(?:edit only|may edit only|only edit|limit (?:production )?changes to|"
    r"production changes (?:are )?limited to|change only|touch only|modify only|"
    r"changes? (?:must be |are )?(?:limited|confined|restricted) to)\b",
    re.I,
)
METHOD_TICK_RE = re.compile(r"`((?:[A-Za-z_][\w]*\.)*)([A-Za-z_]\w*)\(\)`")
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

class Warden:
    def __init__(self, tree: Tree, pool: ShellPool, allowance: Allowance,
                 statement: str = "") -> None:
        self.tree = tree
        self.pool = pool
        self.allowance = allowance
        self.declared = declared_file(statement, tree.root)
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
            self.scope = suite_scope(self.tree.root, self.declared) if SUITE_SCOPE else []
            say("[WARDEN] baseline scope: %s"
                % (", ".join(self.scope) if self.scope else "the whole repository"))
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
            if time.time() - self.job.started > self.allowance.suite_baseline_sec:
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
        done, out = job.wait(min(SUITE_RECHECK_SEC, room))
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
        job = self.pool.start("%s %s" % (self.suite_command(),
                                         " ".join(shlex.quote(n) for n in asked)))
        done, out = job.wait(min(SUITE_RECHECK_SEC, room))
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
            names = ", ".join(
                ("`%s.%s()`" % (p, n) if p else "`%s()`" % n) for p, n in self.methods
            )
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
    paths = [p for p in out.splitlines() if p.endswith(".py")] if code == 0 else []
    for path in sorted(tree._untracked() - tree.untracked_at_start):
        if path.endswith(".py") and path not in paths:
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
        self.label = label
        self.conform_state = "armed" if SUBMIT_CONFORM else "off"
        self.conform_edits = 0
        self.blank_submit_refusals = 0

    def note_findings(self, command: str, out: str) -> None:
        if self.findings is None:
            return
        try:
            self.findings.observe(command, out)
        except BaseException:
            self.findings.beacon.skipped("the output could not be read")

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
        note = self.compile_check(path)
        return "edited %s (%d occurrence%s)%s" % (path, hits if every else 1, "" if hits == 1 else "s", note)

    def do_create_file(self, args: dict) -> str:
        path = str(args.get("path") or "")
        self.tree.write(path, str(args.get("content") or ""))
        self.allowance.edits += 1
        return "wrote %s%s" % (path, self.compile_check(path))

    def compile_check(self, path: str) -> str:
        argv = SYNTAX_CHECKS.get(os.path.splitext(path)[1].lower())
        if not argv or not shutil.which(argv[0]):
            return ""
        done = subprocess.run(
            argv + [self.tree.absolute(path)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if done.returncode == 0:
            return ""
        return "\n\nWARNING: the file no longer parses:\n" + clip(done.stderr or "", 1200, "error")

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
            return clip(out, SHELL_OUTPUT_CAP, "shell output") or "(no output)"
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
            except BaseException:
                shape = []
            if shape:
                return (
                    "Not handed in. The statement's own patch-shape rules are "
                    "not met yet:\n\n"
                    + "\n\n".join(shape[:4])
                    + "\n\nThere is budget left. Fix the shape and call submit again."
                )
        reserve = (self.allowance.conform_min_wall_sec
                   if (self.conform_state == "armed" and
                       self.allowance.clock_left() >=
                       self.allowance.conform_min_wall_sec) else
                   self.allowance.warden_release_sec)
        faults = self.warden.verdict(reserve) if self.warden else []
        if not faults:
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
straight off it, so leave the fix in place and call submit.

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

Make the smallest patch that satisfies the complete contract. Inspect its query shape for
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

BEFORE YOU SUBMIT

Read the final diff hunk by hunk. Confirm every changed line is inside the allowed scope,
the query preserves required multiplicity and laziness, imports and signatures obey the
statement, and unrelated behavior is untouched. Call submit with a one-line summary."""

def without_sweep(brief: str) -> str:
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
8. If the file already uses RawSQL / text() / a SQL string, write one
   correlated raw subquery per annotation rather than a tower of
   OuterRef/Subquery/Exists that needs new imports. Watch integer vs numeric
   division (100 -> 100.0 rather than importing Cast), DISTINCT double-counting
   across joins, NULL-safe equality, and N+1. On ClickHouse filter on the
   ORDER BY / partition key so PREWHERE and pruning work; avoid SELECT * and
   FINAL unless required. Helpers and new import lines are not free when the
   statement freezes the rest of the file: stay inside the named method."""

def compose_brief() -> str:
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
            "Use run_sql against a reachable engine; wrap writes in "
            "BEGIN; ... ROLLBACK; on PostgreSQL:\n" + db_report
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
                           "is good enough; there is no reward for spending the whole budget.",
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
            except Exception as error:
                result = "could not read the arguments: %s" % error
            else:
                try:
                    result = kit.run(name, args)
                except Finished as done:
                    say("[LOOP] submit at turn %d: %s" % (turn, str(done)[:200]))
                    return
                except ToolFault as fault:
                    result = "error: %s" % fault
                except Exception as error:
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
    allowance = Allowance()
    root = os.getcwd()
    tree = Tree(root)
    pool = ShellPool(root)
    statement = str((input or {}).get("problem_statement") or "").strip()
    say("[RUN] budget=$%.3f clock=%.0fs"
        % (allowance.ceiling_usd, allowance.clock_left()))
    findings = FindingMap(root) if FINDING_MAP else None
    try:
        drive(statement, tree, pool, allowance, findings)
    except Spent as stop:
        say("[RUN] out of allowance: %s" % stop)
    except BaseException as error:
        import traceback
        traceback.print_exc()
        say("[RUN] crashed: %s: %s" % (type(error).__name__, error))
    pool.close()
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

_REPLICA_BUILD_STAMP = "c87e01"
