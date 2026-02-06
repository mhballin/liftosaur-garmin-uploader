"""Validate reference FIT fixtures with Garmin's FitCSVTool."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = PROJECT_ROOT / "tools" / "FitCSVTool.jar"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "fit"


def _validate_fit_file(fit_path: Path) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_csv = Path(temp_dir) / f"{fit_path.stem}.csv"
        return subprocess.run(
            [
                "java",
                "-jar",
                str(TOOL_PATH),
                "-b",
                str(fit_path),
                str(output_csv),
            ],
            capture_output=True,
            text=True,
        )


def test_reference_fit_files_are_valid() -> None:
    if not TOOL_PATH.exists():
        pytest.skip("FitCSVTool.jar not found in tools/. Download the FIT SDK to run.")

    fit_files = [
        FIXTURES_DIR / "21779306834_ACTIVITY.fit",
        FIXTURES_DIR / "21783591203_ACTIVITY.fit",
    ]

    for fit_file in fit_files:
        assert fit_file.exists(), f"Missing fixture: {fit_file}"
        result = _validate_fit_file(fit_file)
        assert result.returncode == 0, (
            f"Validation failed for {fit_file}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
