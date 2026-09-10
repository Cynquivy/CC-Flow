import type { CatalogCourse, CourseMarks, CourseStatus } from './types'

// Only `hard` prerequisites gate eligibility -- `coreq`/`soft`/`exemption`
// are informational (same convention as the M6/M7 schedulers). A hard
// prereq outside this program's own catalog can't happen -- the backend
// already excludes unresolved/external requisite edges -- but the check
// stays defensive rather than assuming that guarantee forever.
export function deriveStatuses(
  courses: CatalogCourse[],
  marks: CourseMarks,
): Record<string, CourseStatus> {
  const knownCodes = new Set(courses.map((c) => c.code))
  const statuses: Record<string, CourseStatus> = {}

  for (const course of courses) {
    const mark = marks[course.code]
    if (mark === 'completed' || mark === 'needs-retake') {
      statuses[course.code] = mark
      continue
    }
    const hardPrereqs = course.requisites.filter((r) => r.type === 'hard')
    const allSatisfied = hardPrereqs.every(
      (r) => marks[r.code] === 'completed' || !knownCodes.has(r.code),
    )
    statuses[course.code] = allSatisfied ? 'eligible-now' : 'locked'
  }

  return statuses
}
