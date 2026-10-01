"""M0.5A: cost provenance (H-WALLET-06) and cache telemetry (H-LLM-08)."""

import json
import socket
import urllib.error

import pytest

from quarry.llm import LLMError, ModelRoute, ProxyClient
from quarry.telemetry import TELEMETRY_PREFIX, build_record, format_line, parse_log
from quarry.wallet import BudgetExhausted, Wallet
from tools.bench_cost import reconcile, trusted_cost
from tools.run_bench import SessionLedger, bench_lock, flatten_telemetry, format_cost, settled_usage

PRICES = {"m": (1.0, 1.0), "fb": (1.0, 1.0)}


def ok_body(usage):
    body = {"choices": [{"message": {"content": "hi"}}]}
    if usage is not None:
        body["usage"] = usage
    return 200, json.dumps(body)


def client(replies, cap=1.0):
    replies = list(replies)

    def transport(url, body, headers, timeout):
        item = replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    return ProxyClient(Wallet(cap, PRICES), {"SANDBOX_PROXY_URL": "http://p"}, transport, sleep=lambda s: None)


ROUTE = ModelRoute("m", max_tokens=100)


def call(c, route=None):
    return c.complete([{"role": "user", "content": "x"}], route or ROUTE)


# ---------------------------------------------------------------- H-WALLET-06


def test_H_WALLET_06_reported_positive_and_zero_cost_are_provider():
    c = client([ok_body({"cost": 0.002, "prompt_tokens": 10, "completion_tokens": 5}), ok_body({"cost": 0, "prompt_tokens": 1, "completion_tokens": 1})])
    call(c), call(c)
    assert [r.cost_source for r in c.telemetry] == ["provider", "provider"]
    assert [r.cost for r in c.telemetry] == [0.002, 0.0]
    s = c.wallet.summary()
    assert s["provider_usd"] == 0.002 and s["estimated_calls"] == 0 and s["accounting_complete"]


def test_H_WALLET_06_usage_without_cost_is_labelled_estimate():
    c = client([ok_body({"prompt_tokens": 1000, "completion_tokens": 1000})])
    call(c)
    rec = c.telemetry[0]
    assert rec.cost_source == "estimate" and rec.cost == pytest.approx(0.002)
    s = c.wallet.summary()
    assert s["cost_estimated"] and s["estimate_usd"] == pytest.approx(0.002) and s["provider_usd"] == 0


def test_H_WALLET_06_absent_usage_is_unknown_and_keeps_reservation():
    c = client([ok_body(None)])
    call(c)
    rec = c.telemetry[0]
    assert rec.cost is None and rec.cost_source == "unknown"
    w = c.wallet
    assert w.unknown_attempts == 1 and w.unknown_usd > 0 and not w.accounting_complete
    assert w.consumed_usd == pytest.approx(w.unknown_usd)


def test_H_WALLET_06_timeout_keeps_reservation_refused_connection_releases():
    refused = urllib.error.URLError(ConnectionRefusedError(111, "refused"))
    c = client([socket.timeout("timed out"), refused, ok_body({"cost": 0.001})])
    call(c)
    sources = [r.cost_source for r in c.telemetry]
    assert sources == ["unknown", "none", "provider"]
    assert c.wallet.unknown_attempts == 1
    assert c.wallet.consumed_usd == pytest.approx(c.wallet.unknown_usd + 0.001)
    assert c.wallet.pending_usd == pytest.approx(0.0)


def test_H_WALLET_06_http_error_response_releases_reservation():
    c = client([(500, "upstream error"), ok_body({"cost": 0.001})])
    call(c)
    assert [r.cost_source for r in c.telemetry] == ["none", "provider"]
    assert c.wallet.consumed_usd == pytest.approx(0.001)


def test_H_WALLET_06_retry_refused_when_estimate_no_longer_fits():
    # each attempt reserves ~ (prompt + 100 out tokens) at $1/M; a tiny cap fits one attempt only
    c = client([socket.timeout("t"), ok_body({"cost": 0.0})], cap=0.00025)
    with pytest.raises(BudgetExhausted):
        call(c)
    assert len(c.telemetry) == 1 and c.telemetry[0].cost_source == "unknown"


