import { useMemo, useState } from 'react'
import type { CatalogCourse, CourseMarks } from './types'

interface CourseFormProps {
  courses: CatalogCourse[]
  yearDataReliable: boolean
  marks: CourseMarks
  onSetMark: (code: string, mark: 'completed' | 'needs-retake' | null) => void
}

function groupByYear(courses: CatalogCourse[]): Map<number | 'unknown', CatalogCourse[]> {
  const groups = new Map<number | 'unknown', CatalogCourse[]>()
  for (const course of courses) {
    const key = course.yearNumber ?? 'unknown'
    const list = groups.get(key) ?? []
    list.push(course)
    groups.set(key, list)
  }
  return new Map([...groups.entries()].sort((a, b) => {
    if (a[0] === 'unknown') return 1
    if (b[0] === 'unknown') return -1
    return a[0] - b[0]
  }))
}

export function CourseForm({ courses, yearDataReliable, marks, onSetMark }: CourseFormProps) {
  const [filter, setFilter] = useState('')

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return courses
    return courses.filter(
      (c) => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
    )
  }, [courses, filter])

  const grouped = useMemo(() => groupByYear(filtered), [filtered])

  return (
    <div className="course-form">
      {!yearDataReliable && (
        <p className="course-form__warning">
          This program's source data doesn't reliably distinguish all years -- some courses may
          be grouped under the wrong year below, or under "Unknown year."
        </p>
      )}
      <input
        className="course-form__filter"
        type="text"
        placeholder="Filter by code or name..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="course-form__list">
        {[...grouped.entries()].map(([year, group]) => (
          <div key={year} className="course-form__group">
            <h3 className="course-form__group-title">
              {year === 'unknown' ? 'Unknown year' : `Year ${year}`}
            </h3>
            {group.map((course) => {
              const mark = marks[course.code]
              return (
                <div key={course.code} className="course-row">
                  <div className="course-row__info">
                    <span className="course-row__code">{course.code}</span>
                    <span className="course-row__name">{course.name || '(untitled)'}</span>
                    <span className="course-row__units">{course.units}u</span>
                  </div>
                  <div className="course-row__actions">
                    <button
                      type="button"
                      className={`pill-toggle pill-toggle--done${mark === 'completed' ? ' pill-toggle--active' : ''}`}
                      onClick={() => onSetMark(course.code, mark === 'completed' ? null : 'completed')}
                    >
                      Done
                    </button>
                    <button
                      type="button"
                      className={`pill-toggle pill-toggle--retake${mark === 'needs-retake' ? ' pill-toggle--active' : ''}`}
                      onClick={() => onSetMark(course.code, mark === 'needs-retake' ? null : 'needs-retake')}
                    >
                      Retake
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
