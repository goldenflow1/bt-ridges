from datetime import datetime, timedelta, timezone

from django.db import connection
from django.db.models import QuerySet
from django.test.utils import CaptureQueriesContext

from clinic.api import get_roster
from clinic.models import Appointment, Doctor, Session
from clinic.repositories.workload import doctor_workload

NOW=datetime(2026,1,10,12,tzinfo=timezone.utc)


def test_unrelated_annotations_do_not_fan_out(conn):
    conn.execute("INSERT INTO doctors VALUES (1,7,'Alma')")
    conn.execute("INSERT INTO sessions VALUES (1,1,30,true),(2,1,45,true),(3,1,90,false)")
    conn.execute("INSERT INTO appointments VALUES (1,1,'2026-02-01','open'),(2,1,'2026-02-02','open'),(3,1,'2026-02-03','cancelled')")
    assert get_roster(7,NOW)['doctors'] == [{'id':1,'name':'Alma','approved_minutes':75,'open_appointments':2}]


def test_empty_and_nonmatching_counts_are_integer_zero(conn):
    conn.execute("INSERT INTO doctors VALUES (1,7,'Alma'),(2,7,'Bo'),(3,7,'Cai')")
    conn.execute("INSERT INTO appointments VALUES (1,2,'2026-01-09','open'),(2,3,'2026-02-01','closed')")
    actual=get_roster(7,NOW)['doctors']
    assert [row['open_appointments'] for row in actual] == [0,0,0]
    assert all(type(row['open_appointments']) is int and type(row['approved_minutes']) is int for row in actual)
    assert [row['approved_minutes'] for row in actual] == [0,0,0]


def test_boundary_clinic_isolation_ties_and_fresh_state(conn):
    Doctor.objects.bulk_create([Doctor(id=i,clinic_id=7 if i<4 else 8,display_name='Same') for i in [3,2,1,4]])
    Appointment.objects.bulk_create([
        Appointment(id=1,doctor_id=1,starts_at=NOW,state='open'),
        Appointment(id=2,doctor_id=1,starts_at=NOW-timedelta(microseconds=1),state='open'),
        Appointment(id=3,doctor_id=1,starts_at=NOW+timedelta(seconds=1),state='closed'),
        Appointment(id=4,doctor_id=4,starts_at=NOW,state='open')])
    equivalent=NOW.astimezone(timezone(timedelta(hours=5,minutes=30)))
    result=get_roster(7,equivalent)['doctors']
    assert [r['id'] for r in result] == [1,2,3]
    assert [r['open_appointments'] for r in result] == [1,0,0]
    Appointment.objects.filter(id=1).update(state='closed')
    assert get_roster(7,NOW)['doctors'][0]['open_appointments'] == 0


def test_query_count_is_constant_at_one_and_fifty_doctors(conn):
    for count in [1,50]:
        Appointment.objects.all().delete()
        Session.objects.all().delete()
        Doctor.objects.all().delete()
        Doctor.objects.bulk_create([Doctor(id=i,clinic_id=7,display_name=f'D{i:03}') for i in range(1,count+1)])
        Appointment.objects.bulk_create([Appointment(doctor_id=i,starts_at=NOW,state='open') for i in range(1,count+1) for _ in range(3)])
        Session.objects.bulk_create([Session(doctor_id=i,minutes=20,approved=True) for i in range(1,count+1) for _ in range(2)])
        with CaptureQueriesContext(connection) as queries:
            queryset=doctor_workload(7,NOW)
            assert isinstance(queryset,QuerySet)
            assert not queries.captured_queries
            actual=list(queryset)
        assert len(queries) == 1
        assert len(actual) == count
        assert all(d.open_appointments==3 and d.approved_minutes==40 for d in actual)
        assert all(type(d.open_appointments) is int for d in actual)