@pytest.mark.parametrize("body", ['{', '[]', '{}', '{"choices": [null]}', '{"choices": [{"message": []}]}'])
def test_H_WALLET_06_malformed_success_keeps_reservation_and_blocks_unaffordable_retry(body):
    c = client([(200, body), ok_body({"cost": 0})], cap=0.00025)
    with pytest.raises(BudgetExhausted):
        call(c)
    assert len(c.telemetry) == 1 and c.telemetry[0].cost_source == "unknown"
    assert c.wallet.consumed_usd > 0 and not c.wallet.accounting_complete


def test_H_WALLET_06_broken_message_with_usage_still_counts_reported_charge():
    c = client([(200, '{"usage": {"cost": 0.001}, "choices": []}'), ok_body({"cost": 0.002})])
    call(c)
    assert [r.cost_source for r in c.telemetry] == ["provider", "provider"]
    assert c.wallet.consumed_usd == pytest.approx(0.003)


@pytest.mark.parametrize("delta", [0.1, -1, float('nan'), float('inf'), None])
def test_H_WALLET_06_unattributable_key_usage_is_not_trial_cost(delta):
    row = {'cost_provider': 0.01, 'accounting_complete': True, 'estimated_calls': 0, 'unknown_attempts': 0}
    result = reconcile(row, delta)
    assert result['reconciled_cost'] is None and result['cost_reconciliation'] != 'matched'
    assert trusted_cost(dict(row, reconciled_cost=delta)) is None


def test_H_WALLET_06_reconciliation_requires_complete_provider_accounting():
    row = {'cost_provider': 0.01, 'accounting_complete': True, 'estimated_calls': 0, 'unknown_attempts': 0}
    assert reconcile(row, .01001)['reconciled_cost'] == .01001
    assert reconcile(dict(row, unknown_attempts=1), .01)['reconciled_cost'] is None
    assert reconcile(dict(row, estimated_calls=1), .01)['reconciled_cost'] is None
    assert reconcile(dict(row, accounting_complete=False), .01)['reconciled_cost'] is None
    zero = dict(row, cost_provider=0)
    assert trusted_cost(dict(zero, **reconcile(zero, 0))) == 0


def test_H_WALLET_06_reservation_is_replaced_not_doubled():
    w = Wallet(1.0, PRICES)
    res = w.reserve(0.05)
    assert w.remaining() == pytest.approx(0.9 - 0.05)
    cost, source = w.settle(res, "m", {"cost": 0.01})
    assert (cost, source) == (0.01, "provider")
    assert w.remaining() == pytest.approx(0.9 - 0.01) and w.pending_usd == 0
    with pytest.raises(ValueError):
        w.settle(res, "m", {"cost": 0.01})


def test_H_WALLET_06_run_telemetry_never_shows_unknown_as_zero():
    row = flatten_telemetry(None)
    assert row["telemetry"] == "missing" and row["cost_accounted"] is None
    assert format_cost({**row, "reconciled_cost": None}) == "unknown"
    legacy = flatten_telemetry(None, "[quarry] calls=3 prompt_tokens=9 cached_tokens=0 cost=$0.0100 elapsed=5s")
    assert legacy["telemetry"] == "legacy-incomplete" and legacy["cost_accounted"] is None


def test_H_WALLET_06_host_ledger_uses_key_usage_delta_and_never_double_counts(tmp_path):
    usage = {"v": 10.0}
    ledger = SessionLedger(str(tmp_path / "ledger.json"), 30.0, lambda: usage["v"])
    usage["v"] = 10.5
    ledger.record("run/a/r1", 0.29, 0.5, 0.4)
    ledger.record("run/a/r1", 0.29, 0.5, 0.4)  # re-recording the same trial
    assert ledger.spent() == {"usd": 0.5, "source": "key-usage"}
    offline = SessionLedger(str(tmp_path / "l2.json"), 1.0, lambda: None)
    offline.record("run/a/r1", 0.29, None, 0.2)
    offline.record("run/a/r1", 0.29, None, 0.2)
    offline.record("run/b/r1", 0.29, None, None)  # nothing known: counts its full allowance
    assert offline.spent() == {"usd": pytest.approx(0.49), "source": "per-run records"}
    assert offline.fits(0.29) and not offline.fits(0.6)


