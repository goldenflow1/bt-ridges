from observatory.report import daily_events

def test_empty_requested_interval(ch):
    assert daily_events(ch, 'acme', '2026-01-01', '2026-01-01', 'UTC') == []

def test_service_identity(ch):
    from observatory.report import service_name
    assert service_name() == 'observatory'
