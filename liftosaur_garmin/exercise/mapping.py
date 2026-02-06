"""Exercise name to Garmin category mapping."""

EXERCISE_MAP = {
    # Compound barbell
    "squat": (28, 0),
    "bench press": (0, 0),
    "deadlift": (8, 0),
    "overhead press": (24, 0),
    "romanian deadlift, barbell": (8, 7),
    "barbell row": (23, 0),
    "bent over row": (23, 0),
    "pendlay row": (23, 0),

    # Pull
    "lat pulldown": (21, 0),
    "pull up": (21, 0),
    "chin up": (21, 0),
    "seated row": (23, 0),
    "cable row": (23, 0),
    "face pull": (23, 0),

    # Push accessories
    "incline bench press": (0, 0),
    "dumbbell bench press": (0, 0),
    "dumbbell fly": (9, 0),
    "cable fly": (9, 0),
    "dip": (30, 0),

    # Shoulders
    "lateral raise": (14, 0),
    "shrug": (26, 0),

    # Arms
    "dumbbell curl": (7, 0),
    "bicep curl": (7, 0),
    "hammer curl": (7, 0),
    "tricep pushdown": (30, 0),
    "tricep extension": (30, 0),

    # Legs
    "leg press": (28, 0),
    "leg curl": (15, 0),
    "leg extension": (28, 0),
    "calf raise": (1, 0),
    "hip thrust": (10, 0),
    "lunge": (17, 0),
    "bulgarian split squat": (17, 0),

    # Core / posterior chain
    "plank": (19, 0),
    "superman": (13, 0),
    "back extension": (13, 0),
    "ab wheel": (5, 0),
    "hanging leg raise": (16, 0),
    "russian twist": (5, 0),
}


def lookup_exercise(name: str) -> tuple[int, int]:
    """Map exercise name to (category_id, exercise_name_id)."""
    key = name.strip().lower()
    if key in EXERCISE_MAP:
        return EXERCISE_MAP[key]
    for k, v in EXERCISE_MAP.items():
        if k in key or key in k:
            return v
    return (65534, 0)  # unknown