def test_H_WALLET_06_settled_usage_waits_for_billing_to_catch_up():
    reads = iter([1.0, 1.2, 1.3, 1.3])
    assert settled_usage(lambda: next(reads), sleep=lambda s: None) == 1.3


def test_H_WALLET_06_concurrent_bench_cannot_share_a_key(tmp_path):
    identity = str(tmp_path)
    with bench_lock(identity), pytest.raises(RuntimeError, match='Another benchmark'):
        with bench_lock(identity):
            pytest.fail('overlapping run acquired the lock')
    with bench_lock(identity):
        pass


# ---------------------------------------------------------------- H-LLM-08


def records_for(usages):
    c = client([ok_body(u) for u in usages])
    for _ in usages:
        call(c)
    return c


def test_H_LLM_08_missing_zero_positive_cache_fields():
    c = records_for([
        {"cost": 0.001, "prompt_tokens": 100, "completion_tokens": 1},
        {"cost": 0.001, "prompt_tokens": 100, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 0}},
        {"cost": 0.001, "prompt_tokens": 100, "completion_tokens": 1,
         "prompt_tokens_details": {"cached_tokens": 80, "cache_write_tokens": 20}},
    ])
    assert [r.cached_tokens for r in c.telemetry] == [None, 0, 80]
    assert [r.cache_write_tokens for r in c.telemetry] == [None, None, 20]


def test_H_LLM_08_independent_read_write_coverage_and_share_denominator():
    c = records_for([
        {"cost": 0.001, "prompt_tokens": 100, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 50}},
        {"cost": 0.001, "prompt_tokens": 300, "completion_tokens": 1, "prompt_tokens_details": {"cache_write_tokens": 300}},
        {"cost": 0.001, "prompt_tokens": 100, "completion_tokens": 1},
    ])
    rec = build_record(c.telemetry, c.wallet)
    read, write, share = rec["cache"]["read"], rec["cache"]["write"], rec["cache"]["read_share"]
    assert (read["reported_calls"], read["coverage"], read["tokens"]) == (1, "partial", 50)
    assert (write["reported_calls"], write["coverage"], write["tokens"]) == (1, "partial", 300)
    assert share == {"value": 0.5, "over_calls": 1, "coverage": "partial"}  # only the call reporting reads
    none = build_record(records_for([{"cost": 0.001, "prompt_tokens": 1, "completion_tokens": 1}]).telemetry, Wallet(1))
    assert none["cache"]["read"]["tokens"] is None and none["cache"]["read_share"]["value"] is None


def test_H_LLM_08_failed_attempts_do_not_count_as_cache_reports():
    c = client([socket.timeout("t"), ok_body({"cost": 0.001, "prompt_tokens": 10, "completion_tokens": 1,
                                               "prompt_tokens_details": {"cached_tokens": 5}})])
    call(c)
    rec = build_record(c.telemetry, c.wallet)
    assert rec["attempts"] == 2 and rec["cache"]["successful_calls"] == 1 and rec["cache"]["read"]["coverage"] == "complete"


def test_H_LLM_08_versioned_line_roundtrip_and_unsupported_version():
    c = records_for([{"cost": 0.001, "prompt_tokens": 10, "completion_tokens": 1}])
    line = format_line(build_record(c.telemetry, c.wallet, {"elapsed_sec": 3.0}))
    assert line.startswith(TELEMETRY_PREFIX) and "Authorization" not in line
    parsed = parse_log("noise\n" + line + "\nmore noise")
    assert parsed["version"] == 1 and parsed["elapsed_sec"] == 3.0
    row = flatten_telemetry(parsed)
    assert row["telemetry"] == "v1" and row["cost_provider"] == 0.001 and row["cache_read_tokens"] is None
    bad = parse_log(TELEMETRY_PREFIX + json.dumps({"version": 99}))
    assert bad["unsupported"] and flatten_telemetry(bad)["cost_accounted"] is None


def test_H_LLM_08_all_attempts_failing_still_reports():
    c = client([(503, "busy")] * 4)
    with pytest.raises(LLMError):
        call(c)
    rec = build_record(c.telemetry, c.wallet)
    assert rec["attempts"] == 4 and rec["cache"]["successful_calls"] == 0
    assert rec["cache"]["read"]["coverage"] == "none" and rec["cost"]["accounting_complete"]
