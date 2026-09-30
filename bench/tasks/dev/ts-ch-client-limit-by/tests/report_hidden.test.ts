import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { db, topItems } from '../src/reports.js';
after(async () => { await db.close(); });
async function reset() { await db.command({query:'DROP TABLE IF EXISTS items'}); await db.command({query:'CREATE TABLE items(tenant String, category String, id UInt32, score Int32, active UInt8) ENGINE=MergeTree ORDER BY (tenant, category, id)'}); }
test('hidden: each category gets its own quota', async () => {
 await reset();
 const values=[];
 for(const category of ['b','a','c'])for(let id=1;id<=4;id++)values.push({tenant:'a',category,id,score:10-id,active:1});
 await db.insert({table:'items',format:'JSONEachRow',values});
 assert.deepEqual((await topItems('a',2)).map(r=>[r.category,r.id]),[['a',1],['a',2],['b',1],['b',2],['c',1],['c',2]]);
 assert.equal((await topItems('a',20)).length,12);
});
test('hidden: cutoff ties choose smaller IDs', async () => {
 await reset();
 await db.insert({table:'items',format:'JSONEachRow',values:[7,2,9,1,5].map(id=>({tenant:'a',category:'ties',id,score:3,active:1}))});
 for(let repeat=0;repeat<3;repeat++)assert.deepEqual((await topItems('a',3)).map(r=>r.id),[1,2,5]);
});
test('hidden: filter eligibility before ranking', async () => {
 await reset();
 await db.insert({table:'items',format:'JSONEachRow',values:[{tenant:'a',category:'x',id:1,score:999,active:0},{tenant:'a',category:'x',id:2,score:-4,active:1},{tenant:'a',category:'x',id:3,score:0,active:1},{tenant:'other',category:'x',id:4,score:999,active:1},{tenant:'a',category:'empty',id:5,score:99,active:0}]});
 assert.deepEqual(await topItems('a',1),[{category:'x',id:3,score:0}]);
 assert.deepEqual(await topItems('a',0),[]);
 assert.deepEqual(await topItems('missing',3),[]);
});
