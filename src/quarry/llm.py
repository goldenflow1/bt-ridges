"""Chat-completions client for the inference proxy: retries, model fallback, budget checks, telemetry."""

from __future__ import annotations

import json
import os
import random
import socket
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from quarry.wallet import BudgetExhausted, Wallet, is_budget_refusal

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}
MAX_ATTEMPTS = 4
MIN_ATTEMPT_SEC = 5.0  # an attempt with less time than this is not worth starting
DEFAULT_PROXY = "http://sandbox-proxy:80"  # documented default of SANDBOX_PROXY_URL


class LLMError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict
    error: str = ""  # set when the arguments were not valid JSON


@dataclass
class ChatResult:
    content: str
    tool_calls: List[ToolCall]
    usage: Dict
    model: str
    message: Dict  # assistant message to append to the transcript


@dataclass
class CallRecord:
    """One attempt. Token and cost fields are None when the response did not report them (never coerced to 0)."""

    role: str
    model: str
    status: int
    latency: float
    cost: Optional[float]
    cost_source: str  # provider | estimate | unknown | none (see wallet.py)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    cache_discount: Optional[float] = None
    ok: bool = True
    note: str = ""


def _opt_int(value) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def usage_fields(usage) -> Dict:
    """Token and cache fields exactly as reported; missing stays None."""
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    discount = usage.get("cache_discount")
    return {
        "prompt_tokens": _opt_int(usage.get("prompt_tokens")),
        "completion_tokens": _opt_int(usage.get("completion_tokens")),
        "cached_tokens": _opt_int(details.get("cached_tokens")),
        "cache_write_tokens": _opt_int(details.get("cache_write_tokens")),
        "cache_discount": float(discount) if isinstance(discount, (int, float)) and not isinstance(discount, bool) else None,
    }


def _never_sent(exc: BaseException) -> bool:
    """True when the request certainly never reached the provider (so it cannot have been charged)."""
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (ConnectionRefusedError, socket.gaierror))


def resolve_endpoint(environ: Optional[dict] = None) -> Tuple[str, str]:
    """(chat completions URL, bearer key). Production proxy first, then the local-run helper."""
    env = os.environ if environ is None else environ
    base = (env.get("RIDGES_INFERENCE_BASE_URL") or "").rstrip("/")
    if base and not env.get("SANDBOX_PROXY_URL"):
        return base + "/chat/completions", env.get("RIDGES_INFERENCE_API_KEY", "") or env.get("OPENROUTER_API_KEY", "")
    proxy = (env.get("SANDBOX_PROXY_URL") or DEFAULT_PROXY).rstrip("/")
    return proxy + "/api/v1/chat/completions", env.get("OPENROUTER_API_KEY", "")


def estimate_tokens(messages: List[Dict], tools: Optional[List[Dict]] = None) -> int:
    size = len(json.dumps(messages, ensure_ascii=False))
    if tools:
        size += len(json.dumps(tools))
    return int(size / 3.2) + 50


Transport = Callable[[str, bytes, Dict[str, str], float], Tuple[int, str]]


