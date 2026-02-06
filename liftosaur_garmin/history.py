"""Upload tracking."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path.home() / ".liftosaur_garmin" / "history.json"


def load_history() -> dict:
    """Load upload history metadata."""
    if HISTORY_PATH.exists():
        with HISTORY_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_history(history: dict) -> None:
    """Persist upload history metadata."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)


def mark_uploaded(workout_datetime: str, sets: list[dict]) -> None:
    """Record a workout upload in history."""
    history = load_history()
    working_sets = [
        row for row in sets if (row.get("Is Warmup Set?") or "0").strip() != "1"
    ]
    history[workout_datetime] = {
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(sets),
        "working_sets": len(working_sets),
        "day": sets[0].get("Day Name", ""),
        "exercises": list(
            OrderedDict.fromkeys(row.get("Exercise", "") for row in working_sets)
        ),
    }
    save_history(history)


def get_new_workouts(workouts: OrderedDict[str, list[dict]], force: bool) -> OrderedDict[str, list[dict]]:
    """Return workouts not yet uploaded unless force is enabled."""
    if force:
        return workouts
    history = load_history()
    return OrderedDict((key, value) for key, value in workouts.items() if key not in history)
