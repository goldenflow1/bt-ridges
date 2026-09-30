from datetime import UTC, datetime

from meterline.balances import CurrencyTotal, tenant_balance_summary


def stop_merges(ch):
    ch.command("SYSTEM STOP MERGES account_balances")


def active_parts(ch):
    rows = ch.query(
        "SELECT count() AS parts FROM system.parts "
        "WHERE database = currentDatabase() AND table = 'account_balances' AND active"
    )
    return int(rows[0]["parts"])


def test_unmerged_revisions_count_once(ch, ledger):
    stop_merges(ch)
    ledger.write("orbit", 11, 1, 20_000)
    ledger.write("orbit", 11, 2, 17_500)
    ledger.write("orbit", 11, 3, 16_125)
    ledger.write("orbit", 12, 1, 4_000)
    ledger.write("orbit", 12, 2, 3_000)
    ledger.write("orbit", 13, 1, 950, currency="USD")
    assert active_parts(ch) == 6

    assert tenant_balance_summary(ch, "orbit") == [
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=16_125 + 3_000),
        CurrencyTotal(currency="USD", accounts=1, balance_minor=950),
    ]


def test_out_of_order_arrival_uses_highest_revision(ch, ledger):
    stop_merges(ch)
    ledger.write("orbit", 21, 5, 1_200)
    ledger.write("orbit", 21, 3, 9_000)
    ledger.write("orbit", 21, 4, 5_000)
    ledger.write("orbit", 22, 1, 700)
    ledger.write("orbit", 22, 2, 650)
    ledger.write("orbit", 23, 9, 2_000)
    ledger.write("orbit", 23, 8, 1_000)

    assert tenant_balance_summary(ch, "orbit") == [
        CurrencyTotal(currency="EUR", accounts=3, balance_minor=1_200 + 650 + 2_000)
    ]


def test_current_status_and_currency_decide_membership(ch, ledger):
    stop_merges(ch)
    ledger.write("tundra", 31, 1, 5_000)
    ledger.write("tundra", 31, 2, 5_000, status="frozen")
    ledger.write("tundra", 32, 1, 0, status="closed")
    ledger.write("tundra", 32, 2, 2_500, status="active")
    ledger.write("tundra", 33, 1, 8_000)
    ledger.write("tundra", 33, 2, 0, status="closed")
    ledger.write("tundra", 34, 1, 6_600, currency="EUR")
    ledger.write("tundra", 34, 2, 7_100, currency="CHF")
    ledger.write("tundra", 35, 1, 300)

    assert tenant_balance_summary(ch, "tundra") == [
        CurrencyTotal(currency="CHF", accounts=1, balance_minor=7_100),
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=2_500 + 300),
    ]


def test_revision_not_timestamp_decides_the_current_row(ch, ledger):
    stop_merges(ch)
    same = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    earlier = datetime(2026, 5, 2, 11, 59, 58, tzinfo=UTC)
    ledger.write("delta", 41, 1, 4_400, at=same)
    ledger.write("delta", 41, 2, 4_100, at=same)
    ledger.write("delta", 41, 3, 3_900, at=same)
    ledger.write("delta", 42, 1, 8_000, at=same)
    ledger.write("delta", 42, 2, 6_000, at=earlier)
    ledger.write("delta", 43, 1, 1_000, at=same)
    ledger.write("delta", 43, 2, 1_000, status="frozen", at=earlier)

    assert tenant_balance_summary(ch, "delta") == [
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=3_900 + 6_000)
    ]


def test_repeated_balances_are_not_collapsed(ch, ledger):
    stop_merges(ch)
    ledger.write("delta", 51, 1, 500)
    ledger.write("delta", 51, 2, 800)
    ledger.write("delta", 51, 3, 500)
    ledger.write("delta", 52, 1, 500)
    ledger.write("delta", 53, 1, 500)
    ledger.write("delta", 53, 2, 500)

    assert tenant_balance_summary(ch, "delta") == [
        CurrencyTotal(currency="EUR", accounts=3, balance_minor=1_500)
    ]


def test_same_answer_before_and_after_merge(ch, ledger):
    stop_merges(ch)
    for account in range(61, 71):
        for revision in range(1, 5):
            status = "frozen" if account % 3 == 0 and revision == 4 else "active"
            ledger.write("summit", account, revision, account * 100 - revision, status=status)
    expected = [
        CurrencyTotal(
            currency="EUR",
            accounts=7,
            balance_minor=sum(a * 100 - 4 for a in range(61, 71) if a % 3),
        )
    ]
    assert active_parts(ch) == 40

    before = tenant_balance_summary(ch, "summit")
    ch.command("SYSTEM START MERGES account_balances")
    ledger.merge()
    after = tenant_balance_summary(ch, "summit")

    assert before == expected
    assert after == expected


def test_tenant_with_only_inactive_current_rows_is_empty(ch, ledger):
    stop_merges(ch)
    ledger.write("ember", 81, 1, 1_000)
    ledger.write("ember", 81, 2, 0, status="closed")
    ledger.write("ember", 82, 1, 2_000)
    ledger.write("ember", 82, 2, 2_000, status="frozen")
    ledger.write("orbit", 81, 1, 3_000)

    assert tenant_balance_summary(ch, "ember") == []
    assert tenant_balance_summary(ch, "orbit") == [
        CurrencyTotal(currency="EUR", accounts=1, balance_minor=3_000)
    ]


def test_currencies_sorted_by_code_not_by_size(ch, ledger):
    stop_merges(ch)
    ledger.write("fjord", 1, 1, 9_999, currency="AUD")
    ledger.write("fjord", 1, 2, 2_000, currency="AUD")
    ledger.write("fjord", 2, 1, 3_000, currency="AUD")
    ledger.write("fjord", 3, 1, 50, currency="EUR")
    ledger.write("fjord", 4, 1, 70, currency="EUR")
    ledger.write("fjord", 5, 1, 80, currency="EUR")
    ledger.write("fjord", 6, 1, 90_000, currency="USD")

    assert tenant_balance_summary(ch, "fjord") == [
        CurrencyTotal(currency="AUD", accounts=2, balance_minor=5_000),
        CurrencyTotal(currency="EUR", accounts=3, balance_minor=200),
        CurrencyTotal(currency="USD", accounts=1, balance_minor=90_000),
    ]
