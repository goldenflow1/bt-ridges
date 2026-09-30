import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { db, topItems } from '../src/reports.js';
after(async () => { await db.close(); });
export async function reset() {
 await db.command({query:'DROP TABLE IF EXISTS items'});
 await db.command({query:'CREATE TABLE items(tenant String, category String, id UInt32, score Int32, active UInt8) ENGINE=MergeTree ORDER BY (tenant, category, id)'});
}
test('visible: highest scoring item', async () => {
 await reset();
 await db.insert({table:'items',format:'JSONEachRow',values:[{tenant:'a',category:'books',id:1,score:12,active:1},{tenant:'a',category:'books',id:2,score:7,active:1}]});
 assert.deepEqual(await topItems('a',1),[{category:'books',id:1,score:12}]);
});
