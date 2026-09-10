# CC-Flow frontend

Vite + React + TypeScript. Lets a student check off completed courses for a
CCS program and see a color-coded prerequisite graph (React Flow + dagre),
plus generate a term-by-term plan via the backend's greedy/optimal solvers.

## Local development

From the repo root, `npm run dev` starts this alongside the backend. To run
just this piece:

```bash
npm install
cp .env.example .env   # sets VITE_API_URL for the separately-running backend
npm run dev
```

`backend/` must be running separately (see `backend/README.md` if present,
or the repo root `ROADMAP.md`) — this app expects it at `http://localhost:8000`
by default, overridable via `VITE_API_URL` in `.env`.

## Production (Vercel)

Deployed alongside `backend/` as a
[Vercel Services](https://vercel.com/docs/services) monorepo — see
`vercel.json` at the repo root. In production, frontend and backend share one
domain, so `VITE_API_URL` is left unset and requests go to the same-origin
`/api/...` path instead (see `src/api.ts`).

## Code layout

- `App.tsx` — top-level composition: program picker, health check, layout.
- `CourseForm.tsx` — the completed/retake checklist, grouped by canonical year.
- `CourseGraph.tsx` — the prerequisite graph (React Flow + dagre auto-layout).
- `SchedulePanel.tsx` — calls the backend's schedule-generation endpoint.
- `deriveStatus.ts` — client-side status derivation (completed / eligible-now
  / locked / needs-retake) from the catalog + the user's marks.
- `useCompletedCourses.ts` — `localStorage`-backed persistence, per program.
- `api.ts` / `types.ts` — the backend API client and its response shapes.
