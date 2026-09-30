from grid.api import get_connections


def row(meter,time,version,state='online',region='North',reading=0,utility='u'):
    return dict(utility=utility,meter_id=meter,observed_at=time,version=version,state=state,region=region,reading=reading)


def test_current_state_precedes_online_and_region_filters(ch):
    ch.insert('meter_events',[
        row('disconnected','2026-01-01',1),row('disconnected','2026-01-02',2,'offline'),
        row('moved','2026-01-01',1),row('moved','2026-01-02',2,region='South'),
        row('stable','2026-01-01',1,reading=-5)])
    assert [r['meter_id'] for r in get_connections(ch,'u','North')['meters']] == ['stable']
    assert [r['meter_id'] for r in get_connections(ch,'u','South')['meters']] == ['moved']


def test_version_ties_choose_the_complete_latest_payload(ch):
    events=[]
    for i in range(40):
        events += [row(f'M{i:03}','2026-02-01 12:00:00.123456',1,'offline','Old',999),
                   row(f'M{i:03}','2026-02-01 12:00:00.123456',2,'online','North',-i)]
    ch.insert('meter_events',events)
    result=get_connections(ch,'u','North')['meters']
    assert result == [{'meter_id':f'M{i:03}','state':'online','region':'North','reading':-i,'version':2,'observed_us':1769947200123456} for i in range(40)]


def test_event_time_over_version_precision_parameter_binding_and_freshness(ch):
    utility="utility'quoted"
    region="north'wing"
    ch.insert('meter_events',[
        row('M','2026-03-01 12:00:00.000001',1,region=region,reading=-1,utility=utility),
        row('M','2026-03-01 12:00:00.000000',99,'offline',region,100,utility),
        row('foreign','2026-03-01',1,region=region,utility='other')])
    result=get_connections(ch,utility,region)['meters']
    assert len(result)==1 and result[0]['meter_id']=='M' and result[0]['reading']==-1 and result[0]['version']==1
    ch.insert('meter_events',[row('M','2026-03-01 12:00:01',2,'offline',region,0,utility)])
    assert get_connections(ch,utility,region)['meters']==[]


def test_single_query_returns_only_current_rows_and_stable_order(ch):
    rows=[]
    for i in reversed(range(1,101)):
        rows += [row(f'M{i:03}','2026-01-01',1,region='Old'),row(f'M{i:03}','2026-01-02',2,reading=i)]
    ch.insert('meter_events',rows)
    class MeasuredClient:
        def __init__(self):
            self.calls=[]
        def query(self,sql,params=None):
            result=ch.query(sql,params)
            self.calls.append((sql,params,len(result)))
            return result
    measured=MeasuredClient()
    result=get_connections(measured,'u','North')['meters']
    assert [r['meter_id'] for r in result]==[f'M{i:03}' for i in range(1,101)]
    assert len(measured.calls)==1 and measured.calls[0][2]==100
    assert all(type(r['reading']) is int and type(r['observed_us']) is int and type(r['version']) is int for r in result)
