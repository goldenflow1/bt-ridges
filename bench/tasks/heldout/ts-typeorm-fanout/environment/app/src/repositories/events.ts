import type { DataSource } from 'typeorm';
import { EventSchema, TicketTypeSchema, type VenueEvent } from '../entities.js';

export interface EventPage { items: VenueEvent[]; total: number }

/** Load one page of published events and their complete ticket-type collections. */
export async function listEvents(source: DataSource, tenant: number, kind: string | null, offset: number, limit: number): Promise<EventPage> {
  const query = source.getRepository(EventSchema).createQueryBuilder('event')
    .leftJoinAndSelect('event.ticketTypes', 'ticket')
    .where('event.tenantId = :tenant', { tenant }).andWhere('event.published = true');
  if (kind !== null) query.andWhere('ticket.kind = :kind AND ticket.enabled = true', { kind });
  query.orderBy('event.startsAt', 'ASC').limit(limit).offset(offset);
  const total = (await query.clone().limit(undefined).offset(undefined).getRawMany()).length;
  return { items: await query.getMany(), total };
}

export async function enabledTicketKinds(source: DataSource, eventId: number): Promise<string[]> {
  const tickets = await source.getRepository(TicketTypeSchema).find({ where: { eventId, enabled: true }, order: { id: 'ASC' } });
  return tickets.map(ticket => ticket.kind);
}
