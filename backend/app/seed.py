"""M3: load parser/output/curricula.json into the schema in models.py.

Usage (from backend/, with .venv active):
    python -m app.seed [curricula.json path] [--database-url URL] [--reset]

Defaults to DATABASE_URL from .env (see app.config) and to
../parser/output/curricula.json. --reset drops and recreates all tables
first -- only meant for iterating on the schema before real data lands in
it, never point it at a database you care about keeping.

Requisite codes that don't resolve to exactly one course within the same
curriculum_version (an external exam-waiver code, a typo, or an ambiguous
duplicate-code match) are kept as raw text with a null resolved FK rather
than guessed -- see the printed exceptions log for the full list.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Base, Course, CourseSlot, CurriculumVersion, ElectiveSlot, Program, RequisiteEdge

DEFAULT_CURRICULA_PATH = Path(__file__).resolve().parent.parent.parent / "parser" / "output" / "curricula.json"

ELECTIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^LCC"), "GE"),
    (re.compile(r"ELEC\d*$"), "program_elective"),
]


def classify_elective(code: str) -> str | None:
    for pattern, category in ELECTIVE_PATTERNS:
        if pattern.search(code):
            return category
    return None


def seed(session: Session, records: list[dict]) -> list[str]:
    warnings: list[str] = []

    by_program: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_program[record["program"]].append(record)

    for program_code, program_records in sorted(by_program.items()):
        program = Program(code=program_code)
        session.add(program)
        session.flush()

        curriculum_version = CurriculumVersion(program_id=program.id, label="v1")
        session.add(curriculum_version)
        session.flush()

        courses_by_code: dict[str, list[Course]] = defaultdict(list)

        for record in program_records:
            category = classify_elective(record["code"])
            course = Course(
                curriculum_version_id=curriculum_version.id,
                code=record["code"],
                name=record["name"],
                units=record["units"],
                is_zero_credit=record["is_zero_credit"],
                is_elective_placeholder=category is not None,
            )
            session.add(course)
            session.flush()

            session.add(CourseSlot(course_id=course.id, year_raw=record["year"], term=record["term"]))
            if category is not None:
                session.add(ElectiveSlot(course_id=course.id, category=category))

            courses_by_code[record["code"]].append(course)

        for record in program_records:
            course = courses_by_code[record["code"]][0]
            for req in record["requisites"]:
                matches = courses_by_code.get(req["code"], [])
                requisite_course_id = None
                if len(matches) == 1:
                    requisite_course_id = matches[0].id
                elif len(matches) > 1:
                    warnings.append(
                        f"{program_code}/{record['code']}: requisite code {req['code']!r} matches "
                        f"{len(matches)} courses in this curriculum version (ambiguous, likely the "
                        f"duplicate-code data issue) -- left unresolved"
                    )
                else:
                    warnings.append(
                        f"{program_code}/{record['code']}: requisite code {req['code']!r} "
                        f"({req['type']}) doesn't match any course in this curriculum version -- "
                        f"kept as raw text, not linked"
                    )
                session.add(
                    RequisiteEdge(
                        course_id=course.id,
                        type=req["type"],
                        requisite_code=req["code"],
                        requisite_course_id=requisite_course_id,
                    )
                )

    session.commit()
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("curricula_path", nargs="?", type=Path, default=DEFAULT_CURRICULA_PATH)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = parser.parse_args()

    database_url = args.database_url or get_settings().database_url
    if not database_url:
        print("no DATABASE_URL configured (set it in backend/.env or pass --database-url)", file=sys.stderr)
        raise SystemExit(1)

    if not args.curricula_path.exists():
        print(f"curricula.json not found at {args.curricula_path}", file=sys.stderr)
        raise SystemExit(1)

    engine = create_engine(database_url)
    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    records = json.loads(args.curricula_path.read_text(encoding="utf-8"))

    with Session(engine) as session:
        warnings = seed(session, records)

    program_count = len({r["program"] for r in records})
    print(f"Seeded {program_count} program(s), {len(records)} course record(s) from {args.curricula_path}")
    if warnings:
        print(f"\n{len(warnings)} unresolved requisite reference(s):")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
