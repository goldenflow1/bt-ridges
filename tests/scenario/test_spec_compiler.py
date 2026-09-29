"""Scenario tests for the deterministic spec compiler (docs/specs/harness.md §5)."""

import os

import pytest

from quarry.spec import compile_statement

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PUBLIC = os.path.join(ROOT, "bench", "tasks", "public")


def load(name):
    with open(os.path.join(HERE, "statements", name + ".md")) as handle:
        return compile_statement(handle.read())


def load_public(name):
    with open(os.path.join(PUBLIC, name, "instruction.md")) as handle:
        return compile_statement(handle.read())


# ---- expectations: (fixture, field, expected)
SYNTHETIC = {
    "ch_replacing_repair": dict(
        kind="repair", engine="clickhouse", files=["app/reports/balances.py"], symbols=["current_balances"],
        mode="named", freeze_signature=True, freeze_imports=True, rest_frozen=True,
        checks=["pytest tests/test_balances.py -q"], forbidden=[],
    ),
    "go_sqlx_pagination": dict(
        kind="repair", files=["internal/store/events.go"], symbols=["Store.ListEvents"], mode="named",
        freeze_signature=True, rest_frozen=True,
        checks=["go test ./internal/store/... -run TestListEvents\ngo vet ./internal/store/..."],
    ),
    "ts_prisma_percent": dict(
        kind="repair", engine="postgresql", files=["src/stats/conversion.ts"], symbols=["conversionByCampaign"],
        checks=["npx vitest run src/stats", "npx tsc --noEmit -p ."],
    ),
    "pg_partial_index_migration": dict(
        kind="optimization", engine="postgresql", mode="open", allow_new_files=True,
        checks=["python manage.py test support.tests.test_queue --keepdb"],
    ),
    "unnamed_left_join": dict(
        kind="repair", mode="discover-one-symbol", freeze_signature=True, forbidden=["no_raw_sql"],
        checks=["pytest tests/test_roster.py"], templates=["ruff check {changed_files}"],
    ),
    "authoring_tz_buckets": dict(
        kind="authoring", engine="clickhouse", files=["growth/queries.py"], symbols=["daily_signups"],
        freeze_imports=True, rest_frozen=True, forbidden=["no_loops", "no_comprehensions"],
        checks=["python -m pytest tests/test_growth.py -q"],
    ),
    "add_tests_allowed": dict(kind="repair", allow_test_changes=True, checks=["pytest tests/test_totals.py"]),
    "sqla_optimization": dict(
        kind="optimization", files=["billing/repository.py"], symbols=["InvoiceRepository.list_invoices"],
        freeze_signature=True, freeze_imports=True, rest_frozen=True, forbidden=["no_python_materialization"],
    ),
    "positive_raw_sql": dict(kind="repair", files=["reports/sql.py"], forbidden=[]),
    "multiline_inline_command": dict(
        files=["app/counts.py"], symbols=["Counter.distinct_users"],
        checks=["python app/manage.py test app.tests.CountTests --keepdb --noinput", "ruff check --no-cache app/counts.py"],
    ),
    "no_scope_open": dict(kind="optimization", mode="open", files=[], symbols=[], checks=[]),
    "knex_window_authoring": dict(
        kind="authoring", files=["src/ledger/balances.ts"], mode="named", checks=["npm test -- ledger"],
    ),
}

PUBLIC_EXPECT = {
    "pg-netbox-bulk-tag-assignment-001": dict(
        kind="optimization", mode="discover-one-symbol", freeze_signature=True, freeze_imports=True, rest_frozen=True,
        forbidden_has=["no_raw_sql"], forbidden_not=["no_db_writes", "no_loops"], templates=["ruff check --no-cache {changed_files}"],
    ),
    "pg-netbox-cached-value-index-001": dict(
        kind="optimization", engine="postgresql", mode="named", allow_new_files=False,
        files=["netbox/extras/migrations/0107_cachedvalue_extras_cachedvalue_object.py"],
    ),
    "pg-netbox-contact-group-counts-001": dict(
        kind="repair", files=["netbox/tenancy/models/contacts.py"], symbols=["ContactGroupManager.annotate_contacts"],
        freeze_signature=True, freeze_imports=True, rest_frozen=True,
        forbidden_has=["no_loops", "no_comprehensions", "no_lambdas", "no_exception_handling", "no_context_managers",
                       "no_db_writes", "no_dynamic_code"],
        forbidden_not=["no_raw_sql"],
    ),
    "pg-netbox-ipaddress-device-filter-001": dict(
        kind="optimization", symbols=["IPAddressFilterSet.filter_device"], files=["netbox/ipam/filtersets.py"],
    ),
    "pg-netbox-prefix-hierarchy-annotations-001": dict(
        kind="authoring", symbols=["PrefixQuerySet.annotate_hierarchy"],
        checks=["python netbox/manage.py test ipam.tests.test_models.TestPrefixHierarchy --keepdb --noinput",
                "ruff check --no-cache netbox/ipam/querysets.py"],
    ),
    "pg-netbox-vlangroup-utilization-001": dict(kind="repair", symbols=["VLANGroupQuerySet.annotate_utilization"]),
}


