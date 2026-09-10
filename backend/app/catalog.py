"""M9 backend support: the full per-program course catalog, including
prereq edges and a best-effort canonical year number. Used by the
frontend to group the completed-courses form and lay out/flag the
graph. Not part of M6/M7's scheduling -- this is a separate, simpler
read: give me everything about a program's courses, no scheduling.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Course, CourseSlot, CurriculumVersion, Program, RequisiteEdge

_YEAR_NUMBER_PATTERN = re.compile(r"Year (\d+)")
_YEAR_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}

# A program's year labels are unreliable if there are fewer than 3 distinct
# values across 30+ course records -- the same heuristic parser/parse_flowchart.py
# uses at parse time (see parser/output/exceptions_log.txt). Recomputed here from
# live data rather than a hardcoded program list, so it can't drift stale.
_UNRELIABLE_MIN_RECORDS = 30
_UNRELIABLE_MAX_DISTINCT_LABELS = 3


def _extract_year_number(year_raw: str | None) -> int | None:
    if not year_raw:
        return None
    match = _YEAR_NUMBER_PATTERN.search(year_raw)
    if match:
        return int(match.group(1))
    lowered = year_raw.lower()
    for word, number in _YEAR_WORDS.items():
        if word in lowered:
            return number
    return None


@dataclass(frozen=True)
class CourseRequisite:
    type: str
    code: str


@dataclass(frozen=True)
class CatalogCourse:
    code: str
    name: str
    units: float
    is_zero_credit: bool
    year_raw: str | None
    year_number: int | None
    term: int | None
    requisites: list[CourseRequisite]


@dataclass(frozen=True)
class ProgramCatalog:
    program: str
    year_data_reliable: bool
    courses: list[CatalogCourse]


class CatalogError(Exception):
    pass


def load_program_catalog(session: Session, program_code: str) -> ProgramCatalog:
    program = session.scalar(select(Program).where(Program.code == program_code))
    if program is None:
        raise CatalogError(f"no program with code {program_code!r}")

    curriculum_version = session.scalar(
        select(CurriculumVersion).where(CurriculumVersion.program_id == program.id)
    )
    if curriculum_version is None:
        raise CatalogError(f"program {program_code!r} has no curriculum_version")

    courses = list(
        session.scalars(select(Course).where(Course.curriculum_version_id == curriculum_version.id))
    )
    course_ids = [c.id for c in courses]
    code_by_id = {c.id: c.code for c in courses}

    slot_by_course = {
        s.course_id: s
        for s in session.scalars(select(CourseSlot).where(CourseSlot.course_id.in_(course_ids)))
    }

    requisites_by_course: dict[int, list[CourseRequisite]] = defaultdict(list)
    for edge in session.scalars(select(RequisiteEdge).where(RequisiteEdge.course_id.in_(course_ids))):
        if edge.requisite_course_id is None:
            continue  # unresolved (external code or typo) -- can't draw an edge to nothing
        target_code = code_by_id.get(edge.requisite_course_id)
        if target_code is None:
            continue
        requisites_by_course[edge.course_id].append(CourseRequisite(type=edge.type, code=target_code))

    distinct_years = {
        slot_by_course[c.id].year_raw
        for c in courses
        if c.id in slot_by_course and slot_by_course[c.id].year_raw
    }
    year_data_reliable = not (
        len(courses) >= _UNRELIABLE_MIN_RECORDS and len(distinct_years) < _UNRELIABLE_MAX_DISTINCT_LABELS
    )

    catalog_courses = []
    for c in sorted(courses, key=lambda c: c.code):
        slot = slot_by_course.get(c.id)
        year_raw = slot.year_raw if slot else None
        catalog_courses.append(
            CatalogCourse(
                code=c.code,
                name=c.name,
                units=c.units or 0.0,
                is_zero_credit=c.is_zero_credit,
                year_raw=year_raw,
                year_number=_extract_year_number(year_raw),
                term=slot.term if slot else None,
                requisites=requisites_by_course.get(c.id, []),
            )
        )

    return ProgramCatalog(program=program_code, year_data_reliable=year_data_reliable, courses=catalog_courses)
