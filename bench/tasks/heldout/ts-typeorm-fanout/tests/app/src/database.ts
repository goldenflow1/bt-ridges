import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { EventSchema, TicketTypeSchema } from './entities.js';

export function openDatabase(url = process.env.STAGEPASS_DATABASE_URL!): DataSource {
  return new DataSource({ type: 'postgres', url, entities: [EventSchema, TicketTypeSchema], synchronize: false, logging: false });
}
