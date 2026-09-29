import { Prisma, PrismaClient } from "@prisma/client";

export interface CourseCompletion {
  courseId: number;
  code: string;
  title: string;
  enrolled: number;
  completed: number;
  /** Percentage of enrolled learners who completed, 0–100, one decimal place. */
  completionRate: number;
}

export interface InstructorLoad {
  instructorId: number;
  name: string;
  activeCourses: number;
  activeLearners: number;
}

interface CompletionRow {
  course_id: number;
  code: string;
  title: string;
  enrolled: bigint;
  completed: bigint;
  completion_rate: Prisma.Decimal | bigint | number;
}

interface LoadRow {
  instructor_id: number;
  name: string;
  active_courses: bigint;
  active_learners: bigint;
}

/**
 * Completion rate of every course that is not archived.
 *
 * Withdrawn enrollments are ignored. `completionRate` is
 * completed * 100 / enrolled, rounded to one decimal place (halves away from
 * zero); a course without enrollments has a rate of 0. Rows are ordered by
 * rate, highest first, then by course id.
 */
export async function courseCompletionRates(prisma: PrismaClient): Promise<CourseCompletion[]> {
  const rows = await prisma.$queryRaw<CompletionRow[]>`
    SELECT
      c.id AS course_id,
      c.code,
      c.title,
      COUNT(e.id) AS enrolled,
      COUNT(e.completed_at) AS completed,
      COALESCE(COUNT(e.completed_at) * 100 / NULLIF(COUNT(e.id), 0), 0) AS completion_rate
    FROM courses c
    LEFT JOIN enrollments e
      ON e.course_id = c.id
     AND e.status <> 'withdrawn'
    WHERE c.archived_at IS NULL
    GROUP BY c.id, c.code, c.title
    ORDER BY completion_rate DESC, c.id
  `;
  return rows.map((row) => ({
    courseId: row.course_id,
    code: row.code,
    title: row.title,
    enrolled: Number(row.enrolled),
    completed: Number(row.completed),
    completionRate: Number(row.completion_rate),
  }));
}

/** Active (non-archived) courses and distinct active learners per instructor. */
export async function instructorLoad(prisma: PrismaClient): Promise<InstructorLoad[]> {
  const rows = await prisma.$queryRaw<LoadRow[]>`
    SELECT
      i.id AS instructor_id,
      i.name,
      COUNT(DISTINCT c.id) AS active_courses,
      COUNT(DISTINCT e.learner) AS active_learners
    FROM instructors i
    LEFT JOIN courses c
      ON c.instructor_id = i.id
     AND c.archived_at IS NULL
    LEFT JOIN enrollments e
      ON e.course_id = c.id
     AND e.status = 'active'
     AND e.completed_at IS NULL
    GROUP BY i.id, i.name
    ORDER BY i.id
  `;
  return rows.map((row) => ({
    instructorId: row.instructor_id,
    name: row.name,
    activeCourses: Number(row.active_courses),
    activeLearners: Number(row.active_learners),
  }));
}

/** Mark an enrollment as completed. Returns false when it does not exist. */
export async function markCompleted(
  prisma: PrismaClient,
  courseId: number,
  learner: string,
  at: Date = new Date(),
): Promise<boolean> {
  const result = await prisma.enrollment.updateMany({
    where: { courseId, learner, status: "active", completedAt: null },
    data: { completedAt: at },
  });
  return result.count === 1;
}
