"""M5: cross-program course-code equivalencies + shiftee credit-mapping candidates.

Two different questions, both answered from parser/output/curricula.json
(not from your own knowledge yet -- that's applied later by a human
reviewing shiftee_credit_mappings.status):

1. course_code_equivalencies -- for a course *code* that appears in 2+
   programs, do its name/units/requisites actually agree everywhere, or
   does it quietly diverge? Fully derived, recomputed (upserted) on every
   run.
2. shiftee_credit_mappings -- candidate pairs of *different* codes that
   likely mean the same course in different programs (e.g. BSIT-CBL's
   CBPROG1 vs. most other programs' CCPROG1), found by exact name match
   across programs. A pair is dropped if any single program's curriculum
   already contains both codes (then they're clearly two distinct
   requirements, not the same course under two names -- e.g. NSTP-01 and
   NSTP-02 share a generic name but every program that has one has both).
   Every row starts at status="candidate" -- never asserted as fact, per
   the roadmap's "verify, don't assume identical". Rerunning only adds
   newly-found pairs; it never touches a row a human has already set to
   "confirmed" or "rejected".

Usage (from backend/, with .venv active):
    python -m app.seed_equivalencies [curricula.json path] [--database-url URL]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Base, CourseCodeEquivalency, ShifteeCreditMapping
from .seed import DEFAULT_CURRICULA_PATH, classify_elective

EXCLUDE_SHARED_NAMES = {"Generic Code for PE"}


def compute_code_equivalencies(records: list[dict]) -> list[dict]:
    by_code: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_code[record["code"]].append(record)

    rows = []
    for code, recs in sorted(by_code.items()):
        programs = sorted({r["program"] for r in recs})
        if len(programs) < 2:
            continue

        units = {r["units"] for r in recs}
        names = {r["name"] for r in recs if r["name"]}
        req_sets = {tuple(sorted((q["type"], q["code"]) for q in r["requisites"])) for r in recs}

        units_consistent = len(units) <= 1
        name_consistent = len(names) <= 1
        requisites_consistent = len(req_sets) <= 1

        notes = []
        if not units_consistent:
            notes.append(f"units differ: {sorted(str(u) for u in units)}")
        if not name_consistent:
            notes.append(f"names differ: {sorted(names)}")
        if not requisites_consistent:
            notes.append("requisites differ across programs -- see requisite_edges for this code")

        rows.append(
            {
                "code": code,
                "program_count": len(programs),
                "units_consistent": units_consistent,
                "name_consistent": name_consistent,
                "requisites_consistent": requisites_consistent,
                "notes": "; ".join(notes) or None,
            }
        )
    return rows


def compute_shiftee_candidates(records: list[dict]) -> list[dict]:
    by_name: dict[str, set[tuple[str, str]]] = defaultdict(set)
    codes_per_program: dict[str, set[str]] = defaultdict(set)

    for record in records:
        if classify_elective(record["code"]) is not None:
            continue
        name = record["name"].strip()
        if not name or name in EXCLUDE_SHARED_NAMES:
            continue
        by_name[name].add((record["program"], record["code"]))
        codes_per_program[record["program"]].add(record["code"])

    pairs: dict[tuple[str, str], dict] = {}
    for name, entries in by_name.items():
        codes = sorted({code for _, code in entries})
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                a, b = codes[i], codes[j]
                if any(a in codes_per_program[p] and b in codes_per_program[p] for p in codes_per_program):
                    continue  # coexist in one program's own curriculum -- not the same course
                bucket = pairs.setdefault((a, b), {"names": set(), "programs": set()})
                bucket["names"].add(name)
                bucket["programs"].update(p for p, c in entries if c in (a, b))

    rows = []
    for (code_a, code_b), info in sorted(pairs.items()):
        rows.append(
            {
                "code_a": code_a,
                "code_b": code_b,
                "shared_name": " / ".join(sorted(info["names"])),
                "notes": f"seen in: {', '.join(sorted(info['programs']))}",
            }
        )
    return rows


def seed_equivalencies(session: Session, records: list[dict]) -> tuple[int, int]:
    equivalency_rows = compute_code_equivalencies(records)
    existing_equivalencies = {row.code: row for row in session.scalars(select(CourseCodeEquivalency))}
    for row in equivalency_rows:
        existing = existing_equivalencies.get(row["code"])
        if existing is None:
            session.add(CourseCodeEquivalency(**row))
        else:
            for field, value in row.items():
                setattr(existing, field, value)

    candidate_rows = compute_shiftee_candidates(records)
    existing_pairs = {
        (row.code_a, row.code_b) for row in session.scalars(select(ShifteeCreditMapping))
    }
    inserted = 0
    for row in candidate_rows:
        key = (row["code_a"], row["code_b"])
        if key in existing_pairs:
            continue
        session.add(ShifteeCreditMapping(**row))
        inserted += 1

    session.commit()
    return len(equivalency_rows), inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("curricula_path", nargs="?", type=Path, default=DEFAULT_CURRICULA_PATH)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    database_url = args.database_url or get_settings().database_url
    if not database_url:
        print("no DATABASE_URL configured (set it in backend/.env or pass --database-url)", file=sys.stderr)
        raise SystemExit(1)

    if not args.curricula_path.exists():
        print(f"curricula.json not found at {args.curricula_path}", file=sys.stderr)
        raise SystemExit(1)

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    records = json.loads(args.curricula_path.read_text(encoding="utf-8"))

    with Session(engine) as session:
        equivalency_count, new_candidate_count = seed_equivalencies(session, records)

    print(f"course_code_equivalencies: {equivalency_count} codes (appearing in 2+ programs) upserted")
    print(f"shiftee_credit_mappings: {new_candidate_count} new candidate pair(s) inserted (existing rows left untouched)")


if __name__ == "__main__":
    main()