def urllib_transport(url: str, body: bytes, headers: Dict[str, str], timeout: float) -> Tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def parse_tool_calls(message: Dict) -> List[ToolCall]:
    calls: List[ToolCall] = []
    for raw in message.get("tool_calls") or []:
        fn = raw.get("function") or {}
        name = str(fn.get("name") or "").strip()
        call_id = str(raw.get("id") or "") or "call_" + uuid.uuid4().hex[:12]
        raw["id"] = call_id
        args_text = fn.get("arguments")
        if isinstance(args_text, dict):
            calls.append(ToolCall(call_id, name, args_text))
            continue
        try:
            args = json.loads(args_text or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
            calls.append(ToolCall(call_id, name, args))
        except (ValueError, TypeError) as exc:
            calls.append(ToolCall(call_id, name, {}, error=f"invalid JSON arguments: {exc}"))
    return calls


@dataclass
class ModelRoute:
    model: str
    fallback: Optional[str] = None
    max_tokens: int = 4096
    reasoning: Optional[Dict] = None


class ProxyClient:
    def __init__(
        self,
        wallet: Wallet,
        environ: Optional[dict] = None,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.url, self.key = resolve_endpoint(environ)
        self.wallet = wallet
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.telemetry: List[CallRecord] = []
        self._failures: Dict[str, int] = {}

    def complete(
        self,
        messages: List[Dict],
        route: ModelRoute,
        tools: Optional[List[Dict]] = None,
        role: str = "driver",
        timeout: float = 180.0,
        max_tokens: Optional[int] = None,
        deadline: Optional[float] = None,
    ) -> ChatResult:
        """One completion. `deadline` is an absolute time on `self.clock`; no attempt, wait or backoff passes it."""
        max_out = max_tokens or route.max_tokens
        model = route.model
        if route.fallback and self._failures.get(model, 0) >= 2:
            model = route.fallback
        prompt_est = estimate_tokens(messages, tools)
        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            attempt_timeout = timeout
            if deadline is not None:
                left = deadline - self.clock()
                if left < MIN_ATTEMPT_SEC:
                    raise LLMError(f"no time left for a model call ({left:.1f}s); last error: {last_error or 'none'}")
                attempt_timeout = min(timeout, left)
            reservation = self.wallet.reserve(self.wallet.estimate(model, prompt_est, max_out))
            body: Dict = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_out, "usage": {"include": True}}
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            if route.reasoning:
                body["reasoning"] = route.reasoning
            headers = {"Content-Type": "application/json"}
            if self.key:
                headers["Authorization"] = "Bearer " + self.key
            started = self.clock()
            never_sent = False
            try:
                status, text = self.transport(self.url, json.dumps(body).encode(), headers, attempt_timeout)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
                status, text = 0, f"transport error: {exc}"
                never_sent = _never_sent(exc)
            latency = self.clock() - started
            usage: Dict = {}
            if status == 200:
                try:
                    data = json.loads(text)
                    choice = (data.get("choices") or [{}])[0]
                    message = choice.get("message") or {}
                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                except (ValueError, AttributeError, IndexError) as exc:
                    status, text = 502, f"unparseable response: {exc}"
                else:
                    if data.get("error"):
                        status, text = int((data["error"] or {}).get("code") or 502), json.dumps(data["error"])
                    else:
                        return self._success(data, message, model, role, latency, reservation)
            # Failed attempt. An HTTP error response means the request was rejected (no charge); a sent request
            # with no usable answer (timeout, reset, broken body) may have been charged: keep its reservation.
            if never_sent or status >= 400:
                cost, source = self.wallet.release(reservation)
            elif usage:
                cost, source = self.wallet.settle(reservation, model, usage)
            else:
                cost, source = self.wallet.keep_unknown(reservation)
            record = CallRecord(role, model, status, latency, cost, source, ok=False, **usage_fields(usage))
            if is_budget_refusal(status, text):
                self.wallet.mark_spent()
                record.note = f"budget refusal {status}"
                self.telemetry.append(record)
                raise BudgetExhausted(f"provider refused on budget grounds ({status})")
            last_error = f"{status}: {text[:300]}"
            record.note = last_error[:120]
            self.telemetry.append(record)
            self._failures[model] = self._failures.get(model, 0) + 1
            retryable = status == 0 or status in RETRY_STATUS
            if not retryable:
                break
            if route.fallback and model != route.fallback and self._failures[model] >= 2:
                model = route.fallback
            pause = min(20.0, (2 ** attempt) + random.random())
            if deadline is not None:
                pause = min(pause, deadline - self.clock() - MIN_ATTEMPT_SEC)
                if pause < 0:
                    break
            self.sleep(pause)
        raise LLMError(f"model call failed after retries: {last_error}")

    def _success(self, data: Dict, message: Dict, model: str, role: str, latency: float, reservation) -> ChatResult:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        cost, source = self.wallet.settle(reservation, model, usage)
        self.telemetry.append(CallRecord(role, model, 200, latency, cost, source, **usage_fields(usage)))
        self._failures[model] = 0
        calls = parse_tool_calls(message)
        assistant = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("tool_calls"):
            assistant["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in calls
            ]
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return ChatResult(content, calls, usage, str(data.get("model") or model), assistant)

