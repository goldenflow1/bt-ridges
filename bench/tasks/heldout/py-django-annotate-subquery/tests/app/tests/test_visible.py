from datetime import datetime, timezone

from clinic.api import get_roster
from clinic.repositories.calendar import calendar
from clinic.repositories.workload import appointment_overview

NOW = datetime(2026,1,1,tzinfo=timezone.utc)


def test_existing_roster_and_calendar_contracts(conn):
    conn.execute("INSERT INTO doctors VALUES (1,7,'Alma'),(2,8,'Zoe')")
    conn.execute("INSERT INTO sessions VALUES (1,1,45,true),(2,2,30,true)")
    conn.execute("INSERT INTO appointments VALUES (1,1,'2026-01-03','open'),(2,2,'2026-01-04','open')")
    doctors=get_roster(7,NOW)['doctors']
    assert [(d['id'],d['name'],d['approved_minutes']) for d in doctors] == [(1,'Alma',45)]
    assert appointment_overview(7) == [{'state':'open','total':1}]
    assert calendar(7,NOW,datetime(2026,2,1,tzinfo=timezone.utc)) == [{'id':1,'doctor_id':1,'state':'open'}]


def test_absent_clinic(conn):
    assert get_roster(999,NOW) == {'doctors':[]}
