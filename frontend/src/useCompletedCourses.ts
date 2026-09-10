import { useCallback, useState } from 'react'
import type { CourseMark, CourseMarks } from './types'

function storageKey(program: string): string {
  return `cc-flow:marks:${program}`
}

function readMarks(program: string): CourseMarks {
  try {
    const raw = localStorage.getItem(storageKey(program))
    return raw ? (JSON.parse(raw) as CourseMarks) : {}
  } catch {
    return {}
  }
}

// Per-program, per-browser persistence for the student's checked-off/failed
// courses -- there's no login and M8 is stateless, so this is the only place
// this state lives. Losing it on refresh would be a real, easy-to-hit
// annoyance for no benefit.
export function useCompletedCourses(program: string | null) {
  const [marks, setMarks] = useState<CourseMarks>({})
  // Reset when `program` changes, without an effect -- adjusting state
  // during render (guarded by comparing against the last-seen prop) is
  // React's own documented alternative for "derive/reset state from a
  // changed prop," rather than a useEffect that just re-triggers a render.
  const [loadedProgram, setLoadedProgram] = useState(program)
  if (program !== loadedProgram) {
    setLoadedProgram(program)
    setMarks(program ? readMarks(program) : {})
  }

  const setMark = useCallback(
    (code: string, mark: CourseMark | null) => {
      if (!program) return
      setMarks((prev) => {
        const next = { ...prev }
        if (mark === null) {
          delete next[code]
        } else {
          next[code] = mark
        }
        try {
          localStorage.setItem(storageKey(program), JSON.stringify(next))
        } catch {
          // best-effort persistence only -- a private window or full quota
          // shouldn't break the app, just the "survives refresh" convenience
        }
        return next
      })
    },
    [program],
  )

  return { marks, setMark }
}
