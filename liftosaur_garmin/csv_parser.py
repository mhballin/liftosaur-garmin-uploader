"""CSV validation and grouping."""

from __future__ import annotations

import csv
import errno
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .fit.utils import parse_iso

logger = logging.getLogger(__name__)

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


def parse_csv(filepath: Path, workout_datetime: str | None = None) -> list[dict]:
    """Read and validate a Liftosaur CSV export."""
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    if filepath.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, got: {filepath.suffix}")

    rows: list[dict] = []
    max_attempts = 10  # More attempts for cloud-synced files (iCloud Drive)
    delay_seconds = 1.0  # Longer initial delay for cloud synchronization
    for attempt in range(1, max_attempts + 1):
        try:
            with filepath.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                # Try to access fieldnames, which may raise OSError during header read
                try:
                    fieldnames = reader.fieldnames
                except OSError as exc2:
                    # Some platforms (or Python versions) raise OSError without
                    # setting errno; detect the resource-deadlock message text
                    # and retry similarly to the outer OSError handler.
                    is_deadlock_field = (
                        getattr(exc2, "errno", None) == errno.EDEADLK
                        or getattr(exc2, "errno", None) == errno.EAGAIN
                        or "Resource deadlock avoided" in str(exc2)
                    )
                    if is_deadlock_field and attempt < max_attempts:
                        time.sleep(delay_seconds * attempt)
                        raise  # Re-raise original exception to outer handler
                    raise

                if fieldnames is None:
                    raise ValueError("CSV appears to be empty or has no header row.")

                actual = set(fieldnames)
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
                        logger.debug(f"Skipping row with invalid datetime: {wdt}")
                        continue
                    if workout_datetime and wdt != workout_datetime:
                        continue
                    rows.append(row)
            break
        except OSError as exc:
            is_deadlock = (
                getattr(exc, "errno", None) == errno.EDEADLK
                or getattr(exc, "errno", None) == errno.EAGAIN
                or "Resource deadlock avoided" in str(exc)
            )
            if is_deadlock and attempt < max_attempts:
                time.sleep(delay_seconds * attempt)
                continue
            raise

    if not rows:
        raise ValueError("No valid rows found in CSV.")

    logger.debug(f"Parsed {len(rows)} rows from {filepath}")
    return rows


def read_csv(filepath: Path) -> list[dict]:
    """Compatibility wrapper for CSV parsing."""
    return parse_csv(filepath)


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
