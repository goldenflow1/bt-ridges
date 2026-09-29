import { PrismaClient } from "@prisma/client";

/** Create a client for the database named by `envVar` (defaults to the app database). */
export function createClient(envVar = "COURSEBOARD_DATABASE_URL"): PrismaClient {
  const url = process.env[envVar];
  if (!url) {
    throw new Error(`${envVar} is not set`);
  }
  return new PrismaClient({ datasources: { db: { url } } });
}
