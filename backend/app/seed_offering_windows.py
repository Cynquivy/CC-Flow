"""M4: populate course_offering_windows for every course already in the DB.

The flowchart only shows a course's canonical on-time slot -- whether it
can actually be taken off-schedule (every term / T1 only / etc.) is
domain knowledge the user provides directly, not something in the parsed
data. This seeds every course as "unknown" except for known-code
overrides below (currently just LCC..NN, per the user: GE electives
aren't sequenced, so they can be taken any term). Extend
_classify_offering_window as more of that domain knowledge comes in.

Requires M3's courses table to already be populated (this reads existing
Course rows, not curricula.json).

Usage (from backend/, with .venv active):
    python -m app.seed_offering_windows [--database-url URL] [--overwrite-unknown]

--overwrite-unknown re-applies _classify_offering_window to rows still
sitting at "unknown" (e.g. after adding a new override rule below) --
it never touches a row already set to anything else, since that's
assumed to be an intentional/manual edit.
"""

from __future__ import annotations

import argparse
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Base, Course, CourseOfferingWindow


def _classify_offering_window(code: str) -> tuple[str, str | None]:
    if re.match(r"^LCC", code):
        return "every_term", "Lasallian Core Curriculum (GE) -- not sequenced, can be taken any term"
    return "unknown", None


def seed_offering_windows(session: Session, overwrite_unknown: bool) -> tuple[int, int, int]:
    """Returns (inserted, updated, skipped) counts."""
    existing_by_course_id = {
        row.course_id: row for row in session.scalars(select(CourseOfferingWindow))
    }

    inserted = updated = skipped = 0
    for course in session.scalars(select(Course)):
        window, notes = _classify_offering_window(course.code)
        existing = existing_by_course_id.get(course.id)

        if existing is None:
            session.add(CourseOfferingWindow(course_id=course.id, offering_window=window, notes=notes))
            inserted += 1
        elif overwrite_unknown and existing.offering_window == "unknown" and window != "unknown":
            existing.offering_window = window
            existing.notes = notes
            updated += 1
        else:
            skipped += 1

    session.commit()
    return inserted, updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--overwrite-unknown", action="store_true")
    args = parser.parse_args()

    database_url = args.database_url or get_settings().database_url
    if not database_url:
        print("no DATABASE_URL configured (set it in backend/.env or pass --database-url)", file=sys.stderr)
        raise SystemExit(1)

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        inserted, updated, skipped = seed_offering_windows(session, args.overwrite_unknown)

    print(f"course_offering_windows: {inserted} inserted, {updated} updated, {skipped} already set (left alone)")


if __name__ == "__main__":
    main()
