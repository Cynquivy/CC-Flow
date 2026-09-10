export type RequisiteType = 'hard' | 'soft' | 'coreq' | 'exemption'

export interface CourseRequisite {
  type: RequisiteType
  code: string
}

export interface CatalogCourse {
  code: string
  name: string
  units: number
  isZeroCredit: boolean
  yearRaw: string | null
  yearNumber: number | null
  term: number | null
  requisites: CourseRequisite[]
}

export interface ProgramCatalog {
  program: string
  yearDataReliable: boolean
  courses: CatalogCourse[]
}

// Per-course status the student has set manually. Anything not in this map is
// implicitly "not started" -- its displayed status (eligible-now vs locked) is
// derived, not stored.
export type CourseMark = 'completed' | 'needs-retake'

export type CourseMarks = Record<string, CourseMark>

// The derived 4-state status used for graph coloring, per the M9 design: only
// `hard` prerequisites gate eligibility -- coreq/soft/exemption don't block it.
export type CourseStatus = 'completed' | 'eligible-now' | 'locked' | 'needs-retake'

export interface ScheduledCourse {
  code: string
  name: string
  units: number
}

export interface TermPlan {
  termNumber: number
  calendarTerm: number
  courses: ScheduledCourse[]
  totalUnits: number
}

export type Solver = 'greedy' | 'optimal'

export interface ScheduleResponse {
  program: string
  solver: Solver
  termCount: number
  terms: TermPlan[]
}
