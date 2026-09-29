import assert from "node:assert/strict";
import { after, beforeEach, test } from "node:test";
import type { PrismaClient } from "@prisma/client";
import { courseCompletionRates, instructorLoad, markCompleted } from "../src/reports.js";
import { closeClient, course, reset, testClient } from "./helpers.js";

let prisma: PrismaClient;

beforeEach(async () => {
  prisma = await testClient();
  await reset(prisma);
});

after(closeClient);

test("completion rate per course", async () => {
  const a = await course(prisma, "GEO101", 4, 3);
  const b = await course(prisma, "BIO110", 2, 1);

  const rows = await courseCompletionRates(prisma);

  assert.deepEqual(
    rows.map((r) => [r.courseId, r.enrolled, r.completed, r.completionRate]),
    [
      [a, 4, 3, 75],
      [b, 2, 1, 50],
    ],
  );
});

test("course without enrollments has rate zero", async () => {
  const full = await course(prisma, "ART200", 5, 5);
  const empty = await course(prisma, "ART201", 0, 0);

  const rows = await courseCompletionRates(prisma);

  assert.deepEqual(
    rows.map((r) => [r.courseId, r.completionRate]),
    [
      [full, 100],
      [empty, 0],
    ],
  );
  assert.equal(typeof rows[1].completionRate, "number");
});

test("withdrawn enrollments are ignored", async () => {
  const id = await course(prisma, "CHE150", 4, 2, { withdrawn: 3 });

  const [row] = await courseCompletionRates(prisma);

  assert.equal(row.courseId, id);
  assert.equal(row.enrolled, 4);
  assert.equal(row.completionRate, 50);
});

test("archived courses are left out", async () => {
  const live = await course(prisma, "HIS300", 4, 1);
  await course(prisma, "HIS299", 4, 4, { archived: true });

  const rows = await courseCompletionRates(prisma);

  assert.deepEqual(rows.map((r) => r.courseId), [live]);
  assert.equal(rows[0].completionRate, 25);
});

test("equal rates are ordered by course id", async () => {
  const first = await course(prisma, "MAT210", 2, 1);
  const second = await course(prisma, "MAT211", 4, 2);
  const top = await course(prisma, "MAT212", 1, 1);

  const rows = await courseCompletionRates(prisma);

  assert.deepEqual(rows.map((r) => r.courseId), [top, first, second]);
});

test("instructor load counts active learners", async () => {
  await course(prisma, "PHY100", 3, 1, { instructor: "Noor Haddad" });

  const [row] = await instructorLoad(prisma);

  assert.equal(row.name, "Noor Haddad");
  assert.equal(row.activeCourses, 1);
  assert.equal(row.activeLearners, 2);
});

test("markCompleted completes an active enrollment once", async () => {
  const id = await course(prisma, "PHY101", 1, 0);
  const learner = (await prisma.enrollment.findFirstOrThrow({ where: { courseId: id } })).learner;

  assert.equal(await markCompleted(prisma, id, learner), true);
  assert.equal(await markCompleted(prisma, id, learner), false);
  const [row] = await courseCompletionRates(prisma);
  assert.equal(row.completionRate, 100);
});
