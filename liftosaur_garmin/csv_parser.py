"""CSV validation and grouping."""

from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .fit.utils import parse_iso

REQUIRED_CSV_COLUMNS = {
    "Workout DateTime",
    "Exercise",
    "Is Warmup Set?",
    "Completed Reps",
    "Completed Weight Value",
    "Completed Weight Unit",
    "Completed Reps Time",
    "Day Name",
}


def parse_csv_rows(rows: Iterable[dict]) -> list[dict]:
    """Validate and normalize CSV rows."""
    return list(rows)


def read_csv(filepath: Path) -> list[dict]:
    """Read and validate a Liftosaur CSV export."""
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    if filepath.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, got: {filepath.suffix}")

    rows: list[dict] = []
    with filepath.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV appears to be empty or has no header row.")

        actual = set(reader.fieldnames)
        missing = REQUIRED_CSV_COLUMNS - actual
        if missing:
            missing_list = ", ".join(sorted(missing))
            found_list = ", ".join(sorted(actual))
            raise ValueError(
                f"CSV is missing required columns: {missing_list}. "
                f"Found columns: {found_list}"
            )

        for row in reader:
            wdt = (row.get("Workout DateTime") or "").strip()
            if not wdt:
                continue
            try:
                parse_iso(wdt)
            except ValueError:
                continue
            rows.append(row)

    if not rows:
        raise ValueError("No valid rows found in CSV.")

    return rows


def group_workouts(rows: Iterable[dict]) -> OrderedDict[str, list[dict]]:
    """Group CSV rows by Workout DateTime, sorted by set completion time."""
    workouts: OrderedDict[str, list[dict]] = OrderedDict()
    for row in rows:
        wdt = (row.get("Workout DateTime") or "").strip()
        if not wdt:
            continue
        if wdt not in workouts:
            workouts[wdt] = []
        workouts[wdt].append(row)

    for wdt, sets in workouts.items():
        sets.sort(
            key=lambda r: (r.get("Completed Reps Time") or "")
            or (r.get("Workout DateTime") or "")
        )
        workouts[wdt] = sets

    return workouts
