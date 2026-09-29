import { readFileSync } from "node:fs";
import { PrismaClient } from "@prisma/client";
import { createClient } from "../src/db.js";

let client: PrismaClient | undefined;

/** Client for the scratch test database, with the schema applied. */
export async function testClient(): Promise<PrismaClient> {
  if (!client) {
    client = createClient("COURSEBOARD_TEST_DATABASE_URL");
    const ddl = readFileSync(new URL("../migrations/001_init.sql", import.meta.url), "utf8");
    for (const statement of ddl.split(";").map((s) => s.trim()).filter(Boolean)) {
      await client.$executeRawUnsafe(statement);
    }
  }
  return client;
}

export async function reset(prisma: PrismaClient): Promise<void> {
  await prisma.$executeRawUnsafe(
    "TRUNCATE enrollments, courses, instructors RESTART IDENTITY CASCADE",
  );
}

export async function closeClient(): Promise<void> {
  await client?.$disconnect();
  client = undefined;
}

let learnerSeq = 0;

/** Create a course with `enrolled` active enrollments of which `completed` are complete. */
export async function course(
  prisma: PrismaClient,
  code: string,
  enrolled: number,
  completed: number,
  options: { withdrawn?: number; archived?: boolean; instructor?: string } = {},
): Promise<number> {
  const instructor = await prisma.instructor.create({ data: { name: options.instructor ?? `Tutor ${code}` } });
  const created = await prisma.course.create({
    data: {
      code,
      title: `Course ${code}`,
      instructorId: instructor.id,
      archivedAt: options.archived ? new Date("2026-01-01T00:00:00Z") : null,
    },
  });
  const rows = [];
  for (let i = 0; i < enrolled; i++) {
    rows.push({
      courseId: created.id,
      learner: `learner-${++learnerSeq}`,
      completedAt: i < completed ? new Date("2026-03-01T12:00:00Z") : null,
    });
  }
  for (let i = 0; i < (options.withdrawn ?? 0); i++) {
    rows.push({ courseId: created.id, learner: `learner-${++learnerSeq}`, status: "withdrawn" });
  }
  if (rows.length) {
    await prisma.enrollment.createMany({ data: rows });
  }
  return created.id;
}
