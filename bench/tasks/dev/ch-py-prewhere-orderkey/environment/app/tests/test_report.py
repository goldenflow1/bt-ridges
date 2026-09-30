from observatory.report import settled_total

def test_small_total(ch):
    ch.command("INSERT INTO events VALUES (7, '2026-01-01 12:00:00', 1, 'settled', 8), (7, '2026-01-01 13:00:00', 2, 'settled', -3)")
    assert settled_total(ch, 7, '2026-01-01', '2026-01-02') == [{'total':5}]

def test_missing_tenant(ch):
    assert settled_total(ch, 19, '2026-01-01', '2026-01-02') == [{'total':0}]