def assert_expected(spec, expected):
    sc = spec.scope
    for key, value in expected.items():
        if key == "kind":
            assert spec.kind == value, (key, spec.kind)
        elif key == "engine":
            assert spec.engine == value, (key, spec.engine)
        elif key == "checks":
            assert spec.checks == value, (key, spec.checks)
        elif key == "templates":
            assert spec.check_templates == value, (key, spec.check_templates)
        elif key == "forbidden":
            assert sorted(spec.forbidden) == sorted(value), (key, spec.forbidden)
        elif key == "forbidden_has":
            assert set(value) <= set(spec.forbidden), (key, spec.forbidden)
        elif key == "forbidden_not":
            assert not set(value) & set(spec.forbidden), (key, spec.forbidden)
        else:
            assert getattr(sc, key) == value, (key, getattr(sc, key))


@pytest.mark.parametrize("name", sorted(SYNTHETIC))
def test_H_SPEC_01_to_10_synthetic_statements(name):
    assert_expected(load(name), SYNTHETIC[name])


@pytest.mark.parametrize("name", sorted(PUBLIC_EXPECT))
def test_H_SPEC_01_to_10_public_statements(name):
    assert_expected(load_public(name), PUBLIC_EXPECT[name])


def test_H_SPEC_01_fenced_block_kept_as_one_script():
    spec = load_public("pg-netbox-contact-group-counts-001")
    assert spec.checks == [
        "python netbox/manage.py test \\\n  tenancy.tests.test_models.ContactGroupTestCase \\\n  --keepdb --noinput\n"
        "ruff check --no-cache netbox/tenancy/models/contacts.py"
    ]


def test_H_SPEC_02_inline_command_on_changed_file_is_template():
    spec = load("unnamed_left_join")
    assert "ruff check {changed_files}" in spec.check_templates
    assert all("ruff" not in c for c in spec.checks)


def test_H_SPEC_03_workdir_is_not_a_scope_file():
    spec = load("ch_replacing_repair")
    assert "/app" not in spec.scope.files


def test_H_SPEC_04_symbols_outside_bounding_paragraph_ignored():
    spec = load_public("pg-netbox-ipaddress-device-filter-001")
    assert "Device.vc_interfaces" not in spec.scope.symbols


def test_H_SPEC_05_freeze_flags_absent_when_not_stated():
    spec = load("knex_window_authoring")
    assert not spec.scope.freeze_imports and not spec.scope.freeze_signature


def test_H_SPEC_06_discover_mode():
    assert load("unnamed_left_join").scope.mode == "discover-one-symbol"


def test_H_SPEC_07_only_stated_rules():
    assert load("positive_raw_sql").forbidden == []
    assert "no_raw_sql" not in load_public("pg-netbox-contact-group-counts-001").forbidden


def test_H_SPEC_08_kind_default_is_repair():
    assert compile_statement("Please look at this.").kind == "repair"


def test_H_SPEC_09_engine_unknown_without_keywords():
    assert load("go_sqlx_pagination").engine == "unknown"


def test_H_SPEC_10_new_files_only_when_asked():
    assert load("pg_partial_index_migration").scope.allow_new_files
    assert not load_public("pg-netbox-cached-value-index-001").scope.allow_new_files


def test_H_SPEC_11_render_is_compact_and_stable():
    spec = load_public("pg-netbox-contact-group-counts-001")
    text = spec.render()
    assert len(text) <= 2500
    assert text == spec.render()
    assert "R1." in text and "Check: " in text and "Forbidden:" in text
    long = compile_statement("# T\n\n" + "\n".join(f"- requirement number {i} " + "x" * 80 for i in range(100)))
    assert len(long.render()) <= 2500
