import type { DataSource } from 'typeorm';
import { catalogPage } from '../services/catalog.js';

export async function getCatalog(source: DataSource, tenant: number, kind: string | null, page: number, size: number) {
  if (!Number.isInteger(page) || page < 0 || !Number.isInteger(size) || size < 1 || size > 100) throw new RangeError('invalid page');
  return catalogPage(source, tenant, kind, page, size);
}
