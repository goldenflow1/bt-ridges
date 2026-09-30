import test from 'node:test';
import assert from 'node:assert/strict';
import { fixture } from './fixtures.js';
import { getCatalog } from '../src/api/catalog.js';
import { enabledTicketKinds } from '../src/repositories/events.js';

test('visible: one published event and editor kinds', async t => {
  const source = await fixture(t);
  await source.query("INSERT INTO events VALUES (1,7,'Matinee','2026-01-01 12:00+00',true)");
  await source.query("INSERT INTO ticket_types VALUES (1,1,'standard',100,true)");
  const result = await getCatalog(source,7,null,0,10);
  assert.equal(result.total,1);
  assert.deepEqual(result.items.map(event => event.id),[1]);
  assert.equal(result.items[0].ticketTypes[0].capacity,100);
  assert.deepEqual(await enabledTicketKinds(source,1),['standard']);
});

test('visible: absent tenant and invalid page', async t => {
  const source = await fixture(t);
  assert.deepEqual(await getCatalog(source,99,null,0,2),{items:[],total:0});
  await assert.rejects(getCatalog(source,7,null,-1,2),RangeError);
});
