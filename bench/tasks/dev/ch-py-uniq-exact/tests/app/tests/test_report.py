from observatory.report import visitor_count

def test_small_sample(ch):
    ch.command("INSERT INTO visits VALUES ('acme', 1, '2026-01-01 12:00:00'), ('acme', 2, '2026-01-01 12:00:00')")
    assert visitor_count(ch, 'acme', '2026-01-01', '2026-01-02') == [{'visitors': 2}]

def test_empty_window(ch):
    assert visitor_count(ch, 'absent', '2026-01-01', '2026-01-02') == [{'visitors': 0}]
