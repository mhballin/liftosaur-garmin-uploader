"""Set duration estimation."""

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


def estimate_set_duration(reps: int, category_id: int) -> float:
    """Estimate time-under-tension for a set."""
    per_rep = REP_DURATION.get(category_id, DEFAULT_REP_DURATION)
    return max(reps * per_rep, MIN_SET_DURATION)


def lbs_to_kg(lbs: float) -> float:
    """Convert pounds to kilograms."""
    return lbs * 0.453592