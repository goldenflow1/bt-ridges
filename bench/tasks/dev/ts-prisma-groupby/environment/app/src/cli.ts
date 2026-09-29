import { createClient } from "./db.js";
import { courseCompletionRates, instructorLoad } from "./reports.js";

async function main(): Promise<void> {
  const [command = "completion"] = process.argv.slice(2);
  const prisma = createClient();
  try {
    if (command === "completion") {
      console.log(`${"code".padEnd(8)} ${"title".padEnd(28)} ${"enrolled".padStart(8)} ${"done".padStart(5)} ${"rate".padStart(6)}`);
      for (const row of await courseCompletionRates(prisma)) {
        console.log(
          `${row.code.padEnd(8)} ${row.title.padEnd(28)} ${String(row.enrolled).padStart(8)} ` +
            `${String(row.completed).padStart(5)} ${row.completionRate.toFixed(1).padStart(6)}`,
        );
      }
    } else if (command === "instructors") {
      for (const row of await instructorLoad(prisma)) {
        console.log(`${row.name.padEnd(20)} ${row.activeCourses} courses, ${row.activeLearners} learners`);
      }
    } else {
      throw new Error(`unknown command: ${command}`);
    }
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
