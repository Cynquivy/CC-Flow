# CCS Curriculum Planner — Milestone Roadmap

How to use this with Claude Code: feed it **one milestone at a time**, not
the whole file. Each milestone below is scoped to be self-contained — it
names its exact inputs and its exact deliverable, so Claude Code doesn't
need the rest of the roadmap in context to do the work. Check off a
milestone in this file when it's done; that checked state *is* the memory
you hand to the next session, instead of re-explaining status in prose.

Reference files to point Claude Code at once, up front (not repeated per
milestone): this file, DESIGN.md, and `CS-ST.pdf` + its extracted
`CS-ST-layout.txt` as the ground-truth fixture for the parser.

---

## M0 — Repo scaffold
- [x] Done (2026-09-09)
**Input:** DESIGN.md (stack choices), nothing else.
**Deliverable:** Empty-but-running skeleton — backend folder with one
health-check endpoint, frontend folder with one blank page, DB connection
config (no schema yet). No curriculum logic at all in this milestone.
**Done when:** `npm run dev` / equivalent boots both sides with no errors.

## M1 — PDF table parser (single program)
- [x] Done (2026-09-09)
**Input:** `CS-ST.pdf` (or its layout-extracted `.txt`) only.
**Deliverable:** A standalone script that parses the page-2 table into
JSON records: `{code, name, units, is_zero_credit, year, term,
requisites: [{type: "hard"|"soft"|"coreq"|"exemption", code}]}`.
Handle `None`, `TBA`, and multi-code requisite lists (e.g. `h: MTH101A,
BASMATH`).
**Don't do yet:** don't wire this to a database, don't generalize to
other PDFs. Ignore the free-text notes on the right side of the
flowchart (e.g. "CCPROG3 must be taken during Year 1," "CSADPRG must be
taken during Year 2") — parse only the Course Code/Name/Units/Requisites
table. Those notes are out of scope for the project, not just this
milestone.
**Done when:** running it on CS-ST produces JSON matching the table by
manual spot-check (pick 5 courses, verify against the PDF).

## M2 — Generalize parser across all 16 flowcharts
- [x] Done (2026-09-09) — 11 programs, not 16; see note below.
**Input:** the other 15 flowchart PDFs (not yet opened — expect some
layout drift since a few have different revision dates/producers).
**Deliverable:** the parser handles all 16, with a short exceptions log
for anything it can't parse cleanly (flag for manual fix, don't guess).
Output: one `curricula.json` covering every CCS program + curriculum
version.
**Done when:** every program's course count and total units roughly
match what's printed at the bottom of its flowchart ("Total units: X").

**Note:** the source data actually lives in `flowchart_records_11programs/`
as pre-parsed JSON-lines `.txt` files (11 programs, not 16 PDFs — no PDFs
or printed totals exist in this repo). `parse_flowchart.py` now tags every
record with its source `program` (filename stem) and flags a program
whose 'year' labels look collapsed (only 2 distinct labels across 30+
records, vs. 4-5 in comparable programs) — a real layout-drift defect
found in 6 of the 11 files. `parse_all_flowcharts.py` merges all 11 into
`parser/output/curricula.json` (729 records) and writes
`parser/output/exceptions_log.txt` (21 warnings: 4 empty names + the
collapsed-year flag in BSCS-CSE, 1 collapsed-year flag each in BSCS-NIS/
BSInfSec/BSIS/BSIT-CBL/BSIT, 2 LCC-pattern typos + 1 empty name in CS-ST,
2 empty names in CS, 5 empty names + 1 duplicate code in MSCS, none in
IET-AD/IET-GD). Total units per program are computed from parsed data
only, not cross-checked against a printed total (none exists here) —
spot-check manually if you have the source flowcharts.

## M3 — Database schema + seed
- [x] Done (2026-09-09)
**Input:** `curricula.json` from M2.
**Deliverable:** schema for `programs`, `curriculum_versions`, `courses`,
`course_slots` (a course's year/term position within one curriculum
version), `requisite_edges`, and `elective_slots` (for GE/elective
placeholders — these are categories, not fixed course codes). Seed script
loads `curricula.json` into it.
**Don't do yet:** no term-offering-domain table, no equivalency table —
those are separate milestones since they're not in the PDF data at all.

