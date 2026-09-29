from meterline.balances import (
    CurrencyTotal,
    account_history,
    current_balance,
    tenant_balance_summary,
)


def test_summary_totals_per_currency(ch, ledger):
    ledger.write("acme", 1, 1, 12_000)
    ledger.write("acme", 2, 1, 3_500)
    ledger.write("acme", 3, 1, 900, currency="USD")

    assert tenant_balance_summary(ch, "acme") == [
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=15_500),
        CurrencyTotal(currency="USD", accounts=1, balance_minor=900),
    ]


def test_summary_is_scoped_to_tenant(ch, ledger):
    ledger.write("acme", 1, 1, 12_000)
    ledger.write("globex", 1, 1, 99_999)

    assert tenant_balance_summary(ch, "globex") == [
        CurrencyTotal(currency="EUR", accounts=1, balance_minor=99_999)
    ]


def test_summary_skips_frozen_and_closed_accounts(ch, ledger):
    ledger.write("acme", 1, 1, 12_000)
    ledger.write("acme", 2, 1, 4_000, status="frozen")
    ledger.write("acme", 3, 1, 0, status="closed")

    assert tenant_balance_summary(ch, "acme") == [
        CurrencyTotal(currency="EUR", accounts=1, balance_minor=12_000)
    ]


def test_summary_after_merge_uses_latest_revision(ch, ledger):
    ledger.write("acme", 1, 1, 10_000)
    ledger.write("acme", 1, 2, 7_250)
    ledger.write("acme", 2, 1, 500)
    ledger.merge()

    assert tenant_balance_summary(ch, "acme") == [
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=7_750)
    ]


def test_summary_for_unknown_tenant_is_empty(ch, ledger):
    ledger.write("acme", 1, 1, 10_000)

    assert tenant_balance_summary(ch, "initech") == []


def test_negative_balances_are_summed(ch, ledger):
    ledger.write("acme", 1, 1, -2_500)
    ledger.write("acme", 2, 1, 1_000)

    assert tenant_balance_summary(ch, "acme") == [
        CurrencyTotal(currency="EUR", accounts=2, balance_minor=-1_500)
    ]


def test_history_lists_revisions_in_order(ch, ledger):
    ledger.write("acme", 7, 2, 800)
    ledger.write("acme", 7, 1, 1_000)
    ledger.write("acme", 7, 3, 650, status="frozen")

    history = account_history(ch, "acme", 7)

    assert [(r.revision, r.balance_minor, r.status) for r in history] == [
        (1, 1_000, "active"),
        (2, 800, "active"),
        (3, 650, "frozen"),
    ]


def test_current_balance_picks_highest_revision(ch, ledger):
    ledger.write("acme", 8, 4, 300)
    ledger.write("acme", 8, 2, 900)

    current = current_balance(ch, "acme", 8)

    assert current is not None
    assert (current.revision, current.balance_minor) == (4, 300)
    assert current_balance(ch, "acme", 9) is None
