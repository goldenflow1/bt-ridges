from grid.api import get_connections
from grid.reports.history import received_event_count


def test_simple_online_panel_and_history(ch):
    ch.insert('meter_events',[{'utility':'u','meter_id':'M1','observed_at':'2026-01-01 12:00:00','version':1,'state':'online','region':'North','reading':10}])
    assert get_connections(ch,'u','North')['meters'] == [{'meter_id':'M1','state':'online','region':'North','reading':10,'observed_us':1767268800000000,'version':1}]
    assert received_event_count(ch,'u') == 1


def test_empty_utility(ch):
    assert get_connections(ch,'absent','North') == {'meters':[]}
