"""Exercises the None/TBA/multi-code-requisite handling that CS-ST.txt's
data happens not to contain (it was already pre-split), but that other
flowchart files may still need now that M2 generalizes this parser across
all 11 programs -- plus M2's program-tagging and year-label-coverage
checks.

Run with: python test_parse_flowchart.py
"""

from parse_flowchart import parse_flowchart
import json
import tempfile
from pathlib import Path

SAMPLE_LINES = [
    # comma-joined requisite code, as in the raw "h: MTH101A, BASMATH" notation
    json.dumps({
        "code": "MTH101A", "name": "Foundation Course in Mathematics", "units": 5.0,
        "is_zero_credit": False, "year": "Year 1", "term": 1,
        "requisites": [{"type": "hard", "code": "MTH101A, BASMATH"}],
    }),
    # units/term given as "TBA"
    json.dumps({
        "code": "STELECX", "name": "ST Elective X", "units": "TBA",
        "is_zero_credit": False, "year": "Year 4", "term": "TBA",
        "requisites": [],
    }),
    # requisite code literally "None" should be dropped, not kept as a fake requisite
    json.dumps({
        "code": "CCICOMP", "name": "Introduction to Computing", "units": 3.0,
        "is_zero_credit": False, "year": "Year 1", "term": 2,
        "requisites": [{"type": "hard", "code": "None"}],
    }),
    "this is not valid json",
]


SAMPLE_LINES_MANY_YEARS = [
    json.dumps({
        "code": f"CODE{i:02d}", "name": f"Course {i}", "units": 3.0,
        "is_zero_credit": False, "year": f"Year {(i % 4) + 1}", "term": (i % 3) + 1,
        "requisites": [],
    })
    for i in range(32)
]

SAMPLE_LINES_COLLAPSED_YEARS = [
    json.dumps({
        "code": f"CODE{i:02d}", "name": f"Course {i}", "units": 3.0,
        "is_zero_credit": False, "year": f"Year {(i % 2) + 1}", "term": (i % 3) + 1,
        "requisites": [],
    })
    for i in range(32)
]


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "sample.txt"
        input_path.write_text("\n".join(SAMPLE_LINES), encoding="utf-8")

        records, warnings = parse_flowchart(input_path)

        by_code = {r["code"]: r for r in records}

        assert by_code["MTH101A"]["requisites"] == [
            {"type": "hard", "code": "MTH101A"},
            {"type": "hard", "code": "BASMATH"},
        ], "comma-joined requisite code should split into two entries"

        assert by_code["STELECX"]["units"] is None, "'TBA' units should become null"
        assert by_code["STELECX"]["term"] is None, "'TBA' term should become null"

        assert by_code["CCICOMP"]["requisites"] == [], "'None' requisite code should be dropped"

        assert len(records) == 3, "the malformed JSON line should be skipped, not crash the parse"
        assert any("invalid JSON" in w for w in warnings)
        assert any("'TBA'" in w for w in warnings)

        assert all(r["program"] == "sample" for r in records), (
            "every record should be tagged with the input file's stem as its program"
        )

    with tempfile.TemporaryDirectory() as tmp:
        many_years_path = Path(tmp) / "BSMANY.txt"
        many_years_path.write_text("\n".join(SAMPLE_LINES_MANY_YEARS), encoding="utf-8")
        _, many_years_warnings = parse_flowchart(many_years_path)
        assert not any("distinct 'year' label" in w for w in many_years_warnings), (
            "a program with 4 distinct year labels shouldn't trigger the collapsed-years warning"
        )

        collapsed_path = Path(tmp) / "BSCOLLAPSED.txt"
        collapsed_path.write_text("\n".join(SAMPLE_LINES_COLLAPSED_YEARS), encoding="utf-8")
        _, collapsed_warnings = parse_flowchart(collapsed_path)
        assert any("distinct 'year' label" in w for w in collapsed_warnings), (
            "a program with only 2 distinct year labels across 30+ records should be flagged"
        )

    print("All assertions passed.")


if __name__ == "__main__":
    run()
