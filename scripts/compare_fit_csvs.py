#!/usr/bin/env python3
"""Compare two FIT files by converting them to CSV using FitCSVTool."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


try:
    import pandas as pd  # type: ignore

    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False


def _run_fit_csv_tool(fit_path: Path, jar_path: Path, output_dir: Path) -> None:
    """Run FitCSVTool.jar to export CSV files for a FIT file."""
    command = [
        "java",
        "-jar",
        str(jar_path),
        "-b",
        str(fit_path),
        f"{output_dir}/",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"FitCSVTool failed for {fit_path.name}: {error_message or 'Unknown error'}"
        )


def _find_monolithic_csv(directory: Path) -> Path:
    csv_files = sorted(path for path in directory.glob("*.csv") if path.is_file())
    if not csv_files:
        raise RuntimeError(f"No CSV files found in {directory}")
    if len(csv_files) > 1:
        raise RuntimeError(
            f"Expected one CSV file in {directory}, found {len(csv_files)}"
        )
    return csv_files[0]


def _read_csv_with_pandas(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    header = [str(col) for col in df.columns]
    rows = df.astype(str).values.tolist()
    return header, rows


def _read_csv_with_csv_module(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        return [], []

    header = rows[0]
    data_rows = rows[1:]
    return header, data_rows


def _read_monolithic_csv(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    if HAS_PANDAS:
        return _read_csv_with_pandas(csv_path)
    return _read_csv_with_csv_module(csv_path)


def _find_column_index(header: list[str], column_name: str) -> int | None:
    if column_name in header:
        return header.index(column_name)
    lower_map = {name.lower(): idx for idx, name in enumerate(header)}
    return lower_map.get(column_name.lower())


def _extract_field_triplets(header: list[str]) -> list[tuple[int, int | None, int | None]]:
    triplets: list[tuple[int, int | None, int | None]] = []
    index_map = {name: idx for idx, name in enumerate(header)}
    for name, idx in index_map.items():
        if not name.startswith("Field "):
            continue
        suffix = name.removeprefix("Field ")
        value_idx = index_map.get(f"Value {suffix}")
        units_idx = index_map.get(f"Units {suffix}")
        triplets.append((idx, value_idx, units_idx))
    return sorted(triplets, key=lambda item: item[0])


def _row_value(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _format_row(header: list[str], row: list[str]) -> str:
    type_idx = _find_column_index(header, "Type")
    local_idx = _find_column_index(header, "Local Number")
    message_idx = _find_column_index(header, "Message")

    base_parts = []
    if type_idx is not None:
        type_value = _row_value(row, type_idx)
        if type_value:
            base_parts.append(f"Type={type_value}")
    if local_idx is not None:
        local_value = _row_value(row, local_idx)
        if local_value:
            base_parts.append(f"Local={local_value}")
    if message_idx is not None:
        message_value = _row_value(row, message_idx)
        if message_value:
            base_parts.append(f"Message={message_value}")

    field_parts: list[str] = []
    for field_idx, value_idx, units_idx in _extract_field_triplets(header):
        field_name = _row_value(row, field_idx)
        if not field_name:
            continue
        value = _row_value(row, value_idx)
        units = _row_value(row, units_idx)
        if units:
            field_parts.append(f"{field_name}={value} {units}")
        else:
            field_parts.append(f"{field_name}={value}")

    if field_parts:
        return f"{' | '.join(base_parts)} | {', '.join(field_parts)}"
    return " | ".join(base_parts) if base_parts else ", ".join(row)


def _format_rows(header: list[str], rows: Iterable[list[str]], limit: int = 3) -> str:
    rows_list = list(rows)
    if not rows_list:
        return "(no rows)"

    first = rows_list[:limit]
    last = rows_list[-limit:] if len(rows_list) > limit else []
    output_lines: list[str] = []
    for row in first:
        output_lines.append(_format_row(header, row))

    if last and last != first:
        output_lines.append("...")
        for row in last:
            output_lines.append(_format_row(header, row))

    return "\n".join(output_lines)


def _group_rows_by_message(
    header: list[str], rows: list[list[str]]
) -> dict[str, list[list[str]]]:
    message_idx = _find_column_index(header, "Message")
    if message_idx is None:
        raise RuntimeError("CSV is missing the 'Message' column")

    grouped: dict[str, list[list[str]]] = {}
    for row in rows:
        message = _row_value(row, message_idx) or "(blank)"
        grouped.setdefault(message, []).append(row)
    return grouped


def compare_fit_files(
    file1_path: str,
    file2_path: str,
    jar_path: str = "tools/FitCSVTool.jar",
    output_path: str | None = None,
    verbose: bool = False,
) -> None:
    """Compare two FIT files by converting them to CSV and analyzing differences."""
    fit1 = Path(file1_path)
    fit2 = Path(file2_path)
    jar = Path(jar_path)

    if not jar.exists():
        print(f"❌ FitCSVTool.jar not found at {jar}")
        sys.exit(1)

    if not fit1.exists():
        print(f"❌ FIT file not found: {fit1}")
        sys.exit(1)

    if not fit2.exists():
        print(f"❌ FIT file not found: {fit2}")
        sys.exit(1)

    output_dir = Path("tests/output/comparisons")
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path:
        comparison_path = Path(output_path)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison_path = output_dir / f"fit_comparison_{timestamp}.txt"

    with tempfile.TemporaryDirectory() as temp_dir_1, tempfile.TemporaryDirectory() as temp_dir_2:
        csv_dir_1 = Path(temp_dir_1)
        csv_dir_2 = Path(temp_dir_2)

        try:
            _run_fit_csv_tool(fit1, jar, csv_dir_1)
            _run_fit_csv_tool(fit2, jar, csv_dir_2)
        except RuntimeError as exc:
            print(f"❌ {exc}")
            sys.exit(1)

        csv1 = _find_monolithic_csv(csv_dir_1)
        csv2 = _find_monolithic_csv(csv_dir_2)

        header1, rows1 = _read_monolithic_csv(csv1)
        header2, rows2 = _read_monolithic_csv(csv2)

        grouped1 = _group_rows_by_message(header1, rows1)
        grouped2 = _group_rows_by_message(header2, rows2)

        message_types = sorted(set(grouped1) | set(grouped2))
        only1 = sorted(set(grouped1) - set(grouped2))
        only2 = sorted(set(grouped2) - set(grouped1))

        output_lines: list[str] = []
        output_lines.append("=== MESSAGE TYPE COUNTS ===")
        for message in message_types:
            count1 = len(grouped1.get(message, []))
            count2 = len(grouped2.get(message, []))
            output_lines.append(f"{message}: file1={count1}, file2={count2}")

        output_lines.append("")
        output_lines.append("=== MISSING MESSAGE TYPES ===")
        output_lines.append(
            f"Only in file1: {', '.join(only1) if only1 else '(none)'}"
        )
        output_lines.append(
            f"Only in file2: {', '.join(only2) if only2 else '(none)'}"
        )

        for message in message_types:
            output_lines.append("")
            output_lines.append(f"=== SAMPLE DATA: {message} ===")
            rows_for_message_1 = grouped1.get(message, [])
            rows_for_message_2 = grouped2.get(message, [])
            output_lines.append("File1:")
            output_lines.append(_format_rows(header1, rows_for_message_1, limit=3))
            output_lines.append("File2:")
            output_lines.append(_format_rows(header2, rows_for_message_2, limit=3))

        comparison_path.write_text("\n".join(output_lines), encoding="utf-8")

        print("✔ FIT comparison complete")
        print(f"Output: {comparison_path}")
        if verbose:
            print("Message counts:")
            for message in message_types:
                count1 = len(grouped1.get(message, []))
                count2 = len(grouped2.get(message, []))
                print(f"- {message}: file1={count1}, file2={count2}")
            print(
                f"Missing types: file1={', '.join(only1) if only1 else '(none)'}, "
                f"file2={', '.join(only2) if only2 else '(none)'}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare two FIT files via FitCSVTool CSV export."
    )
    parser.add_argument("file1", help="Path to the first FIT file")
    parser.add_argument("file2", help="Path to the second FIT file")
    parser.add_argument(
        "--output",
        help="Optional output path for comparison text file",
        default=None,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print message counts to console in addition to summary",
    )
    args = parser.parse_args()
    compare_fit_files(args.file1, args.file2, output_path=args.output, verbose=args.verbose)
