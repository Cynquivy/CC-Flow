"""M6 tests, against the real CS-ST program data (parser/output/curricula.json)
rather than a synthetic fixture -- per the roadmap's "Unit tests using CS-ST
as the fixture." No DB needed: load_program_courses_from_records builds the
same model generate_schedule consumes directly from the parsed JSON.

Run with: python -m app.test_scheduler (from backend/, with .venv active)
"""

from __future__ import annotations

import json
from pathlib import Path

from .scheduler import SchedulingError, generate_schedule, load_program_courses_from_records

CURRICULA_PATH = Path(__file__).resolve().parent.parent.parent / "parser" / "output" / "curricula.json"


def _load_cs_st() -> list:
    records = json.loads(CURRICULA_PATH.read_text(encoding="utf-8"))
    cs_st_records = [r for r in records if r["program"] == "CS-ST"]
    assert cs_st_records, "expected CS-ST records in curricula.json"
    return load_program_courses_from_records(cs_st_records)


def _term_of(plans, code: str) -> int:
    for plan in plans:
        if any(c.code == code for c in plan.courses):
            return plan.term_number
    raise AssertionError(f"{code} not found in any term of the plan")


def run() -> None:
    courses = _load_cs_st()
    by_code = {c.code: c for c in courses}

    # Fresh student, no completed courses, 18-unit cap -- the roadmap's own
    # hand-traceable scenario.
    plans = generate_schedule(courses, completed_courses=set(), max_units_per_term=18.0)

    all_scheduled = [c.code for plan in plans for c in plan.courses]
    assert sorted(all_scheduled) == sorted(by_code), (
        "every course should appear exactly once across the plan"
    )

    assert 8 <= len(plans) <= 16, (
        f"expected a 'sane' term count for a 4-year program, got {len(plans)}"
    )

    for plan in plans:
        assert plan.total_units <= 18.0 or len(plan.courses) == 1, (
            f"term {plan.term_number} exceeds the 18-unit cap with more than one course: {plan.courses}"
        )

    # Corequisite pair: CSARCH2 (lecture) / LBYARCH (its lab) must land in the same term.
    assert "CSARCH2" in by_code and "LBYARCH" in by_code, "fixture should contain the CSARCH2/LBYARCH pair"
    assert _term_of(plans, "CSARCH2") == _term_of(plans, "LBYARCH"), (
        "CSARCH2 and LBYARCH are a coreq pair and must be scheduled in the same term"
    )

    # Zero-credit course: NSTP-01 (a real CS-ST course, is_zero_credit=True, nonzero units)
    # must still get scheduled like any other course.
    assert by_code["NSTP-01"].is_zero_credit is True
    nstp_term = _term_of(plans, "NSTP-01")
    assert any(c.code == "NSTP-01" for c in plans[nstp_term - 1].courses)

    # Every hard prerequisite must land strictly before the course that requires it.
    term_of_all = {code: _term_of(plans, code) for code in by_code}
    for code, course in by_code.items():
        for prereq in course.hard_prereqs:
            if prereq not in term_of_all:
                continue
            assert term_of_all[prereq] < term_of_all[code], (
                f"{code} requires {prereq} as a hard prereq, but {prereq} is scheduled at "
                f"term {term_of_all[prereq]} and {code} at term {term_of_all[code]}"
            )

    # Completed courses: pre-completing CSARCH1 should drop it from the plan and not
    # break its dependents (CSARCH2/LBYARCH, which hard-require it).
    plans_with_completed = generate_schedule(
        courses, completed_courses={"CSARCH1"}, max_units_per_term=18.0
    )
    scheduled_codes = {c.code for plan in plans_with_completed for c in plan.courses}
    assert "CSARCH1" not in scheduled_codes, "a completed course shouldn't be re-scheduled"
    assert "CSARCH2" in scheduled_codes and "LBYARCH" in scheduled_codes

    # A tighter but still realistic cap shouldn't raise; the scheduler should just take
    # longer (more terms) to fit everything in.
    plans_tight = generate_schedule(courses, completed_courses=set(), max_units_per_term=6.0)
    assert len(plans_tight) > len(plans), "a tighter cap should need at least as many terms"
    assert sorted(c.code for plan in plans_tight for c in plan.courses) == sorted(by_code)

    print("All assertions passed.")


def run_cycle_detection() -> None:
    # A synthetic hard-prereq cycle should raise SchedulingError rather than hang.
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
        generate_schedule([a, b], set(), 18.0)
    except SchedulingError:
        pass
    else:
        raise AssertionError("a genuine hard-prereq cycle should raise SchedulingError")

    print("Cycle detection assertion passed.")


def run_oversized_cluster() -> None:
    # A coreq pair whose combined units exceed max_units_per_term must still be placed
    # together in one term (never split, never stuck) -- exceeding the nominal cap just
    # for that one term, per the module docstring.
    from .scheduler import SchedulableCourse

    lecture = SchedulableCourse(
        code="LEC", name="Lecture", units=3.0, is_zero_credit=False, canonical_term=1,
        offering_window="every_term", coreqs=frozenset({"LAB"}),
    )
    lab = SchedulableCourse(
        code="LAB", name="Lab", units=3.0, is_zero_credit=False, canonical_term=1,
        offering_window="every_term", coreqs=frozenset({"LEC"}),
    )
    plans = generate_schedule([lecture, lab], set(), max_units_per_term=4.0)
    assert len(plans) == 1, "the coreq pair must land in a single term, not split across two"
    assert plans[0].total_units == 6.0, "both courses' units count toward that term's total"
    assert {c.code for c in plans[0].courses} == {"LEC", "LAB"}

    print("Oversized-cluster assertion passed.")


if __name__ == "__main__":
    run()
    run_cycle_detection()
    run_oversized_cluster()
