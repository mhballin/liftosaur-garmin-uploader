"""CSV validation and grouping."""

from __future__ import annotations

import csv
import logging
import platform
import shutil
import subprocess
import time
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .config import cleanup_old_temp_files, get_temp_dir, load_config
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

# iCloud stub files appear as ".filename.icloud" in the parent directory
# when the real file data hasn't been downloaded locally yet.
_ICLOUD_STUB_XATTR = b"com.apple.icloud.itemName"


def _coordinated_copy(src: Path, dst: Path) -> bool:
    """Copy a file using macOS file coordination if available.

    Returns True if the coordinated copy succeeded, False if not supported or failed.
    """
    if platform.system() != "Darwin":
        return False
    try:
        import Foundation  # type: ignore
    except Exception:
        return False

    try:
        url = Foundation.NSURL.fileURLWithPath_(str(src))
        coordinator = Foundation.NSFileCoordinator.alloc().initWithFilePresenter_(None)
    except Exception:
        return False

    def accessor(read_url) -> None:
        shutil.copy2(str(read_url.path()), dst)

    try:
        result = coordinator.coordinateReadingItemAtURL_options_error_byAccessor_(
            url,
            0,
            None,
            accessor,
        )
    except Exception as exc:
        logger.debug(f"NSFileCoordinator copy failed: {exc}")
        return False

    if isinstance(result, tuple):
        _, error = result
        if error is not None:
            logger.debug(f"NSFileCoordinator copy error: {error}")
            return False

    return dst.exists()


def _is_icloud_path(filepath: Path) -> bool:
    """Return True if the file lives inside an iCloud Drive directory."""
    try:
        icloud_root = Path(
            "~/Library/Mobile Documents/com~apple~CloudDocs"
        ).expanduser()
        return filepath.is_relative_to(icloud_root)
    except (ValueError, Exception):
        return False


def _stub_exists(filepath: Path) -> bool:
    """Return True if a .icloud stub file exists for this path (file not local yet)."""
    stub = filepath.parent / f".{filepath.name}.icloud"
    return stub.exists()


def _file_is_local(filepath: Path) -> bool:
    """Return True if the file is fully downloaded locally.

    Checks for the presence of the .icloud stub (which replaces the real file
    when iCloud has evicted it), and verifies the file has non-zero size.
    """
    # Stub present = real file is cloud-only, not downloaded
    if _stub_exists(filepath):
        return False

    # File must exist and have content
    try:
        if filepath.stat().st_size == 0:
            return False
    except OSError:
        return False

    # Optionally check xattr if the xattr package is available
    try:
        import xattr  # type: ignore
        attrs = xattr.listxattr(str(filepath))
        for attr in attrs:
            name = attr if isinstance(attr, str) else attr.decode("utf-8", errors="replace")
            if "com.apple.icloud.itemName" in name:
                return False
    except ImportError:
        pass  # xattr not installed — stub check above is sufficient
    except Exception:
        pass

    return True


def ensure_icloud_downloaded(filepath: Path, timeout: float = 60.0) -> None:
    """Ensure an iCloud Drive file is fully downloaded before reading.

    Calls ``brctl download`` to trigger iCloud to fetch the file, then polls
    until the file is confirmed local or the timeout expires.

    This prevents ``OSError: [Errno 11] Resource deadlock avoided`` which
    occurs when macOS hands Python a cloud-stub file that hasn't been
    materialised yet.

    This function is a no-op on non-macOS platforms and for files that are
    not inside iCloud Drive.
    """
    if platform.system() != "Darwin":
        return
    if not _is_icloud_path(filepath):
        return
    if _file_is_local(filepath):
        logger.debug(f"iCloud file already local: {filepath.name}")
        return

    logger.info(
        f"File is an iCloud stub — requesting download: {filepath.name}"
    )

    # Ask iCloud to download the file
    try:
        result = subprocess.run(
            ["brctl", "download", str(filepath)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                f"brctl download returned {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        else:
            logger.debug("brctl download command accepted")
    except FileNotFoundError:
        logger.warning(
            "brctl not found — cannot force iCloud download. "
            "The file may still download on its own."
        )
    except subprocess.TimeoutExpired:
        logger.warning("brctl download timed out after 10s — continuing to poll")

    # Poll until file is local or we give up
    deadline = time.monotonic() + timeout
    poll_interval = 2.0
    while time.monotonic() < deadline:
        if _file_is_local(filepath):
            logger.info(f"iCloud file is now local: {filepath.name}")
            return
        remaining = int(deadline - time.monotonic())
        logger.debug(f"Waiting for iCloud download... ({remaining}s remaining)")
        time.sleep(poll_interval)

    raise TimeoutError(
        f"iCloud file was not downloaded within {timeout:.0f}s: {filepath}\n"
        "Check your internet connection or open the file in Finder to trigger download."
    )


def parse_csv(filepath: Path, workout_datetime: str | None = None, profile_dir: Path | None = None) -> list[dict]:
    """Read and validate a Liftosaur CSV export.

    If profile_dir is provided and the file is in iCloud Drive, the file will be
    copied to a temp directory to avoid coordination lock issues. The temp copy
    will be parsed instead of the original.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    if filepath.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, got: {filepath.suffix}")

    # Ensure the file is fully downloaded from iCloud before attempting to read.
    # This prevents [Errno 11] Resource deadlock avoided on cloud-stub files.
    # Must do this FIRST, before attempting to copy, so brctl can release locks.
    ensure_icloud_downloaded(filepath)

    # For iCloud files with profile context, copy to temp to avoid deadlock.
    # Note: We do this AFTER ensure_icloud_downloaded() so locks have time to release.
    parse_filepath = filepath
    if profile_dir and _is_icloud_path(filepath):
        temp_dir = get_temp_dir(profile_dir)
        temp_path = temp_dir / f"{filepath.stem}_temp.csv"
        attempt = 0
        delay = 1.0
        while True:
            try:
                # Add a small grace period to let iCloud coordination locks fully release
                time.sleep(delay if attempt > 0 else 1.0)
                if _coordinated_copy(filepath, temp_path):
                    logger.debug(
                        f"Copied iCloud file to temp via NSFileCoordinator: {temp_path.name}"
                    )
                else:
                    shutil.copy2(filepath, temp_path)
                    logger.debug(f"Copied iCloud file to temp: {temp_path.name}")
                parse_filepath = temp_path
                break
            except OSError as exc:
                if getattr(exc, "errno", None) == 11:
                    attempt += 1
                    if attempt >= 5:
                        raise ValueError(
                            "iCloud file is still locked after multiple attempts; "
                            "please try again in a moment."
                        ) from exc
                    logger.debug(
                        f"iCloud file locked; retrying temp copy in {delay:.0f}s (attempt {attempt}/5)"
                    )
                    delay = min(delay * 2, 8.0)
                    continue
                logger.warning(
                    f"Failed to copy iCloud file to temp; will try original: {exc}"
                )
                parse_filepath = filepath
                break

    rows: list[dict] = []
    with parse_filepath.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        fieldnames = reader.fieldnames
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

    if not rows:
        raise ValueError("No valid rows found in CSV.")

    logger.debug(f"Parsed {len(rows)} rows from {parse_filepath}")

    # Clean up old temp files opportunistically
    if profile_dir:
        try:
            config = load_config(profile_dir)
            retention_hours = config.get("temp_dir_retention_hours", 24)
            temp_dir = get_temp_dir(profile_dir)
            cleanup_old_temp_files(temp_dir, retention_hours)
        except Exception as exc:
            logger.debug(f"Temp cleanup failed: {exc}")

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
