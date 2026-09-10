"""M2: generalize parse_flowchart.py across all CCS program flowchart files.

Reads every `.txt` file in flowchart_records_11programs/ (one file per
program), tags each parsed course record with its source program (via
parse_flowchart.py's filename-stem tagging), merges every program's
records into one curricula.json, and writes a consolidated exceptions
log of everything the parser flagged instead of guessed.

Usage:
    python parse_all_flowcharts.py [records_dir] [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from parse_flowchart import parse_flowchart

DEFAULT_RECORDS_DIR = Path(__file__).resolve().parent.parent / "flowchart_records_11programs"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> None:
    records_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RECORDS_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(records_dir.glob("*.txt"))
    if not paths:
        print(f"no .txt files found in {records_dir}", file=sys.stderr)
        raise SystemExit(1)

    all_records: list[dict] = []
    log_lines: list[str] = []
    summary_rows: list[tuple[str, int, float, int]] = []

    for path in paths:
        records, warnings = parse_flowchart(path)
        all_records.extend(records)

        total_units = sum(r["units"] for r in records if r["units"] is not None)
        summary_rows.append((path.stem, len(records), total_units, len(warnings)))

        log_lines.append(f"=== {path.stem} ({len(records)} courses, {len(warnings)} warning(s)) ===")
        if warnings:
            log_lines.extend(f"  - {w}" for w in warnings)
        else:
            log_lines.append("  (no warnings)")
        log_lines.append("")

    output_path = output_dir / "curricula.json"
    output_path.write_text(json.dumps(all_records, indent=2), encoding="utf-8")

    exceptions_path = output_dir / "exceptions_log.txt"
    exceptions_path.write_text("\n".join(log_lines), encoding="utf-8")

    total_warnings = sum(row[3] for row in summary_rows)
    print(f"Parsed {len(paths)} program(s), {len(all_records)} course record(s) total -> {output_path}")
    print(f"Exceptions log ({total_warnings} total warning(s)) -> {exceptions_path}")
    print()
    print(f"{'program':<12} {'courses':>7} {'total units':>12} {'warnings':>9}")
    for program, count, total_units, warn_count in summary_rows:
        print(f"{program:<12} {count:>7} {total_units:>12.1f} {warn_count:>9}")

    print(
        "\nNote: no source PDFs / printed 'Total units' lines are present in this repo "
        "(flowchart_records_11programs/ holds pre-parsed JSON-lines, not raw PDF text) -- "
        "the totals above are computed from the parsed records only and haven't been "
        "cross-checked against a flowchart-printed total. Spot-check them manually against "
        "the source flowcharts if you have them."
    )


if __name__ == "__main__":
    main()
