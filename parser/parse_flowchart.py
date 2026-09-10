"""Parse one CCS flowchart record file into normalized course JSON.

Generalized in M2 to all 11 programs under flowchart_records_11programs/
(see parse_all_flowcharts.py for the multi-file driver); built in M1
against CS-ST only. Each input line is already a JSON object roughly
matching the target schema (whatever produced these .txt files already
split the flowchart's "h: CODE1, CODE2" requisite notation into
structured entries). This script still defends against the raw notation
described in the project roadmap -- None/TBA placeholders and
comma-joined multi-code requisites -- in case a future flowchart file
isn't pre-split.

Every parsed record is tagged with a "program" field (the input
filename's stem, e.g. "CS-ST") so records from different programs can be
merged into one curricula.json without losing their source.

Usage:
    python parse_flowchart.py <input.txt> [output.json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VALID_REQ_TYPES = {"hard", "soft", "coreq", "exemption"}
NULLISH = {"", "none", "tba", "n/a"}
REQUIRED_FIELDS = {"code", "name", "units", "is_zero_credit", "year", "term", "requisites"}


class ParseIssue(Exception):
    pass


def _clean_code(raw: str) -> str | None:
    code = raw.strip()
    return None if code.lower() in NULLISH else code


def _normalize_requisites(raw_requisites: list, line_no: int, warnings: list[str]) -> list[dict]:
    """Expand each requisite entry into one-or-more {type, code} dicts.

    Splits a comma-joined code (the raw "h: MTH101A, BASMATH" notation,
    if it ever survives as a single string) into separate entries, and
    drops None/TBA placeholders.
    """
    normalized: list[dict] = []
    for entry in raw_requisites:
        req_type = str(entry.get("type", "")).strip().lower()
        if req_type not in VALID_REQ_TYPES:
            warnings.append(f"line {line_no}: unknown requisite type {entry.get('type')!r}")
        for raw_code in str(entry.get("code", "")).split(","):
            code = _clean_code(raw_code)
            if code is not None:
                normalized.append({"type": req_type, "code": code})
    return normalized


def parse_record(
    raw_line: str, line_no: int, warnings: list[str], program: str | None = None
) -> dict | None:
    line = raw_line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ParseIssue(f"line {line_no}: invalid JSON ({exc})") from exc

    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ParseIssue(f"line {line_no}: missing field(s) {sorted(missing)}")

    code = _clean_code(str(data["code"]))
    if code is None:
        raise ParseIssue(f"line {line_no}: missing course code")

    name = str(data["name"]).strip()
    if not name:
        warnings.append(f"line {line_no} ({code}): empty course name")

    if code.startswith("LCC") and not re.fullmatch(r"LCC\.\.\d{2}", code):
        warnings.append(f"line {line_no} ({code}): LCC code doesn't match the 'LCC..NN' pattern")

    units_raw = data["units"]
    if isinstance(units_raw, str) and units_raw.strip().lower() in NULLISH:
        units = None
        warnings.append(f"line {line_no} ({code}): units is {units_raw!r}, recorded as null")
    else:
        units = float(units_raw)

    term_raw = data["term"]
    if isinstance(term_raw, str) and term_raw.strip().lower() in NULLISH:
        term = None
        warnings.append(f"line {line_no} ({code}): term is {term_raw!r}, recorded as null")
    else:
        term = int(term_raw)

    return {
        "program": program,
        "code": code,
        "name": name,
        "units": units,
        "is_zero_credit": bool(data["is_zero_credit"]),
        "year": data["year"],
        "term": term,
        "requisites": _normalize_requisites(data.get("requisites") or [], line_no, warnings),
    }


def _check_year_label_coverage(records: list[dict], warnings: list[str]) -> None:
    """Flag programs whose 'year' labels look collapsed rather than genuinely few.

    Across the 11 known programs, curricula with 40+ courses print 4-5
    distinct year labels (e.g. "Year 1 (AY 2025-2026)" .. "Year 4 ..."). A
    handful of files instead show only 2 distinct labels covering the same
    course-count range, which is more likely an upstream extraction defect
    (e.g. a 2-column page layout zipped into one label per column) than a
    real 2-year curriculum. This can't be corrected here -- flag it instead
    of guessing which records belong to which real year.
    """
    distinct_years = {r["year"] for r in records if r["year"] is not None}
    if len(records) >= 30 and len(distinct_years) < 3:
        warnings.append(
            f"only {len(distinct_years)} distinct 'year' label(s) across {len(records)} records "
            f"({sorted(distinct_years)}) -- other programs of comparable size show 4-5 distinct "
            f"year labels. Likely an upstream extraction defect that collapsed multiple curriculum "
            f"years into one label; verify against the source flowchart manually, don't infer."
        )


def parse_flowchart(path: Path) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    records: list[dict] = []
    seen_at: dict[str, int] = {}
    program = path.stem

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = parse_record(raw_line, line_no, warnings, program=program)
        except ParseIssue as exc:
            warnings.append(str(exc))
            continue
        if record is None:
            continue

        if record["code"] in seen_at:
            warnings.append(
                f"line {line_no}: duplicate course code {record['code']!r} "
                f"(first seen on line {seen_at[record['code']]})"
            )
        else:
            seen_at[record["code"]] = line_no
        records.append(record)

    _check_year_label_coverage(records, warnings)
    return records, warnings


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python parse_flowchart.py <input.txt> [output.json]", file=sys.stderr)
        raise SystemExit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output") / f"{input_path.stem.lower().replace('-', '_')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records, warnings = parse_flowchart(input_path)
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print(f"Parsed {len(records)} course record(s) from {input_path} -> {output_path}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
