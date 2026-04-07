"""Upload tracking."""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def load_history(profile_dir: Path) -> dict:
    """Load upload history metadata."""
    history_path = profile_dir / "history.json"
    if history_path.exists():
        with history_path.open("r", encoding="utf-8") as handle:
            history = json.load(handle)
            logger.debug("Loaded upload history: %s workouts", len(history))
            return history
    logger.debug("No upload history found at %s", history_path)
    return {}


def save_history(history: dict, profile_dir: Path) -> None:
    """Persist upload history metadata."""
    history_path = profile_dir / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)
    logger.debug("Saved upload history: %s workouts", len(history))


def mark_uploaded(workout_datetime: str, sets: list[dict], profile_dir: Path) -> None:
    """Record a workout upload in history."""
    history = load_history(profile_dir)
    source = (sets[0].get("__source") or "csv").strip() if sets else "csv"
    source_id = (sets[0].get("__source_id") or "").strip() if sets else ""
    history[workout_datetime] = {
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(sets),
        "working_sets": len(sets),
        "day": sets[0].get("Day Name", ""),
        "exercises": list(
            OrderedDict.fromkeys(row.get("Exercise", "") for row in sets)
        ),
        "source": source,
        "source_id": source_id,
    }
    save_history(history, profile_dir)
    logger.info("Marked workout %s as uploaded", workout_datetime)


def get_new_workouts(
    workouts: OrderedDict[str, list[dict]],
    force: bool,
    profile_dir: Path,
) -> OrderedDict[str, list[dict]]:
    """Return workouts not yet uploaded unless force is enabled."""
    if force:
        logger.debug("Forcing all workouts (ignoring history)")
        return workouts
    history = load_history(profile_dir)
    new = OrderedDict((key, value) for key, value in workouts.items() if key not in history)
    logger.debug(
        "Found %s new workouts (%s already uploaded)",
        len(new),
        len(history),
    )
    return new
