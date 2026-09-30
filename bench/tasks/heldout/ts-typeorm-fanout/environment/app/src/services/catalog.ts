import type { DataSource } from 'typeorm';
import { listEvents } from '../repositories/events.js';

export async function catalogPage(source: DataSource, tenant: number, kind: string | null, page: number, size: number) {
  return listEvents(source, tenant, kind, page * size, size);
}
