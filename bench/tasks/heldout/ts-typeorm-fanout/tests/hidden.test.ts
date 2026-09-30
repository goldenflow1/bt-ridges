import test from 'node:test';
import assert from 'node:assert/strict';
import { fixture } from './fixtures.js';
import { getCatalog } from '../src/api/catalog.js';

test('hidden: totals count matching parents and pages contain complete events', async t => {
  const source = await fixture(t);
  await source.query("INSERT INTO events VALUES (1,7,'A','2026-01-01',true),(2,7,'B','2026-01-02',true),(3,7,'Empty','2026-01-03',true),(4,8,'Other','2026-01-01',true),(5,7,'Draft','2026-01-01',false)");
  await source.query("INSERT INTO ticket_types SELECT n,1,'kind-'||n,10*n,true FROM generate_series(1,8) n");
  await source.query("INSERT INTO ticket_types VALUES (9,2,'standard',0,true),(10,4,'other',1,true),(11,5,'draft',1,true)");
  for (const size of [1,2,5]) {
    const all: number[] = [];
    for (let page=0; page<Math.ceil(3/size); page++) {
      const result=await getCatalog(source,7,null,page,size);
      assert.equal(result.total,3);
      assert.deepEqual(result.items.map(event=>event.id),[1,2,3].slice(page*size,(page+1)*size));
      all.push(...result.items.map(event=>event.id));
      for (const event of result.items) {
        const ids=event.ticketTypes.map(ticket=>ticket.id).sort((a,b)=>a-b);
        assert.deepEqual(ids,event.id===1?[1,2,3,4,5,6,7,8]:event.id===2?[9]:[]);
        assert.ok(event.startsAt instanceof Date);
      }
    }
    assert.deepEqual(all,[1,2,3]);
  }
});

test('hidden: ticket eligibility retains all child types', async t => {
  const source=await fixture(t);
  await source.query("INSERT INTO events VALUES (1,7,'A','2026-01-01',true),(2,7,'Disabled only','2026-01-02',true),(3,7,'B','2026-01-03',true)");
  await source.query("INSERT INTO ticket_types VALUES (1,1,'standard',10,true),(2,1,'vip',20,true),(3,1,'standard',0,false),(4,2,'standard',15,false),(5,3,'standard',30,true)");
  const result=await getCatalog(source,7,'standard',0,10);
  assert.equal(result.total,2);
  assert.deepEqual(result.items.map(event=>event.id),[1,3]);
  assert.deepEqual(result.items[0].ticketTypes.map(ticket=>[ticket.id,ticket.kind,ticket.capacity,ticket.enabled]).sort((a,b)=>Number(a[0])-Number(b[0])),[[1,'standard',10,true],[2,'vip',20,true],[3,'standard',0,false]]);
  assert.deepEqual(await getCatalog(source,7,"unknown'kind",0,2),{items:[],total:0});
});

test('hidden: stable ties, empty pages, fresh data and bounded work', async t => {
  const source=await fixture(t);
  for (const id of [40,10,30,20]) {
    await source.query('INSERT INTO events VALUES ($1,7,$2,$3,true)',[id,'Event '+id,'2026-01-01T12:00:00.123Z']);
    for(let n=0;n<3;n++) await source.query('INSERT INTO ticket_types VALUES ($1,$2,$3,5,true)',[id*10+n,id,'kind-'+n]);
  }
  const create=source.createQueryRunner.bind(source);
  let calls=0;
  source.createQueryRunner=(mode) => {
    const runner=create(mode);
    const query=runner.query.bind(runner);
    runner.query=async (sql: string,parameters?: any[],structured?: true): Promise<any> => { calls++; return structured ? query(sql,parameters,true) : query(sql,parameters); };
    return runner;
  };
  for(let repeat=0;repeat<3;repeat++) {
    for(let page=0;page<2;page++) {
      calls=0;
      const result=await getCatalog(source,7,null,page,2);
      assert.deepEqual(result.items.map(event=>event.id),[10,20,30,40].slice(page*2,page*2+2));
      assert.equal(result.total,4);
      assert.ok(calls>=1 && calls<=3,`queries=${calls}`);
    }
  }
  const empty=await getCatalog(source,7,null,99,2);
  assert.equal(empty.total,4);
  assert.deepEqual(empty.items,[]);
  await source.query("INSERT INTO events VALUES (5,7,'New','2025-12-01',true)");
  const fresh=await getCatalog(source,7,null,0,2);
  assert.equal(fresh.total,5);
  assert.deepEqual(fresh.items.map(event=>event.id),[5,10]);
});
