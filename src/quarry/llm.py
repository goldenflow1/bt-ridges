"""Chat-completions client for the inference proxy: retries, model fallback, budget checks, telemetry."""

from __future__ import annotations

import http.client
import json
import os
import random
import socket
import threading
import time
import urllib.error
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from quarry.wallet import BudgetExhausted, Wallet, is_budget_refusal, is_temporary_budget_refusal

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}
MAX_ATTEMPTS = 4
MIN_ATTEMPT_SEC = 5.0  # an attempt with less time than this is not worth starting
SWITCH_AFTER = 2  # consecutive retryable primary failures within one call before its fallback is used (H-LLM-02)
PRIMARY_COOLDOWN_SEC = 60.0  # after a fallback switch, calls start on the fallback for this long (H-LLM-02)
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


# A transport returns (status, body) or (status, body, lower-case headers).
Transport = Callable[[str, bytes, Dict[str, str], float], tuple]
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def http_transport(url: str, body: bytes, headers: Dict[str, str], timeout: float,
                   max_bytes: int = MAX_RESPONSE_BYTES) -> Tuple[int, str, Dict[str, str]]:
    """POST and read the whole response within `timeout` seconds in total (H-LLM-07). A socket timeout alone only
    bounds each read, so a body sent in small pieces could outlive it; a watchdog closes the socket at the deadline."""
    deadline = time.monotonic() + timeout
    parts = urllib.parse.urlsplit(url)
    connection_class = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parts.hostname, parts.port, timeout=max(0.01, timeout))
    expired = threading.Event()

    def cut_off() -> None:
        expired.set()
        sock = connection.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    watchdog = threading.Timer(max(0.0, timeout), cut_off)
    watchdog.daemon = True
    watchdog.start()
    try:
        path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        chunks: List[bytes] = []
        total = 0
        while True:
            left = deadline - time.monotonic()
            if left <= 0 or expired.is_set():
                raise TimeoutError("response exceeded the attempt deadline")
            if connection.sock is not None:
                connection.sock.settimeout(left)
            chunk = response.read1(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"response larger than {max_bytes} bytes")
            chunks.append(chunk)
        if expired.is_set():
            raise TimeoutError("response exceeded the attempt deadline")
        reply_headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, b"".join(chunks).decode("utf-8", "replace"), reply_headers
    except (OSError, http.client.HTTPException) as exc:
        if expired.is_set():
            raise TimeoutError("response exceeded the attempt deadline") from exc
        raise
    finally:
        watchdog.cancel()
        connection.close()


urllib_transport = http_transport  # earlier name, kept for callers outside the package


def retry_after_seconds(headers: Dict[str, str]) -> Optional[float]:
    """Seconds from a `Retry-After` header; None when absent, malformed or negative (H-LLM-09)."""
    value = (headers or {}).get("retry-after")
    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


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
        self.cooldown_until: Dict[str, float] = {}  # primary model -> clock time before which calls start on its fallback

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
        if route.fallback and self.cooldown_until.get(route.model, float("-inf")) > self.clock():
            model = route.fallback  # the primary failed recently: let it recover (H-LLM-02)
        streak = 0  # consecutive retryable failures of the current model within this call
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
            reply_headers: Dict[str, str] = {}
            try:
                reply = self.transport(self.url, json.dumps(body).encode(), headers, attempt_timeout)
                status, text = reply[0], reply[1]
                if len(reply) > 2 and isinstance(reply[2], dict):
                    reply_headers = reply[2]
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError,
                    http.client.HTTPException, ValueError) as exc:
                status, text = 0, f"transport error: {exc}"
                never_sent = _never_sent(exc)
            latency = self.clock() - started
            rejected = status >= 400
            usage: Dict = {}
            if status == 200:
                try:
                    data = json.loads(text)
                    if not isinstance(data, dict):
                        raise ValueError("response is not an object")
                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                    if data.get("error"):
                        status = int(data["error"].get("code") or 502)
                        text = json.dumps(data["error"])
                        rejected = True
                    else:
                        choices = data.get("choices")
                        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                            raise ValueError("response has no usable choice")
                        message = choices[0].get("message")
                        if not isinstance(message, dict):
                            raise ValueError("response has no usable message")
                except (ValueError, TypeError, AttributeError, IndexError) as exc:
                    status, text = 502, f"unparseable response: {exc}"
                else:
                    if not rejected:
                        if model == route.model:
                            self.cooldown_until.pop(route.model, None)
                        return self._success(data, message, model, role, latency, reservation)
            # Failed attempt. An HTTP error response means the request was rejected (no charge); a sent request
            # with no usable answer (timeout, reset, broken body) may have been charged: keep its reservation.
            if usage:
                cost, source = self.wallet.settle(reservation, model, usage)
            elif never_sent or rejected:
                cost, source = self.wallet.release(reservation)
            else:
                cost, source = self.wallet.keep_unknown(reservation)
            record = CallRecord(role, model, status, latency, cost, source, ok=False, **usage_fields(usage))
            temporary = is_temporary_budget_refusal(status, text, reply_headers)
            if not temporary and is_budget_refusal(status, text):
                self.wallet.mark_spent()
                record.note = f"budget refusal {status}"
                self.telemetry.append(record)
                raise BudgetExhausted(f"provider refused on budget grounds ({status})")
            last_error = f"{status}: {text[:300]}"
            record.note = last_error[:120]
            self.telemetry.append(record)
            retryable = status == 0 or status in RETRY_STATUS or temporary
            if not retryable:
                break
            if not temporary:  # a momentary spending reservation says nothing about the model (H-LLM-03)
                streak += 1
            if route.fallback and model == route.model and streak >= SWITCH_AFTER:
                record.note = f"switch {route.model} -> fallback {route.fallback} after {streak} failures; {last_error}"[:160]
                model, streak = route.fallback, 0
                self.cooldown_until[route.model] = self.clock() + PRIMARY_COOLDOWN_SEC
            pause = min(20.0, (2 ** attempt) + random.random())
            wait = retry_after_seconds(reply_headers)
            if wait is not None:
                pause = max(pause, wait)
            if deadline is not None:
                room = deadline - self.clock() - MIN_ATTEMPT_SEC
                if wait is not None and wait > room:
                    break  # the server asked for a wait this call cannot afford (H-LLM-09)
                pause = min(pause, room)
                if pause < 0:
                    break
            self.sleep(pause)
        raise LLMError(f"model call failed after retries: {last_error}")

    def _success(self, data: Dict, message: Dict, model: str, role: str, latency: float, reservation) -> ChatResult:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        cost, source = self.wallet.settle(reservation, model, usage)
        self.telemetry.append(CallRecord(role, model, 200, latency, cost, source, **usage_fields(usage)))
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