**Note:** schema is in `backend/app/models.py` (SQLAlchemy 2.0 declarative),
seed script in `backend/app/seed.py` — run via `python -m app.seed` from
`backend/` (uses `DATABASE_URL` from `.env`, or pass `--database-url`).
`course_slots.year_raw` stores the flowchart's literal year string
as-is (not normalized to a year number) since M2 flagged 6/11 programs'
year labels as unreliable — normalizing now would mean guessing at
exactly those records. `courses` has no unique constraint on
`(curriculum_version_id, code)` because MSCS has a genuine duplicate
`THESIS` code (flagged in M2, not fixed). `elective_slots` tags
LCC-prefixed and `*ELEC*`-suffixed courses (160 of 729) as category
placeholders rather than fixed titles.
`requisite_edges.requisite_course_id` is a nullable FK resolved by exact
code match within the same curriculum_version; 80 of 590 requisites don't
resolve (external exam-waiver codes like BASMATH/BASSTAT, and likely
upstream typos — e.g. `LSLSONE`/`LSLSTWO` referenced repeatedly instead of
the real `LCLSONE`/`LCLSTWO`, `PRCCC01` vs the real `PRCC01`, and a few
codes with stray parentheses like `(ITCMSY1`) — kept as raw text with a
null FK and printed as a warning list rather than guessed. First
verified end-to-end against a throwaway local SQLite file, then seeded
for real (2026-09-09) into the Supabase Postgres instance now configured
in `backend/.env` — 11 programs, 729 courses, 729 course_slots, 590
requisite_edges (510 resolved / 80 unresolved), 160 elective_slots, all
counts cross-checked against `curricula.json` and matching the SQLite
dry run exactly.

## M4 — Term-offering domain table
- [x] Done (2026-09-09)
**Input:** none from the PDFs — this is data you (domain expert) provide
directly, since the flowchart only shows the canonical on-time slot.
**Deliverable:** a `course_offering_windows` table/UI where each course
gets tagged: every term / T1 only / T2 only / T3 only / shifted-one-term-
earlier-for-delayed. Seed with what you already know; leave the rest
flagged "unknown" rather than guessing.
**Done when:** every course in `courses` has a row here (even if some are
"unknown").

