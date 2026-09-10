"""M7: scheduler v2 -- optimal via OR-Tools CP-SAT.

An alternative solver path to M6's greedy scheduler.py, reusing the exact
same input model (SchedulableCourse) and the exact same fixtures (CS-ST
from parser/output/curricula.json). Same constraint semantics as the
greedy version, so the two are directly comparable:

- Only `hard` requisites are enforced (strictly earlier term); `coreq` as
  an equality constraint (same term) -- equality is transitive under the
  solver, so a multi-course coreq cluster falls out naturally without
  needing to precompute it via union-find the way the greedy version does.
- `units` count toward max_units_per_term regardless of is_zero_credit.
- offering_window restricts which terms a course's domain even contains
  (see scheduler._course_offering_ok), same "unknown -> canonical_term"
  fallback as the greedy version.
- Minimizes the highest term number actually used (the makespan), which
  is "total terms" in the roadmap's wording. A "no gaps before the
  makespan" constraint keeps the result a realistic term-by-term plan --
  without it CP-SAT is equally happy leaving terms empty partway through
  and pushing courses later than necessary, which technically doesn't
  change the objective but reads as a nonsensical plan.
- The search horizon defaults to the greedy result's own term count: it's
  a solution CP-SAT could always fall back to, so it bounds the search
  without ever excluding a better answer.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .scheduler import (
    ScheduledCourse,
    SchedulableCourse,
    SchedulingError,
    SchedulingTimeoutError,
    TermPlan,
    _course_offering_ok,
    generate_schedule,
)

SOLVE_TIME_LIMIT_SECONDS = 30.0
UNIT_SCALE = 10  # unit values in this dataset go to one decimal place at most


def generate_schedule_optimal(
    courses: list[SchedulableCourse],
    completed_courses: set[str],
    max_units_per_term: float,
    horizon_terms: int | None = None,
) -> list[TermPlan]:
    by_code = {c.code: c for c in courses}
    needs_scheduling = sorted(c.code for c in courses if c.code not in completed_courses)
    if not needs_scheduling:
        return []

    if horizon_terms is None:
        horizon_terms = len(generate_schedule(courses, completed_courses, max_units_per_term))
        if horizon_terms == 0:
            return []

    model = cp_model.CpModel()

    allowed_terms: dict[str, list[int]] = {}
    for code in needs_scheduling:
        course = by_code[code]
        allowed = [
            t for t in range(1, horizon_terms + 1) if _course_offering_ok(course, ((t - 1) % 3) + 1)
        ]
        if not allowed:
            raise SchedulingError(
                f"{code}: no term within a {horizon_terms}-term horizon satisfies its offering window"
            )
        allowed_terms[code] = allowed

    term_var = {
        code: model.new_int_var_from_domain(cp_model.Domain.from_values(allowed_terms[code]), f"term_{code}")
        for code in needs_scheduling
    }

    for code in needs_scheduling:
        for prereq in by_code[code].hard_prereqs:
            if prereq in term_var:
                model.add(term_var[prereq] < term_var[code])

    seen_pairs = set()
    for code in needs_scheduling:
        for other in by_code[code].coreqs:
            if other not in term_var:
                continue
            pair = tuple(sorted((code, other)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            model.add(term_var[code] == term_var[other])

    in_term: dict[tuple[str, int], cp_model.IntVar] = {}
    for code in needs_scheduling:
        for t in allowed_terms[code]:
            lit = model.new_bool_var(f"in_term_{code}_{t}")
            model.add(term_var[code] == t).only_enforce_if(lit)
            model.add(term_var[code] != t).only_enforce_if(lit.negated())
            in_term[(code, t)] = lit

    cap_scaled = round(max_units_per_term * UNIT_SCALE)
    term_used: dict[int, cp_model.IntVar] = {}
    for t in range(1, horizon_terms + 1):
        lits_this_term = [in_term[(code, t)] for code in needs_scheduling if (code, t) in in_term]
        if lits_this_term:
            weighted = [(round(by_code[code].units * UNIT_SCALE), in_term[(code, t)]) for code in needs_scheduling if (code, t) in in_term]
            model.add(sum(units * lit for units, lit in weighted) <= cap_scaled)
            used = model.new_bool_var(f"term_used_{t}")
            model.add_max_equality(used, lits_this_term)
        else:
            used = model.new_constant(0)
        term_used[t] = used

    # No gaps: once a term goes unused, no later term may be used either --
    # keeps the plan a realistic contiguous term-by-term sequence.
    for t in range(1, horizon_terms):
        model.add(term_used[t] >= term_used[t + 1])

    max_term = model.new_int_var(1, horizon_terms, "max_term")
    model.add_max_equality(max_term, list(term_var.values()))
    model.minimize(max_term)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_TIME_LIMIT_SECONDS
    status = solver.solve(model)

    if status == cp_model.UNKNOWN:
        # Hit the time limit before concluding feasible or infeasible either way --
        # distinct from a confirmed "no schedule exists" (see SchedulingTimeoutError).
        raise SchedulingTimeoutError(
            f"CP-SAT timed out after {SOLVE_TIME_LIMIT_SECONDS:g}s without resolving a "
            f"{horizon_terms}-term horizon"
        )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SchedulingError(
            f"CP-SAT found no feasible schedule within a {horizon_terms}-term horizon "
            f"(status={solver.status_name(status)})"
        )

    by_term: dict[int, list[str]] = defaultdict(list)
    for code in needs_scheduling:
        by_term[solver.value(term_var[code])].append(code)

    plans = []
    for t in sorted(by_term):
        members = sorted(by_term[t])
        scheduled = tuple(ScheduledCourse(code=c, name=by_code[c].name, units=by_code[c].units) for c in members)
        plans.append(
            TermPlan(
                term_number=t,
                calendar_term=((t - 1) % 3) + 1,
                courses=scheduled,
                total_units=sum(by_code[c].units for c in members),
            )
        )
    return plans


@dataclass(frozen=True)
class ComparisonResult:
    label: str
    greedy_terms: int
    optimal_terms: int

    @property
    def terms_saved(self) -> int:
        return self.greedy_terms - self.optimal_terms


def compare_schedules(
    courses: list[SchedulableCourse],
    completed_courses: set[str],
    max_units_per_term: float,
    label: str,
) -> ComparisonResult:
    greedy_plans = generate_schedule(courses, completed_courses, max_units_per_term)
    optimal_plans = generate_schedule_optimal(
        courses, completed_courses, max_units_per_term, horizon_terms=len(greedy_plans) or None
    )
    return ComparisonResult(
        label=label, greedy_terms=len(greedy_plans), optimal_terms=len(optimal_plans) or len(greedy_plans)
    )


def _print_comparison_report(results: list[ComparisonResult]) -> None:
    print(f"{'scenario':<28} {'greedy':>8} {'optimal':>8} {'saved':>7}")
    for r in results:
        print(f"{r.label:<28} {r.greedy_terms:>8} {r.optimal_terms:>8} {r.terms_saved:>7}")


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    from .scheduler import load_program_courses_from_records

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", nargs="?", default="CS-ST")
    args = parser.parse_args()

    curricula_path = Path(__file__).resolve().parent.parent.parent / "parser" / "output" / "curricula.json"
    records = json.loads(curricula_path.read_text(encoding="utf-8"))
    program_records = [r for r in records if r["program"] == args.program]
    courses = load_program_courses_from_records(program_records)

    results = [
        compare_schedules(courses, set(), 18.0, f"{args.program}, fresh, 18u cap"),
        compare_schedules(courses, set(), 12.0, f"{args.program}, fresh, 12u cap"),
        compare_schedules(courses, set(), 6.0, f"{args.program}, fresh, 6u cap"),
    ]
    _print_comparison_report(results)


if __name__ == "__main__":
    main()
