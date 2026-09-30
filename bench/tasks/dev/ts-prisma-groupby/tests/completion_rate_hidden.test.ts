import assert from "node:assert/strict";
import { after, beforeEach, test } from "node:test";
import type { PrismaClient } from "@prisma/client";
import { courseCompletionRates } from "../src/reports.js";
import { closeClient, course, reset, testClient } from "./helpers.js";

let prisma: PrismaClient;

beforeEach(async () => {
  prisma = await testClient();
  await reset(prisma);
});

after(closeClient);

async function rates(): Promise<Map<number, number>> {
  return new Map((await courseCompletionRates(prisma)).map((r) => [r.courseId, r.completionRate]));
}

test("hidden: fractional rates keep one decimal", async () => {
  const twoThirds = await course(prisma, "LAT101", 3, 2);
  const oneThird = await course(prisma, "LAT102", 3, 1);
  const oneSixth = await course(prisma, "LAT103", 6, 1);
  const fiveSevenths = await course(prisma, "LAT104", 7, 5);

  const got = await rates();

  assert.equal(got.get(twoThirds), 66.7);
  assert.equal(got.get(oneThird), 33.3);
  assert.equal(got.get(oneSixth), 16.7);
  assert.equal(got.get(fiveSevenths), 71.4);
});

test("hidden: halves round away from zero", async () => {
  const a = await course(prisma, "OCE201", 80, 23);
  const b = await course(prisma, "OCE202", 16, 1);
  const c = await course(prisma, "OCE203", 8, 1);
  const d = await course(prisma, "OCE204", 40, 1);

  const got = await rates();

  assert.equal(got.get(a), 28.8);
  assert.equal(got.get(b), 6.3);
  assert.equal(got.get(c), 12.5);
  assert.equal(got.get(d), 2.5);
});

test("hidden: ordering uses the rounded rate, then id", async () => {
  const sixtySix = await course(prisma, "SOC310", 50, 33);
  const twoThirds = await course(prisma, "SOC311", 3, 2);
  const nearlyAll = await course(prisma, "SOC312", 200, 199);
  const all = await course(prisma, "SOC313", 1, 1);
  const none = await course(prisma, "SOC314", 0, 0);

  const rows = await courseCompletionRates(prisma);

  assert.deepEqual(
    rows.map((r) => [r.courseId, r.completionRate]),
    [
      [all, 100],
      [nearlyAll, 99.5],
      [twoThirds, 66.7],
      [sixtySix, 66],
      [none, 0],
    ],
  );
});

test("hidden: withdrawn learners do not dilute fractional rates", async () => {
  const id = await course(prisma, "ECO120", 3, 1, { withdrawn: 2 });
  const archived = await course(prisma, "ECO121", 3, 2, { archived: true });

  const got = await rates();

  assert.equal(got.get(id), 33.3);
  assert.equal(got.has(archived), false);
});

test("hidden: large cohorts and tiny fractions", async () => {
  // Created first so it has the lower id: 1/1500 and 1/1000 both round to 0.1, so "rounded rate, then id"
  // puts it first, while sorting by the unrounded rate would put the 1/1000 course first.
  const tiny = await course(prisma, "CS1003", 1500, 1);
  const oneInThousand = await course(prisma, "CS1000", 1000, 1);
  const almost = await course(prisma, "CS1001", 1000, 999);
  const nothing = await course(prisma, "CS1002", 1000, 0);

  const rows = await courseCompletionRates(prisma);
  const got = new Map(rows.map((r) => [r.courseId, r]));

  assert.equal(got.get(oneInThousand)?.completionRate, 0.1);
  assert.equal(got.get(almost)?.completionRate, 99.9);
  assert.equal(got.get(nothing)?.completionRate, 0);
  assert.equal(got.get(tiny)?.completionRate, 0.1);
  assert.deepEqual(
    rows.filter((r) => r.courseId === tiny || r.courseId === oneInThousand).map((r) => r.courseId),
    [tiny, oneInThousand],
    "equal rounded rates are ordered by course id",
  );
  for (const row of rows) {
    assert.equal(typeof row.completionRate, "number");
    assert.ok(Number.isFinite(row.completionRate));
    assert.equal(typeof row.enrolled, "number");
  }
});
