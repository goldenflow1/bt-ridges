import assert from "node:assert/strict";
import { courseCompletionRates } from "../src/reports.js";
import { closeClient, course, reset, testClient } from "./helpers.js";
async function main() {
 const prisma = await testClient();
 await reset(prisma);
 const first = await course(prisma, "ROUND_A", 1500, 1);
 const second = await course(prisma, "ROUND_B", 1000, 1);
 const rows = await courseCompletionRates(prisma);
 console.log(JSON.stringify({expectedIds:[first, second], actual:rows.map(r=>[r.courseId,r.completionRate])}));
 assert.deepEqual(rows.map(r=>r.courseId), [first, second]);
}
main().finally(closeClient);