**Note:** table added to `backend/app/models.py`
(`CourseOfferingWindow`, with a DB-level CHECK constraint on the allowed
window values); seed script `backend/app/seed_offering_windows.py`, run
via `python -m app.seed_offering_windows` from `backend/` (reads
existing `courses` rows, not `curricula.json`, so it must run after
M3's seed). Went with a table, not a UI — M9/M10 are the actual frontend
milestones, and the current frontend is still M0's blank page. Only
known override right now is `^LCC` → `every_term` (per the LCC-any-term
memory note); everything else seeds as `unknown`. Live in Supabase: 128
`every_term` (all the LCC.. courses) + 601 `unknown`, one row per course,
0 missing. Caught a real bug while seeding for real: `window` is a
reserved word in Postgres and the raw CHECK-constraint SQL wasn't
quoting it — SQLite let it slide silently, Postgres didn't. Renamed the
column to `offering_window` rather than relying on quoting.

## M5 — Cross-program equivalency table
- [x] Done (2026-09-09)
**Input:** `curricula.json`, your own knowledge of shared courses.
**Deliverable:** a table mapping the same course code across programs
where it might carry different prereqs/units per program (verify, don't
assume identical), plus a shiftee credit-mapping table between one
program's course codes and another's.

**Note:** two tables added to `backend/app/models.py`, both seeded by
`backend/app/seed_equivalencies.py` (`python -m app.seed_equivalencies`
from `backend/`, reads `curricula.json` directly like M3's seed does).
Live in Supabase now.
- `course_code_equivalencies`: one row per code that appears in 2+
  programs (100 of them), each flagging whether units/name/requisites
  actually agree everywhere that code is used. **62 of the 100 diverge
  on at least one of those** — e.g. `LBYCBC2` is 1 unit in BSIT-CBL but 2
  units in CS, under two different truncated names, with different
  requisites. Fully derived/recomputed each run, nothing hand-edited
  here.
- `shiftee_credit_mappings`: 34 candidate pairs of *different* codes that
  likely mean the same course across programs (e.g. BSIT-CBL's `CBPROG1`
  ↔ most other programs' `CCPROG1`), found by exact name match across
  programs and filtered to drop pairs that coexist inside any single
  program's own curriculum (that rules out e.g. `NSTP-01`/`NSTP-02`,
  which share a generic name but are two distinct sequential
  requirements, not the same course). Every row starts at
  `status="candidate"` — per "verify, don't assume identical," these are
  not asserted as fact. No UI yet to confirm/reject them (same reasoning
  as M4 — that's M9/M10); reseeding only adds newly-found pairs and never
  touches a row already set to `confirmed`/`rejected`, verified by
  manually confirming a row and rerunning.

## M6 — Scheduler v1 (greedy)
- [x] Done (2026-09-10)
**Input:** the M3 schema populated via M2 + M4.
**Deliverable:** a pure function/module — no API, no UI — that takes
(completed courses, target program, max units/term) and returns a
term-by-term plan via topological sort + earliest-feasible-slot
placement. Unit tests using CS-ST as the fixture, including at least one
case with a corequisite pair (e.g. CSARCH2/LBYARCH) and one with a
zero-credit course.
**Done when:** tests pass and a hand-traceable example (fresh student, no
completed courses, 18-unit cap) produces a sane 12-term plan.

**Note:** `backend/app/scheduler.py` — `generate_schedule()` is the pure
algorithm (plain data in/out, no DB); `load_program_courses()` is the
thin DB-backed adapter for real use (e.g. a future M8 endpoint);
`load_program_courses_from_records()` builds the same model straight
from `curricula.json`, which is what the tests use so they don't need a
live DB. Tests in `backend/app/test_scheduler.py`, run via
`python -m app.test_scheduler` from `backend/`.

Design calls the roadmap left open, made explicit in the module
docstring: terms in the output are student-relative (1, 2, 3, ...), not
flowchart year/terms; only `hard` (ordering) and `coreq` (same-term,
treated as symmetric even where the source data is one-sided — see
OVERNIGHT_QA_LOG.md 2026-09-10) are enforced, `soft`/`exemption` are
informational only; `units` count toward the term cap regardless of
`is_zero_credit` (that flag is about GPA credit, not term workload); a
course's `offering_window` gates which calendar term (T1/T2/T3,
cyclical) it can land in, falling back to its own flowchart-printed
`canonical_term` when the window is `unknown` — the one fact we actually
have, not a guess. A consequence of that last point, confirmed by
hand-testing with `--completed`: completing courses early does **not**
generally shorten the plan, since most courses (`offering_window`
still `unknown` for 601/729) stay anchored to their canonical term
regardless of how early their prereqs are satisfied. This is intentional
and will loosen automatically, with no code changes, as M4's
`course_offering_windows` data gets filled in for real.

Verified: `python -m app.test_scheduler` passes (coreq pairing, hard-
prereq ordering, zero-credit course `NSTP-01` handled, cycle detection,
oversized-cluster placement, a `--completed` case). Hand-traceable run
against the live DB (`python -m app.scheduler CS-ST --max-units 18`)
produces an 11-term plan — `CSARCH2`/`LBYARCH` land together in term 7,
the `THS-ST1→2→3` thesis chain strictly increases across terms 9-11,
NSTP/PE/GE spread sensibly throughout. 11 is a reasonable term count for
a 4-year/12-term program once things pack efficiently under an 18-unit
cap — not exactly 12, but within the same ballpark and every constraint
holds.

## M7 — Scheduler v2 (optimal via CP-SAT)
- [x] Done (2026-09-10)
**Input:** M6's test fixtures, reused as-is.
**Deliverable:** an alternative solver path using OR-Tools CP-SAT that
minimizes total terms; a comparison report showing where it beats the
greedy result and by how much, on the same fixtures.

**Note:** `backend/app/scheduler_cpsat.py` — `generate_schedule_optimal()`
takes/returns the exact same `SchedulableCourse`/`TermPlan` shapes as
M6's `generate_schedule()`, reusing its `_course_offering_ok` and its own
result as the search-horizon upper bound (a solution CP-SAT could always
fall back to, so it never excludes a better answer). `ortools>=9.11`
added to `backend/requirements.txt` and installed. Tests in
`backend/app/test_scheduler_cpsat.py` (`python -m app.test_scheduler_cpsat`),
against the same real CS-ST fixture as M6 per the roadmap's instruction —
verifies CP-SAT's output independently against the *same* constraints
(hard-prereq ordering, coreq same-term, unit cap, no gaps in the term
sequence), not just its own objective value, and asserts optimal never
needs *more* terms than greedy across several caps.

Coreq clustering is expressed differently than the greedy version's
explicit union-find: a per-pair equality constraint (`term[A] ==
term[B]`), which the solver naturally propagates transitively for larger
clusters without needing to precompute them. An explicit "no gaps before
the makespan" constraint was needed — minimizing the highest term used
doesn't by itself stop the solver from leaving an earlier term empty and
pushing a course later for no objective-value reason, which reads as a
nonsensical plan even though it doesn't change the optimization target.

**Comparison report** (`python -m app.scheduler_cpsat <program>`), run
against real seeded data:

| scenario | greedy | optimal | saved |
|---|---|---|---|
| CS-ST, 18u cap | 11 | 11 | 0 |
| CS-ST, 12u cap | 17 | 16 | 1 |
| CS-ST, 6u cap | 32 | 31 | 1 |
| BSCS-CSE, 18u cap | 12 | 11 | 1 |
| BSCS-CSE, 12u cap | 18 | 16 | 2 |
| BSCS-CSE, 6u cap | 33 | 32 | 1 |

CP-SAT ties greedy for CS-ST at the realistic 18-unit cap (expected --
per M6's notes, most courses are still anchored to their own canonical
term via the "unknown" offering-window fallback, leaving little room to
reorder), but beats it for BSCS-CSE even at 18 units, and beats it
everywhere tighter caps give packing more room to matter.

## M8 — Backend API
- [x] Done (2026-09-10)
**Deliverable:** endpoints to submit (completed courses, target program,
max units) and return a generated plan; wraps M6/M7 without duplicating
their logic.

**Note:** design settled via a grilling session before implementation
(see chat) — recorded here since the roadmap's own text left it all
open. `POST /schedule` and `GET /programs` added to `backend/app/main.py`;
request/response schemas in `backend/app/schemas.py`.
- `POST /schedule` body: `targetProgram`, `completedCourses` (codes),
  `maxUnitsPerTerm`, `solver` (`"greedy"` default | `"optimal"`, caller's
  choice) — calls M6's `generate_schedule` or M7's
  `generate_schedule_optimal` directly, no reimplemented scheduling
  logic. Response is the plan only (`TermPlan` shape) plus a small
  envelope (program, solver, term count) — no per-course
  eligibility/status metadata; that's M9's concern, not M8's.
- `GET /programs` — not asked for by the roadmap text, added anyway
  since a caller needs valid program codes; returns the code list,
  sorted (all `programs` has beyond an id).
- All JSON over the wire is camelCase (`schemas.CamelModel`, a Pydantic
  `alias_generator=to_camel` base); everything internal stays
  snake_case.
- Stateless — nothing persisted, matching M3-M5's schema (no "saved
  plans" table exists or is planned).
- Errors: unknown `targetProgram` -> 404. Unknown code(s) in
  `completedCourses` -> 400, listing the bad codes (checked against the
  program's own course list before calling the scheduler, so a typo
  can't silently produce a misleading plan). `solver=optimal` timing out
  -> 422 (added `SchedulingTimeoutError(SchedulingError)` to
  `scheduler.py` so `scheduler_cpsat.py` can raise it distinctly from
  plain infeasibility, itself also 422 with a different message) --
  reuses M7's existing 30s solve-time limit as-is, no second timeout
  layer. Malformed/missing request fields -> FastAPI's own 422
  (Pydantic validation), for free.

Verified live: started `backend/.venv`'s uvicorn, hit both endpoints
with curl. `GET /programs` returns all 11 codes. `POST /schedule` for
CS-ST/greedy/18u reproduces M6's hand-verified 11-term plan exactly, in
camelCase. `solver=optimal` for BSCS-CSE returns 11 terms, matching M7's
comparison report (beating greedy's 12). 404/400/422 all confirmed,
including Pydantic's own validation errors correctly reporting the
camelCase field name (e.g. `maxUnitsPerTerm`) back to the caller.

## M9 — Frontend: manual input + flowchart render
- [x] Done (2026-09-10)
**Deliverable:** a form for manually checking off completed courses, and
a rendered graph (React Flow or similar) color-coded by status
(completed / eligible-now / locked / needs-retake), consuming M8's API.

**Note:** design settled via a grilling session before implementation
(see chat). Turned out the roadmap's own text left a real gap: a true
4-state graph needs actual prereq edges and canonical positions, which
M8 didn't expose (only a computed schedule, not the underlying catalog)
— so this milestone also added a new backend endpoint,
`GET /programs/{code}/courses` (`backend/app/catalog.py`), before the
frontend work could start.

**Backend addition:** `catalog.py` returns a program's full course list
plus all requisite edges (all four types — the frontend decides what to
render) and a best-effort canonical year number, plus a
`yearDataReliable` flag recomputed live from the same heuristic
`parser/parse_flowchart.py` uses at parse time (fewer than 3 distinct
year labels across 30+ courses) — not a hardcoded program list, so it
can't drift stale as data changes.

**Frontend** (`frontend/src/`): `App.tsx` composes `CourseForm.tsx`
(grouped-by-year checklist with a filter, done/retake toggles),
`CourseGraph.tsx` (`@xyflow/react` + `@dagrejs/dagre`), and
`SchedulePanel.tsx` (calls M8's `/schedule`, solver picker, results
list). `deriveStatus.ts` computes the 4-state status client-side from
`hard` prereqs only (matching M6/M7's own convention — `coreq` doesn't
gate eligibility, it's a same-term grouping concern). `needs-retake` is
a purely client-side annotation (`useCompletedCourses.ts`,
`localStorage`-backed per program) — excluded from what's sent to
`/schedule`, never touches the backend. Design tokens lifted from
`DESIGN-cal.md` as CSS custom properties in `index.css`; Inter substitutes
for Cal Sans per that file's own documented fallback.

**Real bug found and fixed while verifying in the browser (not just
typecheck/lint):** dagre lays out each weakly-connected component side
by side. With ~20+ courses having zero prereq/dependent edges at all
(electives, PE, NSTP, orientation courses), the layout ballooned to
~7800px wide, and React Flow's `fitView` — capped by its default
`minZoom` — could only show a sliver of it, looking like most nodes had
vanished. Fixed by laying out only the courses that actually participate
in an edge via dagre, then grid-packing the genuinely isolated ones
densely underneath instead of giving each its own column. Also needed a
`key={program}` on `<CourseGraph>` — `fitView` only runs once on mount,
so switching programs without forcing a remount left the camera fitted
to the *previous* program's layout.

Verified live in the browser end-to-end, not just typecheck/build:
program switching (reliable vs. the 6 flagged-unreliable programs, with
the warning banner appearing correctly), live recoloring on marking a
course done, `localStorage` persistence surviving a full page reload,
correct solid-vs-dashed edges on the real `CSARCH2`/`LBYARCH` coreq
pair, and "Generate my plan" (CS-ST, greedy, 18u) returning the same
11-term result M6 already hand-verified. `tsc -b`, `oxlint`, and
`vite build` all clean.

## M10 — Paste-parse ingestion
- [ ] Not started
**Deliverable:** a text box where a student pastes their raw portal
curriculum-progress export; parse it into the same "completed courses"
shape M9's manual form produces. This replaces live scraping for v1.

## M11 — Deploy to Vercel
- [x] Done (2026-09-10)
Supersedes the original "browser extension" plan for this milestone slot
— the user decided to deploy on Vercel instead of building a browser
extension. (The extension's read-only-DOM-parsing idea may still be
worth revisiting later, but it's no longer this milestone's scope.)

**Deliverable:** `frontend/` and `backend/` deploy together as one
Vercel project via [Vercel Services](https://vercel.com/docs/services)
(`vercel.json` at the repo root) — a JS frontend and a Python backend in
one polyglot monorepo, sharing one domain, is exactly what Services is
for. Confirmed current Vercel platform limits comfortably fit this
stack before committing to the approach: Fluid compute (default for new
projects) gives Python functions 500 MB uncompressed (this backend's
full `site-packages`, OR-Tools/pandas/numpy included, is ~224 MB) and
300s default duration (CP-SAT's own internal solve-time limit is 30s) —
both checked against Vercel's own current docs, not assumed from
possibly-stale general knowledge of serverless limits.

**Routing:** all backend routes moved under `/api` (`backend/app/main.py`
now registers everything on an `APIRouter(prefix="/api")`) so
`vercel.json`'s rewrites can send `/api/*` to the `backend` service and
everything else to the `frontend` service's static build.
`frontend/src/api.ts` defaults to a same-origin relative base URL
(empty string) for that shared-domain production case; local dev sets
`VITE_API_URL=http://localhost:8000` in `frontend/.env` (gitignored, not
committed) to reach the separately-running backend dev server instead.

**Verified:** `vercel dev -L` (local mode, no cloud auth) correctly
auto-detected both services from `vercel.json` ("frontend [Vite]",
"backend [FastAPI]"), confirming the config itself is valid. It then hit
a real bug in Vercel CLI's own Windows-local dev tooling — a generated
Python bootstrap file embeds this project's Windows path unescaped,
corrupting a `\Users` backslash into an invalid `\U` unicode-escape
sequence — which is specific to running `vercel dev` locally on Windows,
not to how Vercel actually builds/deploys Python functions in its
(Linux-based) cloud build step. Confirmed independently instead: `/api`
routes respond correctly (`curl` against the real running backend), the
old unprefixed paths correctly 404, and `vite build` / `tsc -b` both
stay clean. Actually deploying (`vercel deploy`, needs a real account +
`DATABASE_URL` set as a Vercel project environment variable, never
committed) is the one remaining step only the user can do.
