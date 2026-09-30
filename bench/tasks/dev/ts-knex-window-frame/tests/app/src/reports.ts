import knex from 'knex';

export const db = knex({ client: 'pg', connection: process.env.AUDITFEED_TEST_DATABASE_URL ?? 'postgres://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_test?sslmode=disable' });
export interface LedgerRow { id: number; account: string; amount: string; total: string }

/** Return lifetime running balances for visible movements, in chronological ID order. */
export async function runningBalances(tenant: string, start: number, end: number): Promise<LedgerRow[]> {
  const result = await db.raw(`SELECT id, account, amount::text, SUM(amount) OVER (PARTITION BY account ORDER BY occurred_at)::text AS total FROM movements WHERE tenant = ? AND occurred_at >= ? AND occurred_at < ? ORDER BY occurred_at, id`, [tenant, start, end]);
  return result.rows;
}
