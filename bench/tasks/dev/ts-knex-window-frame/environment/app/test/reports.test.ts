import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { db, runningBalances } from '../src/reports.js';
after(async () => { await db.destroy(); });
export async function reset() {
 await db.raw('DROP TABLE IF EXISTS movements');
 await db.raw('CREATE TABLE movements(id integer PRIMARY KEY, tenant text NOT NULL, account text NOT NULL, occurred_at bigint NOT NULL, amount bigint NOT NULL)');
}
test('visible: chronological running total', async () => {
 await reset();
 await db('movements').insert([{id:1,tenant:'a',account:'cash',occurred_at:10,amount:5},{id:2,tenant:'a',account:'cash',occurred_at:20,amount:-2}]);
 assert.deepEqual(await runningBalances('a',0,30),[{id:1,account:'cash',amount:'5',total:'5'},{id:2,account:'cash',amount:'-2',total:'3'}]);
});
