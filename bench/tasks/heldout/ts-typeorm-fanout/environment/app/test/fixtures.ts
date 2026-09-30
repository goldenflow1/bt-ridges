import type { TestContext } from 'node:test';
import { openDatabase } from '../src/database.js';

export async function fixture(t: TestContext) {
  const source = openDatabase(process.env.STAGEPASS_TEST_DATABASE_URL!);
  await source.initialize();
  t.after(async () => { await source.destroy(); });
  await source.query('TRUNCATE ticket_types, events');
  return source;
}
