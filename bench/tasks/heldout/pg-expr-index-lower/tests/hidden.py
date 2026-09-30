import hashlib
import json
from io import StringIO

from django.core.management import call_command
from django.db import connection

from library.api import identify_member
from library.repositories.members import email_lookup

INDEX='library_member_lower_email'


def fingerprint():
    with connection.cursor() as c:
        c.execute("SELECT count(*),sum(id),md5(string_agg(id::text||':'||branch_id::text||':'||email||':'||display_name||':'||active::text,',' ORDER BY id)) FROM library_member")
        data=c.fetchone()
        c.execute("SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_name='library_member' ORDER BY ordinal_position")
        columns=c.fetchall()
        c.execute("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='library_member'::regclass ORDER BY conname")
        constraints=c.fetchall()
    return hashlib.sha256(json.dumps([data,columns,constraints],default=str).encode()).hexdigest()


def plan_for(branch,email):
    sql,args=email_lookup(branch,email).query.sql_with_params()
    with connection.cursor() as c:
        c.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql,args)
        plan=c.fetchone()[0][0]['Plan']
    def indexes(node):
        return ([node['Index Name']] if 'Index Name' in node else []) + [i for child in node.get('Plans',[]) for i in indexes(child)]
    return plan.get('Shared Hit Blocks',0)+plan.get('Shared Read Blocks',0),indexes(plan)


def test_real_lookup_index_work_and_reversible_state(db):
    call_command('migrate','library','0001_initial',verbosity=0)
    with connection.cursor() as c:
        c.execute("INSERT INTO library_member(id,branch_id,email,display_name,active) SELECT n,mod(n,5)+1,'Reader'||n||'@Library.EXAMPLE','Member '||n,true FROM generate_series(1,100000) n")
        c.execute('ANALYZE library_member')
        c.execute("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='library_member' ORDER BY indexname")
        original_indexes=c.fetchall()
    targets=[(3,'READER17@library.example'),(3,'reader50007@LIBRARY.EXAMPLE'),(3,'reader99997@library.example'),(3,'absent@library.example')]
    expected=[identify_member(branch,email) for branch,email in targets]
    before=[plan_for(branch,email)[0] for branch,email in targets]
    original=fingerprint()
    assert min(before)>640
    call_command('migrate',verbosity=0)
    call_command('makemigrations',check=True,dry_run=True,stdout=StringIO())
    with connection.cursor() as c:
        c.execute('ANALYZE library_member')
    for (branch,email),old,result in zip(targets,before,expected):
        work,indexes=plan_for(branch,email)
        assert INDEX in indexes, f'lookup did not use expression index: {indexes}'
        assert work<=64 and work*10<=old, f'work={work}, baseline={old}'
        assert identify_member(branch,email)==result
    assert fingerprint()==original
    with connection.cursor() as c:
        c.execute("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='library_member' ORDER BY indexname")
        current=c.fetchall()
    assert [r for r in current if r[0]!=INDEX]==original_indexes
    assert len(current)==len(original_indexes)+1
    call_command('migrate',verbosity=0)
    assert fingerprint()==original
    call_command('migrate','library','0001_initial',verbosity=0)
    with connection.cursor() as c:
        c.execute("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='library_member' ORDER BY indexname")
        assert c.fetchall()==original_indexes
    assert fingerprint()==original
    assert [identify_member(branch,email) for branch,email in targets]==expected
    call_command('migrate',verbosity=0)
    call_command('makemigrations',check=True,dry_run=True,stdout=StringIO())
    for branch,email in targets:
        assert INDEX in plan_for(branch,email)[1]
