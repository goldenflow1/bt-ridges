from observatory.report import missing_devices

def test_registered_devices_are_not_missing(ch):
    ch.command("INSERT INTO devices VALUES ('acme', 'a', 4, 'label', 1)")
    ch.command("INSERT INTO events VALUES ('acme', 1, 'a')")
    assert missing_devices(ch, 'acme') == []

def test_empty_tenant(ch):
    assert missing_devices(ch, 'empty') == []
