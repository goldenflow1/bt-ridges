from datetime import datetime, timedelta, timezone
import random

from sqlalchemy import event

from freight.api import dashboard
from freight.models import parcel, scan
from freight.repositories.tracking import current_scans


def test_backfilled_scans_do_not_replace_current_state(conn):
    conn.exec_driver_sql("INSERT INTO parcels VALUES (10,7,'X'),(20,7,'Y'),(30,8,'Z'),(40,7,'no-scans')")
    conn.exec_driver_sql("INSERT INTO scans VALUES (1,10,'2026-02-02','East','delivered'),(99,10,'2026-01-01','West','moving'),(2,20,'2026-01-03','South','moving'),(3,30,'2026-01-04','Secret','held')")
    result = dashboard(conn, 7)['current']
    assert [(r['parcel_id'],r['scan_id'],r['depot'],r['condition']) for r in result] == [(10,1,'East','delivered'),(20,2,'South','moving')]


def test_timestamp_ties_choose_one_complete_greatest_id_row(conn):
    at=datetime(2026,3,1,12,0,0,123456,tzinfo=timezone.utc)
    conn.execute(parcel.insert(),[{'id':p,'carrier_id':7,'reference':str(p)} for p in range(1,49)])
    records=[]
    for p in range(1,49):
        records += [{'id':p,'parcel_id':p,'recorded_at':at,'depot':'old','condition':'moving'},
                    {'id':p+1000,'parcel_id':p,'recorded_at':at.astimezone(timezone(timedelta(hours=5,minutes=30))),'depot':'current','condition':'held'}]
    conn.execute(scan.insert(),records)
    actual=current_scans(conn,7)
    expected=[{'parcel_id':p,'scan_id':p+1000,'recorded_at':at,'depot':'current','condition':'held'} for p in range(1,49)]
    assert actual == expected


def test_large_scrambled_history_matches_domain_reference_in_one_query(conn):
    rng=random.Random(90531)
    conn.execute(parcel.insert(),[{'id':p,'carrier_id':7 if p%3 else 8,'reference':str(p)} for p in range(1,181)])
    at=datetime(2026,1,1,tzinfo=timezone.utc)
    records=[{'id':i,'parcel_id':rng.randrange(1,181),'recorded_at':at+timedelta(seconds=rng.randrange(70),microseconds=rng.randrange(3)),
              'depot':'D'+str(i%9),'condition':['moving','held','delivered'][i%3]} for i in range(1,3001)]
    rng.shuffle(records)
    conn.execute(scan.insert(),records)
    expected={}
    for row in records:
        p=row['parcel_id']
        if p%3 and (p not in expected or (row['recorded_at'],row['id'])>(expected[p]['recorded_at'],expected[p]['id'])):
            expected[p]=row
    calls=[]
    returned=[]
    def capture(*args):
        calls.append(args[2])
    def capture_rows(connection,cursor,*args):
        returned.append(cursor.rowcount)
    event.listen(conn,'before_cursor_execute',capture)
    event.listen(conn,'after_cursor_execute',capture_rows)
    try:
        actual=current_scans(conn,7)
    finally:
        event.remove(conn,'before_cursor_execute',capture)
        event.remove(conn,'after_cursor_execute',capture_rows)
    wanted=[{'parcel_id':p,'scan_id':r['id'],'recorded_at':r['recorded_at'],'depot':r['depot'],'condition':r['condition']} for p,r in sorted(expected.items())]
    assert actual == wanted
    assert len(calls) == 1
    assert returned == [len(wanted)]
    assert all(isinstance(r['scan_id'],int) and isinstance(r['recorded_at'],datetime) for r in actual)
    conn.execute(scan.insert(),{'id':9999,'parcel_id':1,'recorded_at':at+timedelta(days=90),'depot':'fresh','condition':'delivered'})
    assert current_scans(conn,7)[0]['scan_id'] == 9999
