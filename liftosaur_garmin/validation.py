"""FIT validation helpers using Garmin's FitCSVTool.jar.

This module provides a reusable validation function so the CLI and
other tools can validate a FIT file without duplicating subprocess logic.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fitcsvtool_path() -> Path:
    return _project_root() / "tools" / "FitCSVTool.jar"


def _run_fitcsvtool(input_fit: Path, output_csv: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "java",
            "-jar",
            str(fitcsvtool_path()),
            "-b",
            str(input_fit),
            str(output_csv),
        ],
        capture_output=True,
        text=True,
    )


def validate_fit_file(input_fit: Path, keep_csv: bool = False) -> Tuple[Optional[bool], Optional[subprocess.CompletedProcess[str]]]:
    """Validate a FIT file using FitCSVTool.

    Returns a tuple (status, result) where status is:
      - True: validation passed (exit code 0)
      - False: validation failed (non-zero exit code)
      - None: FitCSVTool.jar not found (validation skipped)

    `result` is the CompletedProcess from the validation run when executed,
    otherwise ``None``.
    """
    tool_path = fitcsvtool_path()
    if not tool_path.exists():
        logger.debug(f"FitCSVTool.jar not found at {tool_path}")
        return None, None

    # Decide where to write CSV output
    if keep_csv:
        output_csv = input_fit.with_suffix(".csv")
        logger.debug(f"Validating {input_fit} -> {output_csv}")
        result = _run_fitcsvtool(input_fit, output_csv)
        status = result.returncode == 0
        logger.debug(f"Validation {'passed' if status else 'failed'} (exit code {result.returncode})")
        return status, result

    temp_file = tempfile.NamedTemporaryFile(prefix="fitcsv_", suffix=".csv", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    try:
        logger.debug(f"Validating {input_fit}")
        result = _run_fitcsvtool(input_fit, temp_path)
        status = result.returncode == 0
        logger.debug(f"Validation {'passed' if status else 'failed'} (exit code {result.returncode})")
        return status, result
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
