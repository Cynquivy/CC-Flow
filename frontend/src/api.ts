import type { ProgramCatalog, ScheduleResponse, Solver } from './types'

// On Vercel, frontend and backend share one domain (see vercel.json's
// services/rewrites), so the default is a same-origin relative path. Local
// dev runs two separate servers (Vite on 5173, uvicorn on 8000), so
// frontend/.env sets VITE_API_URL=http://localhost:8000 to cross that gap.
// Either way, every backend route lives under /api.
const API_BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : res.statusText
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export function fetchHealth(): Promise<{ status: string; db: string }> {
  return request('/health')
}

export function fetchPrograms(): Promise<string[]> {
  return request('/programs')
}

export function fetchProgramCatalog(program: string): Promise<ProgramCatalog> {
  return request(`/programs/${encodeURIComponent(program)}/courses`)
}

export function fetchSchedule(
  targetProgram: string,
  completedCourses: string[],
  maxUnitsPerTerm: number,
  solver: Solver,
): Promise<ScheduleResponse> {
  return request('/schedule', {
    method: 'POST',
    body: JSON.stringify({
      targetProgram,
      completedCourses,
      maxUnitsPerTerm,
      solver,
    }),
  })
}
