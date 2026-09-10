import { useState } from 'react'
import { ApiError, fetchSchedule } from './api'
import type { ScheduleResponse, Solver } from './types'

interface SchedulePanelProps {
  program: string
  completedCourses: string[]
}

export function SchedulePanel({ program, completedCourses }: SchedulePanelProps) {
  const [solver, setSolver] = useState<Solver>('greedy')
  const [maxUnits, setMaxUnits] = useState(18)
  const [result, setResult] = useState<ScheduleResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    try {
      const response = await fetchSchedule(program, completedCourses, maxUnits, solver)
      setResult(response)
    } catch (err) {
      setResult(null)
      setError(err instanceof ApiError ? err.message : 'Could not generate a plan.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="schedule-panel">
      <h2 className="schedule-panel__title">Generate my plan</h2>
      <div className="schedule-panel__controls">
        <label className="schedule-panel__field">
          Max units/term
          <input
            type="number"
            min={1}
            step={0.5}
            value={maxUnits}
            onChange={(e) => setMaxUnits(Number(e.target.value))}
          />
        </label>
        <label className="schedule-panel__field">
          Solver
          <select value={solver} onChange={(e) => setSolver(e.target.value as Solver)}>
            <option value="greedy">Greedy (fast)</option>
            <option value="optimal">Optimal (may take up to 30s)</option>
          </select>
        </label>
        <button type="button" className="button-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating...' : 'Generate'}
        </button>
      </div>

      {error && <p className="schedule-panel__error">{error}</p>}

      {result && (
        <div className="schedule-panel__result">
          <p className="schedule-panel__summary">
            {result.termCount} term(s) via the {result.solver} solver.
          </p>
          <ol className="schedule-panel__terms">
            {result.terms.map((term) => (
              <li key={term.termNumber} className="schedule-panel__term">
                <span className="schedule-panel__term-header">
                  Term {term.termNumber} (T{term.calendarTerm}) -- {term.totalUnits}u
                </span>
                <span className="schedule-panel__term-courses">
                  {term.courses.map((c) => c.code).join(', ')}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
