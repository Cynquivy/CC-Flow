"""M6: scheduler v1 -- topological sort + earliest-feasible-slot placement.

`generate_schedule` is the pure algorithm: no DB, no IO, just plain data in
and out, so it's unit-testable without a live database (see
test_scheduler.py, which builds its fixtures from parser/output/curricula.json
rather than the DB for exactly that reason). `load_program_courses` is the
thin adapter that actually reads the M3 schema (populated via M2's seed +
M4's offering windows) for real use -- e.g. a future M8 API endpoint.

Design decisions, since the roadmap left some of this unspecified:

- Terms in the output are *student-relative* (1, 2, 3, 4, ... continuous
  enrollment, no gaps), not the flowchart's specific year/term-of-a-given-
  academic-year. `calendar_term = ((term_number - 1) % 3) + 1` maps a
  student-relative term back onto the recurring T1/T2/T3 academic cycle,
  which is what course_offering_windows constrains against.
- Only `hard` requisites are enforced as ordering constraints (must be
  scheduled strictly earlier) and `coreq` as same-term grouping. `soft`
  (recommended, not required) and `exemption` (a waiver relationship, not
  a scheduling one) are informational only -- not enforced here.
- A requisite that doesn't resolve to a real course in this program (an
  external exam-waiver code, or one of the known typos -- see M3's
  exceptions and OVERNIGHT_QA_LOG.md) can't be enforced and is dropped,
  same as it already is in requisite_edges.requisite_course_id being null.
- coreq is treated as symmetric for clustering purposes even where only
  one side's data says so (8 known one-sided cases remain per
  OVERNIGHT_QA_LOG.md 2026-09-10) -- corequisite is symmetric by
  definition, so the clustering doesn't need both sides to agree.
- A course's offering_window governs which calendar term it can land in:
  "every_term" any time; "tN_only" only calendar term N; "unknown" or
  "shifted_earlier_delayed" (or missing) fall back to the course's own
  canonical_term (its flowchart-printed position) as the only constraint
  we actually have -- not a guess, just using the one known fact. A
  course with no canonical_term either (a TBA slot) is allowed in any
  term as a last resort.
- Units count toward max_units_per_term regardless of is_zero_credit --
  that flag is about GPA/degree-credit, not term workload/registration
  load. See OVERNIGHT_QA_LOG.md 2026-09-09 run 2 for why this isn't the
  same thing.
- If a single coreq cluster's combined units alone exceed
  max_units_per_term, it's placed anyway (rather than deferred forever)
  since a coreq cluster can't be split across terms -- this is the only
  case the term total can exceed the nominal cap.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Course, CourseOfferingWindow, CourseSlot, CurriculumVersion, Program, RequisiteEdge
from .seed_offering_windows import _classify_offering_window

MAX_TERMS = 60


class SchedulingError(Exception):
    pass


class SchedulingTimeoutError(SchedulingError):
    """A solver ran out of time without concluding whether a schedule exists at all
    (distinct from SchedulingError's plain case, which means no schedule exists --
    see scheduler_cpsat.py, the only place this is currently raised)."""


@dataclass(frozen=True)
class SchedulableCourse:
    code: str
    name: str
    units: float
    is_zero_credit: bool
    canonical_term: int | None
    offering_window: str
    hard_prereqs: frozenset[str] = field(default_factory=frozenset)
    coreqs: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ScheduledCourse:
    code: str
    name: str
    units: float


@dataclass(frozen=True)
class TermPlan:
    term_number: int
    calendar_term: int
    courses: tuple[ScheduledCourse, ...]
    total_units: float


def load_program_courses(session: Session, program_code: str) -> list[SchedulableCourse]:
    """Load one program's courses from the live M3 schema."""
    program = session.scalar(select(Program).where(Program.code == program_code))
    if program is None:
        raise SchedulingError(f"no program with code {program_code!r}")

    curriculum_version = session.scalar(
        select(CurriculumVersion).where(CurriculumVersion.program_id == program.id)
    )
    if curriculum_version is None:
        raise SchedulingError(f"program {program_code!r} has no curriculum_version")

    courses = list(
        session.scalars(select(Course).where(Course.curriculum_version_id == curriculum_version.id))
    )
    course_ids = [c.id for c in courses]
    code_by_id = {c.id: c.code for c in courses}

    hard_prereqs: dict[int, set[str]] = defaultdict(set)
    coreqs: dict[int, set[str]] = defaultdict(set)
    for edge in session.scalars(select(RequisiteEdge).where(RequisiteEdge.course_id.in_(course_ids))):
        if edge.requisite_course_id is None:
            continue  # unresolved (external code or typo) -- can't enforce, see M3 notes
        target_code = code_by_id.get(edge.requisite_course_id)
        if target_code is None:
            continue
        if edge.type == "hard":
            hard_prereqs[edge.course_id].add(target_code)
        elif edge.type == "coreq":
            coreqs[edge.course_id].add(target_code)
        # soft/exemption: informational only, not enforced by the scheduler

    slot_by_course = {
        s.course_id: s for s in session.scalars(select(CourseSlot).where(CourseSlot.course_id.in_(course_ids)))
    }
    window_by_course = {
        w.course_id: w
        for w in session.scalars(select(CourseOfferingWindow).where(CourseOfferingWindow.course_id.in_(course_ids)))
    }

    result = []
    for c in courses:
        slot = slot_by_course.get(c.id)
        window = window_by_course.get(c.id)
        result.append(
            SchedulableCourse(
                code=c.code,
                name=c.name,
                units=c.units or 0.0,
                is_zero_credit=c.is_zero_credit,
                canonical_term=slot.term if slot else None,
                offering_window=window.offering_window if window else "unknown",
                hard_prereqs=frozenset(hard_prereqs.get(c.id, ())),
                coreqs=frozenset(coreqs.get(c.id, ())),
            )
        )
    return result


