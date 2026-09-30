from observatory.report import visitor_count


def test_large_exact_cardinality(ch):
    for size in (180013, 310019):
        ch.command("TRUNCATE TABLE visits")
        ch.command(f"INSERT INTO visits SELECT 'large', number * 7919 + 13, toDateTime('2026-01-01 12:00:00') FROM numbers({size})")
        assert visitor_count(ch, 'large', '2026-01-01', '2026-01-02') == [{'visitors': size}]

def test_null_is_not_a_visitor(ch):
    ch.command("INSERT INTO visits VALUES ('nulls', NULL, '2026-01-01 12:00:00'), ('nulls', 8, '2026-01-01 12:00:00'), ('nulls', 8, '2026-01-01 12:00:00')")
    assert visitor_count(ch, 'nulls', '2026-01-01', '2026-01-02') == [{'visitors': 1}]

def test_zero_duplicates_tenants_and_half_open_bounds(ch):
    ch.command("INSERT INTO visits VALUES ('chosen', 0, '2026-01-01 00:00:00'), ('chosen', 0, '2026-01-01 23:59:59'), ('chosen', 5, '2026-01-02 00:00:00'), ('chosen', 6, '2025-12-31 23:59:59'), ('other', 9, '2026-01-01 00:00:00')")
    assert visitor_count(ch, 'chosen', '2026-01-01', '2026-01-02') == [{'visitors': 1}]

def test_all_null_and_quoted_tenant(ch):
    ch.insert('visits', [{'tenant': "owner's", 'visitor': None, 'happened': '2026-01-01 01:00:00'}])
    assert visitor_count(ch, "owner's", '2026-01-01', '2026-01-02') == [{'visitors': 0}]
