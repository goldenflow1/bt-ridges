from observatory.report import daily_events as report_daily_events


class QueryProbe:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def query(self, *args, **kwargs):
        rows = self.client.query(*args, **kwargs)
        self.calls.append(dict(self.client.last_statistics))
        return rows


def daily_events(client, *args):
    probe = QueryProbe(client)
    result = report_daily_events(probe, *args)
    assert len(probe.calls) == 1, "counting and day generation require one SQL query"
    return result


def add(ch, tenant, times):
    ch.insert('events', [{'tenant': tenant, 'happened': t} for t in times])

def test_empty_days_are_materialized(ch):
    add(ch, 't', ['2026-02-02 12:00:00.000'])
    assert daily_events(ch, 't', '2026-02-01', '2026-02-04', 'UTC') == [{'day':'2026-02-01','events':0}, {'day':'2026-02-02','events':1}, {'day':'2026-02-03','events':0}]

def test_spring_forward_local_days_and_half_open(ch):
    add(ch, 't', ['2026-03-08 04:59:59.999', '2026-03-08 05:00:00.000', '2026-03-09 03:59:59.999', '2026-03-09 04:00:00.000'])
    assert daily_events(ch, 't', '2026-03-08', '2026-03-09', 'America/New_York') == [{'day':'2026-03-08','events':2}]

def test_fall_back_day_includes_last_hour(ch):
    add(ch, 't', ['2026-11-01 04:00:00.000', '2026-11-01 05:30:00.000', '2026-11-01 06:30:00.000', '2026-11-02 04:59:59.999', '2026-11-02 05:00:00.000'])
    assert daily_events(ch, 't', '2026-11-01', '2026-11-02', 'America/New_York') == [{'day':'2026-11-01','events':4}]

def test_fractional_offset_tenant_and_leap_day(ch):
    add(ch, "owner's", ['2024-02-28 18:14:59.999', '2024-02-28 18:15:00.000', '2024-02-29 18:14:59.999', '2024-02-29 18:15:00.000'])
    add(ch, 'other', ['2024-02-29 10:00:00.000'])
    assert daily_events(ch, "owner's", '2024-02-29', '2024-03-01', 'Asia/Kathmandu') == [{'day':'2024-02-29','events':2}]

def test_no_events_and_reverse_range(ch):
    assert daily_events(ch, 'absent', '2026-05-01', '2026-05-03', 'Europe/Berlin') == [{'day':'2026-05-01','events':0}, {'day':'2026-05-02','events':0}]
    assert daily_events(ch, 'absent', '2026-05-03', '2026-05-01', 'UTC') == []
