"""v004 A0 (whole-exchange deadlines) and A1a (recoverable routing, budget-refusal classes, Retry-After).

H-LLM-02/03/07/09 and H-WALLET-04 as revised 2026-10-01 after the v003 screening incident."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from quarry.llm import LLMError, ModelRoute, ProxyClient, http_transport
from quarry.wallet import BudgetExhausted, Wallet, is_budget_refusal, is_temporary_budget_refusal

OK = {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.001}}
ROUTE = ModelRoute("primary", "fallback")
MSG = [{"role": "user", "content": "hi"}]


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class Scripted:
    """Transport answering by model: each model has its own queue of (status, body[, headers])."""

    def __init__(self, **queues):
        self.queues = {model.replace("_", "-"): list(replies) for model, replies in queues.items()}
        self.models = []

    def __call__(self, url, body, headers, timeout):
        model = json.loads(body)["model"]
        self.models.append(model)
        reply = self.queues[model].pop(0) if self.queues.get(model) else (200, OK)
        status, payload = reply[0], reply[1]
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return (status, text, reply[2]) if len(reply) > 2 else (status, text)


def make(transport, clock=None, cap=1.0):
    clock = clock or FakeClock()
    wallet = Wallet(cap, {"primary": (0.2, 1.2), "fallback": (0.48, 4.2)})
    c = ProxyClient(wallet, {"SANDBOX_PROXY_URL": "http://proxy"}, transport, sleep=clock.sleep, clock=clock)
    return c, clock


# ---------------------------------------------------------------- A1a routing (H-LLM-02)


def test_H_LLM_02_v003_incident_two_transient_failures_no_longer_pin_the_run_to_the_fallback():
    # v003: 503, 503 on the primary in the first call -> every later call went to the fallback for the whole run.
    transport = Scripted(primary=[(503, "busy"), (503, "busy")])
    c, clock = make(transport)
    c.complete(MSG, ROUTE)                     # primary, primary, then fallback within this call
    clock.now += 61                            # past the 60 s cooldown
    for _ in range(5):
        c.complete(MSG, ROUTE)
    assert transport.models == ["primary", "primary", "fallback"] + ["primary"] * 5


def test_H_LLM_02_cooldown_avoids_hammering_an_unavailable_primary_then_probes_it():
    transport = Scripted(primary=[(503, "busy")] * 4)
    c, clock = make(transport)
    c.complete(MSG, ROUTE)                     # primary x2 -> fallback; cooldown starts
    c.complete(MSG, ROUTE)                     # within cooldown: straight to fallback
    clock.now += 61
    c.complete(MSG, ROUTE)                     # probe: primary fails twice more -> fallback, new cooldown
    c.complete(MSG, ROUTE)                     # within the new cooldown: fallback
    assert transport.models == ["primary", "primary", "fallback", "fallback",
                                "primary", "primary", "fallback", "fallback"]


def test_H_LLM_02_primary_success_clears_the_cooldown_and_failures_are_counted_per_call():
    transport = Scripted(primary=[(503, "busy"), (200, OK), (503, "busy"), (200, OK)])
    c, _ = make(transport)
    c.complete(MSG, ROUTE)                     # one failure, then success on the primary
    c.complete(MSG, ROUTE)                     # the earlier failure does not count toward a switch here
    assert transport.models == ["primary", "primary", "primary", "primary"]
    assert not c.cooldown_until


def test_H_LLM_02_switches_are_recorded_with_their_reason():
    transport = Scripted(primary=[(429, "slow down"), (503, "busy")])
    c, _ = make(transport)
    c.complete(MSG, ROUTE)
    notes = [r.note for r in c.telemetry if "fallback" in r.note]
    assert notes and "primary" in notes[0] and "503" in notes[0]


def test_H_LLM_02_fallback_failures_still_end_the_call():
    transport = Scripted(primary=[(503, "a"), (503, "b")], fallback=[(503, "c"), (503, "d")])
    c, _ = make(transport)
    with pytest.raises(LLMError):
        c.complete(MSG, ROUTE)
    assert transport.models == ["primary", "primary", "fallback", "fallback"]


def test_H_LLM_02_without_a_fallback_the_primary_is_retried_and_never_cooled_down():
    transport = Scripted(primary=[(503, "a"), (503, "b"), (200, OK)])
    c, _ = make(transport)
    c.complete(MSG, ModelRoute("primary"))
    assert transport.models == ["primary"] * 3 and not c.cooldown_until


# ---------------------------------------------------------------- budget refusals (H-LLM-03, H-WALLET-04)

TEMP = json.dumps({"error": {"code": 402, "message": "in_flight_budget_exhausted: too many reservations in flight"}})
HARD = json.dumps({"error": {"code": 402, "message": "budget_exhausted"}})


def test_H_WALLET_04_temporary_and_hard_budget_refusals_are_classified_apart():
    assert is_temporary_budget_refusal(402, TEMP, {})
    assert is_temporary_budget_refusal(402, HARD, {"retry-after": "3"})
    assert not is_temporary_budget_refusal(402, HARD, {})
    assert not is_temporary_budget_refusal(429, "rate limited", {"retry-after": "3"})
    assert is_budget_refusal(402, HARD) and is_budget_refusal(429, '{"error": "max cost exceeded for this run"}')


def test_H_LLM_03_temporary_budget_refusal_is_retried_without_marking_the_wallet_spent():
    transport = Scripted(primary=[(402, TEMP), (402, TEMP), (200, OK)])
    c, _ = make(transport)
    c.complete(MSG, ROUTE)
    assert transport.models == ["primary"] * 3      # not a model failure: no switch to the fallback
    assert not c.wallet.spent


def test_H_LLM_03_hard_budget_refusal_still_stops_immediately():
    transport = Scripted(primary=[(402, HARD), (200, OK)])
    c, _ = make(transport)
    with pytest.raises(BudgetExhausted):
        c.complete(MSG, ROUTE)
    assert transport.models == ["primary"] and c.wallet.spent


# ---------------------------------------------------------------- Retry-After (H-LLM-09)


def test_H_LLM_09_retry_after_sets_the_minimum_wait():
    transport = Scripted(primary=[(429, "slow", {"retry-after": "7"}), (200, OK)])
    c, clock = make(transport)
    c.complete(MSG, ROUTE, deadline=clock() + 120)
    assert clock.slept and clock.slept[0] >= 7


def test_H_LLM_09_retry_after_never_sleeps_past_the_deadline():
    transport = Scripted(primary=[(429, "slow", {"retry-after": "300"}), (200, OK)])
    c, clock = make(transport)
    start = clock()
    with pytest.raises(LLMError):
        c.complete(MSG, ModelRoute("primary"), deadline=start + 60)
    assert clock() <= start + 60 and transport.models == ["primary"]


def test_H_LLM_09_malformed_retry_after_is_ignored():
    transport = Scripted(primary=[(503, "busy", {"retry-after": "soon"}), (503, "busy", {"retry-after": "-4"}), (200, OK)])
    c, clock = make(transport)
    c.complete(MSG, ModelRoute("primary"), deadline=clock() + 120)
    assert all(s < 20 for s in clock.slept) and len(clock.slept) == 2


# ---------------------------------------------------------------- A0 whole-exchange deadline (H-LLM-07)


class Trickle(BaseHTTPRequestHandler):
    status = 200
    size = 20
    pause = 0.05

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(self.status)
        self.send_header("Content-Length", str(self.size))
        self.end_headers()
        try:
            for _ in range(self.size):
                self.wfile.write(b" ")
                self.wfile.flush()
                time.sleep(self.pause)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_):
        pass


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.parametrize("status", [200, 500])
def test_H_LLM_07_a_trickled_body_cannot_outlive_the_attempt_timeout(status):
    handler = type("H", (Trickle,), {"status": status})   # 20 bytes x 50 ms = 1 s of body
    server = serve(handler)
    try:
        started = time.monotonic()
        with pytest.raises((TimeoutError, OSError)):
            http_transport(f"http://127.0.0.1:{server.server_port}/x", b"{}", {}, 0.3)
        assert time.monotonic() - started < 0.8
    finally:
        server.shutdown()
        server.server_close()


def test_H_LLM_07_oversized_bodies_are_rejected():
    handler = type("H", (Trickle,), {"size": 4096, "pause": 0.0})
    server = serve(handler)
    try:
        with pytest.raises(ValueError):
            http_transport(f"http://127.0.0.1:{server.server_port}/x", b"{}", {}, 5.0, max_bytes=1024)
    finally:
        server.shutdown()
        server.server_close()


def test_H_LLM_07_a_normal_exchange_returns_status_body_and_lowercase_headers():
    class Ok(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.dumps(OK).encode()
            self.send_response(429)
            self.send_header("Retry-After", "2")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = serve(Ok)
    try:
        status, text, headers = http_transport(f"http://127.0.0.1:{server.server_port}/x", b"{}", {}, 5.0)
        assert status == 429 and json.loads(text) == OK and headers["retry-after"] == "2"
    finally:
        server.shutdown()
        server.server_close()


def test_H_LLM_07_a_cut_off_exchange_keeps_its_cost_reservation():
    def transport(url, body, headers, timeout):
        raise TimeoutError("response body exceeded the attempt deadline")

    c, _ = make(transport)
    with pytest.raises(LLMError):
        c.complete(MSG, ModelRoute("primary"), deadline=1000.0 + 60)
    assert all(r.cost_source == "unknown" for r in c.telemetry) and c.wallet.consumed_usd > 0
