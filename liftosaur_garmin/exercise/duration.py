"""Set duration estimation utilities.

This module provides an estimate of time-under-tension for a set and a
helper to compute set timing relative to the previous set end. The
estimates are heuristic and clamped to a minimum set duration.
"""

from datetime import datetime, timedelta
from typing import Dict

REP_DURATION = {
    28: 5.0,   # squat
    8: 5.0,    # deadlift
    0: 4.0,    # bench press
    24: 3.5,   # shoulder press
    23: 3.0,   # row
    21: 3.5,   # pull up
    17: 4.0,   # lunge
    10: 3.5,   # hip raise
    13: 3.0,   # hyperextension
}

DEFAULT_REP_DURATION = 3.0
MIN_SET_DURATION = 8.0


def estimate_time_under_tension(reps: int, category_id: int) -> float:
    """Estimate time-under-tension (seconds) for a set.

    This returns per-rep duration * reps, clamped to MIN_SET_DURATION.
    """
    per_rep = REP_DURATION.get(category_id, DEFAULT_REP_DURATION)
    return max(reps * per_rep, MIN_SET_DURATION)


def compute_set_timing(
    set_end: datetime,
    prev_set_end: datetime,
    reps: int,
    category_id: int,
) -> Dict[str, object]:
    """Compute set timing and rest duration.

    Args:
        set_end: datetime when the set completed (from CSV)
        prev_set_end: datetime of previous set end (or workout start for first set)
        reps: completed reps
        category_id: Garmin category id used for per-rep timing

    Returns:
        dict with keys: `set_start`, `set_end`, `set_duration` (seconds),
        and `rest_duration` (seconds, >= 0).
    """
    time_under_tension = estimate_time_under_tension(reps, category_id)
    set_start = set_end - timedelta(seconds=time_under_tension)

    # Clamp set_start to not begin before previous set end
    if set_start < prev_set_end:
        set_start = prev_set_end

    set_duration = (set_end - set_start).total_seconds()
    rest_duration = (set_start - prev_set_end).total_seconds()
    if rest_duration < 0:
        rest_duration = 0.0

    return {
        "set_start": set_start,
        "set_end": set_end,
        "set_duration": set_duration,
        "rest_duration": rest_duration,
    }


def lbs_to_kg(lbs: float) -> float:
    """Convert pounds to kilograms."""
    return lbs * 0.453592