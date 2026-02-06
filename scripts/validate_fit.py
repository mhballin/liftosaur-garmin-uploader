#!/usr/bin/env python3
"""Validate a FIT file using Garmin's FitCSVTool."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_MISSING_TOOL = 2


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fitcsvtool_path() -> Path:
    return _project_root() / "tools" / "FitCSVTool.jar"


def _default_output_csv(input_fit: Path) -> Path:
    return input_fit.with_suffix(".csv")


def _run_validation(input_fit: Path, output_csv: Path) -> subprocess.CompletedProcess[str]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a FIT file using FitCSVTool.")
    parser.add_argument("fit_file", type=Path, help="Path to the FIT file to validate.")
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        help="Keep the generated CSV output for inspection.",
    )
    args = parser.parse_args()

    input_fit = args.fit_file
    if not input_fit.exists():
        print(f"✗ FIT file not found: {input_fit}")
        return EXIT_INVALID

    tool_path = _fitcsvtool_path()
    if not tool_path.exists():
        print("✗ FitCSVTool.jar not found.")
        print(
            "Please download the Garmin FIT SDK and copy tools/FitCSVTool.jar into this project."
        )
        return EXIT_MISSING_TOOL

    output_csv: Path
    temp_output: Path | None = None
    if args.keep_csv:
        output_csv = _default_output_csv(input_fit)
    else:
        temp_file = tempfile.NamedTemporaryFile(prefix="fitcsv_", suffix=".csv", delete=False)
        temp_output = Path(temp_file.name)
        temp_file.close()
        output_csv = temp_output

    result = _run_validation(input_fit, output_csv)

    if result.returncode == 0:
        print("✓ FIT file is valid")
        print(f"CSV output: {output_csv}")
        exit_code = EXIT_OK
    else:
        print("✗ FIT file validation failed")
        if result.stdout:
            print("--- stdout ---")
            print(result.stdout.strip())
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr.strip())
        exit_code = EXIT_INVALID

    if not args.keep_csv and temp_output is not None:
        temp_output.unlink(missing_ok=True)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
