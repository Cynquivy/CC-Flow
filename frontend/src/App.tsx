import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { ApiError, fetchHealth, fetchProgramCatalog, fetchPrograms } from './api'
import { CourseForm } from './CourseForm'
import { CourseGraph } from './CourseGraph'
import { deriveStatuses } from './deriveStatus'
import { SchedulePanel } from './SchedulePanel'
import type { ProgramCatalog } from './types'
import { useCompletedCourses } from './useCompletedCourses'

type HealthResponse = { status: string; db: string }

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [programs, setPrograms] = useState<string[]>([])
  const [program, setProgram] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<ProgramCatalog | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [loadingCatalog, setLoadingCatalog] = useState(false)

  const { marks, setMark } = useCompletedCourses(program)

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealthError('Could not reach backend'))
  }, [])

  useEffect(() => {
    fetchPrograms()
      .then((list) => {
        setPrograms(list)
        setProgram((current) => current ?? list[0] ?? null)
      })
      .catch(() => setPrograms([]))
  }, [])

  useEffect(() => {
    if (!program) return
    setLoadingCatalog(true)
    setCatalogError(null)
    fetchProgramCatalog(program)
      .then(setCatalog)
      .catch((err) => {
        setCatalog(null)
        setCatalogError(err instanceof ApiError ? err.message : 'Could not load this program.')
      })
      .finally(() => setLoadingCatalog(false))
  }, [program])

  const statuses = useMemo(
    () => (catalog ? deriveStatuses(catalog.courses, marks) : {}),
    [catalog, marks],
  )

  const completedCodes = useMemo(
    () => Object.entries(marks).filter(([, m]) => m === 'completed').map(([code]) => code),
    [marks],
  )

  return (
    <main>
      <header className="app-header">
        <h1>CC-Flow</h1>
        <p className="app-header__status">
          Backend: {healthError ? healthError : health ? `${health.status} (db: ${health.db})` : 'checking...'}
        </p>
        <label className="app-header__program-picker">
          Program
          <select value={program ?? ''} onChange={(e) => setProgram(e.target.value)}>
            {programs.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </header>

      {loadingCatalog && <p className="app-loading">Loading {program}...</p>}
      {catalogError && <p className="app-error">{catalogError}</p>}

      {catalog && (
        <>
          <section className="app-layout">
            <CourseForm
              courses={catalog.courses}
              yearDataReliable={catalog.yearDataReliable}
              marks={marks}
              onSetMark={setMark}
            />
            <CourseGraph key={catalog.program} courses={catalog.courses} statuses={statuses} />
          </section>

          <SchedulePanel program={catalog.program} completedCourses={completedCodes} />
        </>
      )}
    </main>
  )
}

export default App
