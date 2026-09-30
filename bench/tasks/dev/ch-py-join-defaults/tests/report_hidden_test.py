from observatory.report import missing_devices


def test_missing_and_valid_zero_identifier(ch):
    ch.command("INSERT INTO devices VALUES ('target', 'real-zero', 0, 'normal', 1)")
    ch.command("INSERT INTO events VALUES ('target', 8, 'missing'), ('target', 3, 'real-zero')")
    assert missing_devices(ch, 'target') == [{'event_id': 8, 'device': 'missing'}]

def test_empty_label_is_registered(ch):
    ch.command("INSERT INTO devices VALUES ('target', 'blank-label', 90, '', 1)")
    ch.command("INSERT INTO events VALUES ('target', 10, 'absent'), ('target', 2, 'blank-label')")
    assert missing_devices(ch, 'target') == [{'event_id': 10, 'device': 'absent'}]

def test_disabled_cross_tenant_order_and_empty_code(ch):
    ch.command("INSERT INTO devices VALUES ('other', 'cross', 11, 'x', 1), ('target', 'disabled', 7, 'x', 0), ('target', '', 9, '', 1)")
    ch.command("INSERT INTO events VALUES ('target', 40, 'cross'), ('target', 9, 'disabled'), ('target', 12, 'unknown'), ('target', 3, ''), ('other', 1, 'unknown')")
    assert missing_devices(ch, 'target') == [{'event_id': 9, 'device': 'disabled'}, {'event_id': 12, 'device': 'unknown'}, {'event_id': 40, 'device': 'cross'}]

def test_repeated_events_and_quoted_tenant(ch):
    ch.insert('events', [{'tenant': "reader's", 'event_id': i, 'device': 'gone'} for i in (5,2)])
    assert missing_devices(ch, "reader's") == [{'event_id': 2, 'device': 'gone'}, {'event_id': 5, 'device': 'gone'}]
