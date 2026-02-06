#!/usr/bin/env python3
"""Compare two FIT files by converting them to CSV with FitCSVTool."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_MISSING_TOOL = 2
EXIT_CONVERSION_FAILED = 3


IMPORTANT_FIELDS: dict[str, list[str]] = {
    "file_id": [
        "type",
        "manufacturer",
        "product",
        "garmin_product",
        "serial_number",
        "time_created",
    ],
    "session": [
        "timestamp",
        "start_time",
        "total_timer_time",
        "total_elapsed_time",
        "sport",
        "sub_sport",
        "total_calories",
        "num_laps",
    ],
    "activity": [
        "timestamp",
        "total_timer_time",
        "local_timestamp",
        "type",
        "event",
        "event_type",
    ],
    "sport": [
        "sport",
        "sub_sport",
        "name",
    ],
    "event": [
        "event",
        "event_type",
        "timestamp",
    ],
    "set": [
        "set_type",
        "duration",
        "repetitions",
        "weight",
        "category",
    ],
    "record": [
        "timestamp",
        "distance",
        "heart_rate",
        "cadence",
    ],
}


@dataclass
class FitCsvReport:
    types: dict[str, int]
    messages: dict[str, int]
    field_values: dict[str, dict[str, set[str]]]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fitcsvtool_path() -> Path:
    return _project_root() / "tools" / "FitCSVTool.jar"


def _run_fitcsvtool(input_fit: Path, output_csv: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "java",
            "-jar",
            str(_fitcsvtool_path()),
            "-b",
            str(input_fit),
            str(output_csv),
        ],
        capture_output=True,
        text=True,
    )


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _safe_str(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _column_lookup(headers: Iterable[str]) -> dict[str, str]:
    return {header.strip().lower(): header for header in headers}


def _find_column(headers: dict[str, str], candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in headers:
            return headers[key]
    return None


def _parse_field_pairs(headers: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for header in headers:
        header_lower = header.strip().lower()
        if header_lower.startswith("field "):
            suffix = header_lower.split(" ", 1)[1]
            value_header = None
            for candidate in (f"value {suffix}", f"value_{suffix}"):
                for existing in headers:
                    if existing.strip().lower() == candidate:
                        value_header = existing
                        break
                if value_header:
                    break
            if value_header:
                pairs.append((header, value_header))
    return pairs


def _load_report(csv_path: Path) -> FitCsvReport:
    types: dict[str, int] = {}
    messages: dict[str, int] = {}
    field_values: dict[str, dict[str, set[str]]] = {}

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return FitCsvReport(types=types, messages=messages, field_values=field_values)

        headers = _column_lookup(reader.fieldnames)
        type_col = _find_column(headers, ["type"])
        message_col = _find_column(headers, ["message", "mesg", "msg"])
        field_pairs = _parse_field_pairs(reader.fieldnames)

        for row in reader:
            if type_col:
                type_value = _safe_str(row.get(type_col, "")).strip()
                if type_value:
                    types[type_value] = types.get(type_value, 0) + 1

            message_name = ""
            if message_col:
                message_name = _safe_str(row.get(message_col, "")).strip()

            if message_name:
                messages[message_name] = messages.get(message_name, 0) + 1

            normalized_message = _normalize_name(message_name)
            if normalized_message in IMPORTANT_FIELDS and field_pairs:
                for field_col, value_col in field_pairs:
                    field_name = _safe_str(row.get(field_col, "")).strip()
                    if not field_name:
                        continue
                    normalized_field = _normalize_name(field_name)
                    if normalized_field not in IMPORTANT_FIELDS[normalized_message]:
                        continue
                    value = _safe_str(row.get(value_col, "")).strip()
                    if not value:
                        continue
                    field_values.setdefault(normalized_message, {}).setdefault(
                        normalized_field, set()
                    ).add(value)

    return FitCsvReport(types=types, messages=messages, field_values=field_values)


def _format_value_set(values: set[str]) -> str:
    if not values:
        return "(none)"
    sorted_values = sorted(values)
    if len(sorted_values) <= 5:
        return ", ".join(sorted_values)
    preview = ", ".join(sorted_values[:5])
    return f"{preview} (+{len(sorted_values) - 5} more)"


def _compare_counts(
    label: str,
    counts1: dict[str, int],
    counts2: dict[str, int],
) -> list[str]:
    lines: list[str] = []
    keys = sorted(set(counts1) | set(counts2))
    for key in keys:
        count1 = counts1.get(key)
        count2 = counts2.get(key)
        if count1 is not None and count2 is not None:
            if count1 == count2:
                lines.append(f"✓ Both files have {count1} {label} {key}")
            else:
                lines.append(f"✗ file1 has {count1} {label} {key}, file2 has {count2}")
        elif count1 is not None:
            lines.append(f"⚠ Only in file1: {label} {key} ({count1})")
        else:
            lines.append(f"⚠ Only in file2: {label} {key} ({count2})")
    return lines


def _compare_field_values(report1: FitCsvReport, report2: FitCsvReport) -> list[str]:
    lines: list[str] = []
    for message_name in sorted(set(report1.field_values) | set(report2.field_values)):
        fields1 = report1.field_values.get(message_name, {})
        fields2 = report2.field_values.get(message_name, {})
        for field_name in IMPORTANT_FIELDS.get(message_name, []):
            values1 = fields1.get(field_name, set())
            values2 = fields2.get(field_name, set())
            label = f"{message_name}.{field_name}"
            if values1 and values2:
                if values1 == values2:
                    lines.append(f"✓ Both files have {label}: {_format_value_set(values1)}")
                else:
                    lines.append(
                        "✗ file1 has {label}: {value1}, file2 has {value2}".format(
                            label=label,
                            value1=_format_value_set(values1),
                            value2=_format_value_set(values2),
                        )
                    )
            elif values1:
                lines.append(f"⚠ Only in file1: {label}: {_format_value_set(values1)}")
            elif values2:
                lines.append(f"⚠ Only in file2: {label}: {_format_value_set(values2)}")
    return lines


def _build_report(report1: FitCsvReport, report2: FitCsvReport) -> list[str]:
    lines: list[str] = []

    lines.append("Message type counts:")
    lines.extend(_compare_counts("rows of", report1.types, report2.types))

    lines.append("")
    lines.append("Message name counts:")
    lines.extend(_compare_counts("messages named", report1.messages, report2.messages))

    lines.append("")
    lines.append("Key field values:")
    lines.extend(_compare_field_values(report1, report2))

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two FIT files using Garmin FitCSVTool output."
    )
    parser.add_argument("file1", type=Path, help="First FIT file to compare.")
    parser.add_argument("file2", type=Path, help="Second FIT file to compare.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the comparison report.",
    )
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        help="Keep the generated CSV files for inspection.",
    )
    args = parser.parse_args()

    for fit_path in (args.file1, args.file2):
        if not fit_path.exists():
            print(f"✗ FIT file not found: {fit_path}")
            return EXIT_INVALID

    tool_path = _fitcsvtool_path()
    if not tool_path.exists():
        print("✗ FitCSVTool.jar not found.")
        print(
            "Please download the Garmin FIT SDK and copy tools/FitCSVTool.jar into this project."
        )
        return EXIT_MISSING_TOOL

    temp_files: list[Path] = []
    csv_paths: list[Path] = []

    for fit_path in (args.file1, args.file2):
        if args.keep_csv:
            csv_path = fit_path.with_suffix(".csv")
        else:
            temp_file = tempfile.NamedTemporaryFile(prefix="fitcsv_", suffix=".csv", delete=False)
            temp_files.append(Path(temp_file.name))
            temp_file.close()
            csv_path = temp_files[-1]
        csv_paths.append(csv_path)

    for fit_path, csv_path in zip((args.file1, args.file2), csv_paths, strict=True):
        result = _run_fitcsvtool(fit_path, csv_path)
        if result.returncode != 0:
            print(f"✗ FitCSVTool failed for: {fit_path}")
            if result.stdout:
                print("--- stdout ---")
                print(result.stdout.strip())
            if result.stderr:
                print("--- stderr ---")
                print(result.stderr.strip())
            if not args.keep_csv:
                for temp_path in temp_files:
                    temp_path.unlink(missing_ok=True)
            return EXIT_CONVERSION_FAILED

    report1 = _load_report(csv_paths[0])
    report2 = _load_report(csv_paths[1])

    report_lines = _build_report(report1, report2)
    report_text = "\n".join(report_lines)
    print(report_text)

    if args.output:
        args.output.write_text(report_text + "\n", encoding="utf-8")
        print(f"\nSaved report to: {args.output}")

    if not args.keep_csv:
        for temp_path in temp_files:
            temp_path.unlink(missing_ok=True)

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
