import { createClient } from '@clickhouse/client';

export const db = createClient({ url: 'http://clickhouse:8123', username: 'meterline', password: 'meterline-app-4e2a9c17', database: 'meterline_test' });
export interface RankedItem { category: string; id: number; score: number }

/** Return up to n eligible items per category, with deterministic ties. */
export async function topItems(tenant: string, n: number): Promise<RankedItem[]> {
  const result = await db.query({ query: `SELECT category, id, score FROM items WHERE tenant = {tenant:String} AND active = 1 ORDER BY category, score DESC, id ASC LIMIT 1`, query_params: { tenant, n }, format: 'JSONEachRow' });
  return result.json<RankedItem>();
}
