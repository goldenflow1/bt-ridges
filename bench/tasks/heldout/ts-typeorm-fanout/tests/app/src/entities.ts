import { EntitySchema } from 'typeorm';

export interface VenueEvent {
  id: number; tenantId: number; title: string; startsAt: Date; published: boolean; ticketTypes: TicketType[];
}
export interface TicketType {
  id: number; eventId: number; kind: string; capacity: number; enabled: boolean; event?: VenueEvent;
}
export const EventSchema = new EntitySchema<VenueEvent>({
  name: 'VenueEvent', tableName: 'events',
  columns: { id: { type: Number, primary: true }, tenantId: { type: Number, name: 'tenant_id' },
    title: { type: String }, startsAt: { type: 'timestamptz', precision: 3, name: 'starts_at' }, published: { type: Boolean } },
  relations: { ticketTypes: { type: 'one-to-many', target: 'TicketType', inverseSide: 'event' } },
});
export const TicketTypeSchema = new EntitySchema<TicketType>({
  name: 'TicketType', tableName: 'ticket_types',
  columns: { id: { type: Number, primary: true }, eventId: { type: Number, name: 'event_id' },
    kind: { type: String }, capacity: { type: Number }, enabled: { type: Boolean } },
  relations: { event: { type: 'many-to-one', target: 'VenueEvent', joinColumn: { name: 'event_id' }, inverseSide: 'ticketTypes' } },
});
