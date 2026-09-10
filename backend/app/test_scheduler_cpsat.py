"""M7 tests, against the same real CS-ST fixture as M6's test_scheduler.py
(per the roadmap: "Input: M6's test fixtures, reused as-is").

Run with: python -m app.test_scheduler_cpsat (from backend/, with .venv active)
"""

from __future__ import annotations

import json
from pathlib import Path

from .scheduler import SchedulingError, generate_schedule, load_program_courses_from_records
from .scheduler_cpsat import compare_schedules, generate_schedule_optimal

CURRICULA_PATH = Path(__file__).resolve().parent.parent.parent / "parser" / "output" / "curricula.json"


def _load_cs_st() -> list:
    records = json.loads(CURRICULA_PATH.read_text(encoding="utf-8"))
    cs_st_records = [r for r in records if r["program"] == "CS-ST"]
    return load_program_courses_from_records(cs_st_records)


def _term_of(plans, code: str) -> int:
    for plan in plans:
        if any(c.code == code for c in plan.courses):
            return plan.term_number
    raise AssertionError(f"{code} not found in any term of the plan")


def run() -> None:
    courses = _load_cs_st()
    by_code = {c.code: c for c in courses}

    plans = generate_schedule_optimal(courses, completed_courses=set(), max_units_per_term=18.0)

    # Same correctness properties test_scheduler.py checks on the greedy result --
    # CP-SAT's output has to satisfy the identical constraints, just search harder for
    # a better makespan.
    all_scheduled = [c.code for plan in plans for c in plan.courses]
    assert sorted(all_scheduled) == sorted(by_code), "every course should appear exactly once"

    for plan in plans:
        assert plan.total_units <= 18.0 + 1e-6, f"term {plan.term_number} exceeds the 18-unit cap"

    assert _term_of(plans, "CSARCH2") == _term_of(plans, "LBYARCH"), (
        "CSARCH2/LBYARCH must land in the same term"
    )

    term_of_all = {code: _term_of(plans, code) for code in by_code}
    for code, course in by_code.items():
        for prereq in course.hard_prereqs:
            if prereq in term_of_all:
                assert term_of_all[prereq] < term_of_all[code], (
                    f"{code} requires {prereq}, but it isn't scheduled strictly earlier"
                )

    # No gaps: term numbers used must be contiguous starting at 1.
    used_terms = sorted(plan.term_number for plan in plans)
    assert used_terms == list(range(1, len(used_terms) + 1)), (
        f"expected a contiguous term sequence, got {used_terms}"
    )

    # Optimal must never need MORE terms than greedy across a range of caps -- that's
    # the entire point of a v2 "optimal" solver existing alongside v1 "greedy".
    for cap in (18.0, 12.0, 6.0):
        greedy_plans = generate_schedule(courses, set(), cap)
        optimal_plans = generate_schedule_optimal(courses, set(), cap, horizon_terms=len(greedy_plans))
        assert len(optimal_plans) <= len(greedy_plans), (
            f"cap={cap}: optimal used {len(optimal_plans)} terms, more than greedy's {len(greedy_plans)}"
        )

    # compare_schedules should report a non-negative saving and agree with the above.
    result = compare_schedules(courses, set(), 12.0, "CS-ST 12u")
    assert result.terms_saved >= 0

    print("All assertions passed.")


def run_cycle_detection() -> None:
    from .scheduler import SchedulableCourse

    a = SchedulableCourse(
        code="A", name="A", units=3.0, is_zero_credit=False, canonical_term=1,
        offering_window="every_term", hard_prereqs=frozenset({"B"}),
    )
    b = SchedulableCourse(
        code="B", name="B", units=3.0, is_zero_credit=False, canonical_term=1,
        offering_window="every_term", hard_prereqs=frozenset({"A"}),
    )
    try:
        generate_schedule_optimal([a, b], set(), 18.0, horizon_terms=5)
    except SchedulingError:
        pass
    else:
        raise AssertionError("a genuine hard-prereq cycle should raise SchedulingError")

    print("Cycle detection assertion passed.")


if __name__ == "__main__":
    run()
    run_cycle_detection()