def load_program_courses_from_records(records: list[dict]) -> list[SchedulableCourse]:
    """Alternate loader: builds the same model directly from a list of
    parser/output/curricula.json records already filtered to one program,
    without touching the DB. Used by tests against the real CS-ST fixture.
    """
    codes = {r["code"] for r in records}
    result = []
    for r in records:
        hard = set()
        coreq = set()
        for q in r["requisites"]:
            if q["code"] not in codes:
                continue  # unresolved/external -- same resolution rule as M3's DB loader
            if q["type"] == "hard":
                hard.add(q["code"])
            elif q["type"] == "coreq":
                coreq.add(q["code"])
        offering_window, _ = _classify_offering_window(r["code"])
        result.append(
            SchedulableCourse(
                code=r["code"],
                name=r["name"],
                units=r["units"] or 0.0,
                is_zero_credit=r["is_zero_credit"],
                canonical_term=r["term"],
                offering_window=offering_window,
                hard_prereqs=frozenset(hard),
                coreqs=frozenset(coreq),
            )
        )
    return result


def _course_offering_ok(course: SchedulableCourse, calendar_term: int) -> bool:
    window = course.offering_window
    if window == "every_term":
        return True
    if window in ("t1_only", "t2_only", "t3_only"):
        return int(window[1]) == calendar_term
    # "unknown", "shifted_earlier_delayed", or anything else: fall back to the
    # flowchart's own canonical term -- the one fact we have. No canonical term
    # either (a TBA course) -- allow any term as a last resort.
    if course.canonical_term is None:
        return True
    return course.canonical_term == calendar_term


