import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { db, runningBalances } from '../src/reports.js';
after(async () => { await db.destroy(); });
async function reset() { await db.raw('DROP TABLE IF EXISTS movements'); await db.raw('CREATE TABLE movements(id integer PRIMARY KEY, tenant text NOT NULL, account text NOT NULL, occurred_at bigint NOT NULL, amount bigint NOT NULL)'); }
test('hidden: peers advance one row at a time', async () => {
 await reset();
 await db('movements').insert([{id:30,tenant:'a',account:'cash',occurred_at:10,amount:7},{id:10,tenant:'a',account:'cash',occurred_at:10,amount:3},{id:20,tenant:'a',account:'cash',occurred_at:10,amount:-5},{id:5,tenant:'a',account:'other',occurred_at:10,amount:100}]);
 const rows=await runningBalances('a',0,20);
 assert.deepEqual(rows.map(r=>[r.id,r.total]),[[5,'100'],[10,'3'],[20,'-2'],[30,'5']]);
});
test('hidden: lifetime balance survives display cutoff', async () => {
 await reset();
 await db('movements').insert([{id:9,tenant:'a',account:'cash',occurred_at:-10,amount:'9007199254740993'},{id:2,tenant:'a',account:'cash',occurred_at:10,amount:-3},{id:4,tenant:'a',account:'cash',occurred_at:20,amount:999},{id:3,tenant:'other',account:'cash',occurred_at:0,amount:77}]);
 assert.deepEqual(await runningBalances('a',10,20),[{id:2,account:'cash',amount:'-3',total:'9007199254740990'}]);
 assert.deepEqual(await runningBalances('a',20,20),[]);
 assert.deepEqual(await runningBalances('absent',0,100),[]);
});
test('hidden: independent partitions and repeated amounts', async () => {
 await reset();
 const data=[];
 for(let i=1;i<=45;i++)data.push({id:i,tenant:'a',account:i%2?'odd':'even',occurred_at:Math.floor(i/4),amount:i%3?2:-1});
 data.push({id:900,tenant:'a',account:'odd',occurred_at:1,amount:-7});
 await db('movements').insert(data.reverse());
 const rows=await runningBalances('a',3,10);
 const totals:Record<string,bigint>={};const expected=[];
 for(const r of data.sort((a,b)=>a.occurred_at-b.occurred_at||a.id-b.id)) {totals[r.account]=(totals[r.account]??0n)+BigInt(r.amount);if(r.occurred_at>=3&&r.occurred_at<10)expected.push([r.id,totals[r.account].toString()]);}
 assert.deepEqual(rows.map(r=>[r.id,r.total]),expected);
});
