from observatory.report import settled_total as report_settled_total


class QueryProbe:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def query(self, *args, **kwargs):
        rows = self.client.query(*args, **kwargs)
        self.calls.append(dict(self.client.last_statistics))
        return rows


def measured_total(client, *args):
    probe = QueryProbe(client)
    result = report_settled_total(probe, *args)
    assert len(probe.calls) == 1, "the report must execute exactly one SQL query"
    return result, probe.calls[0]['rows_read']


def settled_total(client, *args):
    return measured_total(client, *args)[0]


def test_filter_status_range_and_tenant(ch):
    ch.command("INSERT INTO events VALUES (7, '2026-01-01 00:00:00', 1, 'settled', 8), (7, '2026-01-01 12:00:00', 2, 'settled', -3), (7, '2026-01-01 12:00:00', 3, 'pending', 999), (7, '2026-01-02 00:00:00', 4, 'settled', 100), (8, '2026-01-01 12:00:00', 5, 'settled', 1000)")
    assert settled_total(ch, 7, '2026-01-01', '2026-01-02') == [{'total':5}]

def test_primary_key_read_rows_drop_tenfold(ch):
    size = 1048576
    ch.command(f"INSERT INTO events SELECT toUInt32(intDiv(number,8192)), toDateTime('2026-01-01') + (number % 8192), number, if(number % 3 = 0, 'pending', 'settled'), toInt64(number % 17) - 8 FROM numbers({size})")
    ch.command("OPTIMIZE TABLE events FINAL")
    for tenant in (9, 71, 117):
        params = {'tenant': tenant, 'start':'2026-01-01', 'end':'2026-01-02'}
        slow = "SELECT sum(amount) AS total FROM events WHERE cityHash64(tenant_id) = cityHash64({tenant:UInt32}) AND happened >= {start:DateTime} AND happened < {end:DateTime} AND status = 'settled' SETTINGS max_threads=1, use_query_cache=0"
        expected = ch.query(slow, params)
        original_reads = ch.last_statistics['rows_read']
        result, candidate_reads = measured_total(ch, tenant, params['start'], params['end'])
        assert result == expected
        assert original_reads >= size // 2, original_reads
        assert candidate_reads > 0
        assert candidate_reads * 10 <= original_reads, (candidate_reads, original_reads)

def test_same_tenant_narrow_window(ch):
    ch.command("INSERT INTO events VALUES (3, '2026-01-01 00:00:00', 1, 'settled', 4), (3, '2026-01-01 00:00:01', 2, 'settled', 9)")
    assert settled_total(ch, 3, '2026-01-01 00:00:00', '2026-01-01 00:00:01') == [{'total':4}]