def generate_schedule(
    courses: list[SchedulableCourse],
    completed_courses: set[str],
    max_units_per_term: float,
) -> list[TermPlan]:
    by_code = {c.code: c for c in courses}
    needs_scheduling = {c.code for c in courses if c.code not in completed_courses}

    # Union-find over coreq edges, treated as symmetric regardless of whether
    # the source data agrees on both sides (see module docstring).
    parent: dict[str, str] = {code: code for code in needs_scheduling}

    def find(x: str) -> str:
        while parent[x] != x:
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for code in needs_scheduling:
        for other in by_code[code].coreqs:
            if other in needs_scheduling:
                union(code, other)

    clusters: dict[str, set[str]] = defaultdict(set)
    for code in needs_scheduling:
        clusters[find(code)].add(code)
    cluster_of = {code: find(code) for code in needs_scheduling}

    depends_on: dict[str, set[str]] = defaultdict(set)
    for code in needs_scheduling:
        for prereq_code in by_code[code].hard_prereqs:
            if prereq_code not in needs_scheduling:
                continue  # already completed, or unresolved/external -- trivially satisfied
            prereq_cluster = cluster_of[prereq_code]
            if prereq_cluster != cluster_of[code]:
                depends_on[cluster_of[code]].add(prereq_cluster)

    remaining = set(clusters)
    scheduled_term: dict[str, int] = {}
    plans: list[TermPlan] = []
    term_number = 0

    while remaining:
        term_number += 1
        if term_number > MAX_TERMS:
            unresolved = ", ".join(sorted(remaining))
            raise SchedulingError(
                f"could not schedule within {MAX_TERMS} terms -- remaining clusters: {unresolved} "
                "(likely a hard-prerequisite cycle, or an offering-window that never matches)"
            )
        calendar_term = ((term_number - 1) % 3) + 1

        ready = [
            cluster
            for cluster in remaining
            if depends_on[cluster] <= scheduled_term.keys()
            and all(_course_offering_ok(by_code[m], calendar_term) for m in clusters[cluster])
        ]

        def priority(cluster: str) -> tuple:
            members = clusters[cluster]
            canonical_match = any(by_code[m].canonical_term == calendar_term for m in members)
            downstream_count = sum(1 for c in remaining if cluster in depends_on[c])
            return (not canonical_match, -downstream_count, min(members))

        ready.sort(key=priority)

        term_units = 0.0
        term_members: list[str] = []
        for cluster in ready:
            cluster_units = sum(by_code[m].units for m in clusters[cluster])
            if term_members and term_units + cluster_units > max_units_per_term:
                continue
            term_members.extend(clusters[cluster])
            term_units += cluster_units
            scheduled_term[cluster] = term_number
            remaining.discard(cluster)

        if term_members:
            scheduled = tuple(
                ScheduledCourse(code=code, name=by_code[code].name, units=by_code[code].units)
                for code in sorted(term_members)
            )
            plans.append(
                TermPlan(
                    term_number=term_number,
                    calendar_term=calendar_term,
                    courses=scheduled,
                    total_units=term_units,
                )
            )

    return plans


def _print_plan(plans: list[TermPlan]) -> None:
    for plan in plans:
        print(f"Term {plan.term_number} (calendar T{plan.calendar_term}) -- {plan.total_units:g} units")
        for c in plan.courses:
            print(f"    {c.code:10} {c.units:g}u  {c.name}")


def main() -> None:
    import argparse

    from sqlalchemy import create_engine

    from .config import get_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", nargs="?", default="CS-ST")
    parser.add_argument("--max-units", type=float, default=18.0)
    parser.add_argument("--completed", default="", help="comma-separated completed course codes")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    database_url = args.database_url or get_settings().database_url
    if not database_url:
        import sys

        print("no DATABASE_URL configured (set it in backend/.env or pass --database-url)", file=sys.stderr)
        raise SystemExit(1)

    completed = {c.strip() for c in args.completed.split(",") if c.strip()}

    engine = create_engine(database_url)
    with Session(engine) as session:
        courses = load_program_courses(session, args.program)

    plans = generate_schedule(courses, completed, args.max_units)
    print(f"{args.program}: {len(plans)} term(s), {len(completed)} course(s) already completed, "
          f"{args.max_units:g}-unit cap")
    print()
    _print_plan(plans)


if __name__ == "__main__":
    main()
