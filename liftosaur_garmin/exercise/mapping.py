"""Exercise name to Garmin FIT category/exercise mapping.

Three-tier lookup system:
1. Manual overrides - curated map covering all 182 built-in Liftosaur exercises
2. Fuzzy matching - searches Garmin's exercise database within the right category
3. Muscle-based fallback - uses CSV target muscles to pick the correct category

Values are (exercise_category, exercise_name) tuples from Garmin FIT Profile.xlsx.
Reference: FIT SDK Profile.xlsx -> Types tab
"""

from __future__ import annotations

from difflib import SequenceMatcher, get_close_matches


# ---------------------------------------------------------------------------
# Tier 1: Manual overrides covering all built-in Liftosaur exercises
# ---------------------------------------------------------------------------
MANUAL_OVERRIDES: dict[str, tuple[int, int]] = {
    # === COMPOUND BARBELL ===
    "squat": (28, 6), "back squat": (28, 6), "bench press": (0, 1),
    "deadlift": (8, 0), "overhead press": (24, 14), "shoulder press": (24, 4),
    "romanian deadlift": (8, 23), "romanian deadlift, barbell": (8, 23),
    "front squat": (28, 8), "sumo deadlift": (8, 15),
    # === BENCH PRESS VARIANTS ===
    "bench press close grip": (0, 4), "bench press wide grip": (0, 25),
    "decline bench press": (0, 5), "incline bench press": (0, 8),
    "incline bench press wide grip": (0, 8), "dumbbell bench press": (0, 6),
    "incline dumbbell bench press": (0, 9), "sling shot bench press": (0, 1),
    "legs up bench press": (0, 1),
    # === CHEST ===
    "chest press": (0, 6), "incline chest press": (0, 9),
    "iso-lateral chest press": (0, 21), "chest fly": (9, 2),
    "incline chest fly": (9, 3), "dumbbell fly": (9, 2),
    "cable fly": (9, 0), "cable crossover": (9, 0), "pec deck": (9, 0),
    "chest dip": (30, 2),
    # === ROWS ===
    "barbell row": (23, 45), "bent over row": (23, 46),
    "bent over one arm row": (23, 13), "pendlay row": (23, 46),
    "seated row": (23, 18), "cable row": (23, 18),
    "seated wide grip row": (23, 33), "chest-supported row": (23, 40),
    "iso-lateral row": (23, 24), "incline row": (23, 2),
    "inverted row": (23, 0), "standing row": (23, 1),
    "standing row close grip": (23, 1),
    "standing row rear delt with rope": (23, 5),
    "standing row rear delt, horizontal, with rope": (23, 5),
    "standing row v-bar": (23, 32), "high row": (23, 0),
    "squat row": (23, 0), "t bar row": (23, 28), "t-bar row": (23, 28),
    "face pull": (23, 5), "face pull, cable": (23, 5), "rowing": (23, 0),
    # === PULL UPS / PULLDOWNS ===
    "lat pulldown": (21, 13), "pull up": (21, 38), "chin up": (21, 39),
    "wide pull up": (21, 26), "kipping pull up": (21, 32),
    "reverse lat pulldown": (21, 18), "kneeling pulldown": (21, 11),
    "muscle up": (14, 13), "pullover": (21, 8),
    # === SHOULDERS ===
    "lateral raise": (14, 34), "dumbbell lateral raise": (14, 34),
    "cable lateral raise": (14, 14), "arnold press": (24, 1),
    "push press": (24, 3), "seated overhead press": (24, 16),
    "shoulder press parallel grip": (24, 24), "behind the neck press": (24, 16),
    "press under": (24, 4), "front raise": (14, 10),
    "seated front raise": (14, 10), "reverse fly": (14, 25),
    "rear delt fly": (14, 25), "around the world": (14, 32),
    "shrug": (26, 5), "barbell shrug": (26, 1), "upright row": (26, 24),
    # === ARMS - BICEPS ===
    "bicep curl": (7, 3), "dumbbell curl": (7, 46), "hammer curl": (7, 16),
    "preacher curl": (7, 19), "concentration curl": (7, 44),
    "incline curl": (7, 22), "lying bicep curl": (7, 46),
    "reverse curl": (7, 29), "reverse grip concentration curl": (7, 44),
    "wrist curl": (7, 5), "reverse wrist curl": (7, 4),
    "seated palms up wrist curl": (7, 18), "wrist roller": (7, 5),
    # === ARMS - TRICEPS ===
    "triceps pushdown": (30, 39), "tricep pushdown": (30, 39),
    "triceps extension": (30, 15), "tricep extension": (30, 15),
    "skullcrusher": (30, 13), "skull crusher": (30, 13),
    "cable kickback": (30, 3), "triceps dip": (30, 2), "dip": (30, 2),
    "bench dip": (30, 0), "handstand push up": (22, 25), "push up": (22, 77),
    # === LEGS - SQUAT VARIANTS ===
    "leg press": (28, 0), "seated leg press": (28, 0), "goblet squat": (28, 37),
    "hack squat": (28, 9), "box squat": (28, 7), "overhead squat": (28, 44),
    "pistol squat": (28, 47), "safety squat bar squat": (28, 6),
    "split squat": (17, 13), "sissy squat": (28, 61), "jump squat": (20, 0),
    "zercher squat": (28, 86), "thruster": (28, 79), "step up": (28, 66),
    "leg extension": (28, 0),
    # === LEGS - DEADLIFT VARIANTS ===
    "stiff leg deadlift": (8, 1), "straight leg deadlift": (8, 25),
    "deficit deadlift": (8, 0), "trap bar deadlift": (8, 17),
    "single leg deadlift": (8, 14), "deadlift high pull": (8, 16),
    "sumo deadlift high pull": (8, 16), "snatch pull": (8, 16),
    # === LEGS - LUNGES ===
    "lunge": (17, 32), "walking lunge": (17, 78), "dumbbell lunge": (17, 21),
    "reverse lunge": (17, 11), "bulgarian split squat": (17, 18),
    # === LEGS - CURLS / CALVES ===
    "leg curl": (15, 0), "seated leg curl": (15, 0), "lying leg curl": (15, 0),
    "good morning": (15, 2), "calf raise": (1, 18), "standing calf raise": (1, 18),
    "seated calf raise": (1, 6), "single leg calf raise": (1, 15),
    "calf press on leg press": (1, 0), "calf press on seated leg press": (1, 6),
    # === HIPS / GLUTES ===
    "hip thrust": (10, 1), "barbell hip thrust": (10, 1),
    "single leg hip thrust": (10, 30), "glute bridge": (10, 6),
    "glute bridge march": (10, 24), "glute kickback": (10, 0),
    "single leg bridge": (10, 30), "single leg glute bridge on bench": (10, 32),
    "single leg glute bridge straight leg": (10, 30),
    "single leg glute bridge bent knee": (10, 30),
    "kettlebell swing": (10, 23), "cable pull through": (10, 0),
    "hip abductor": (11, 0), "hip adductor": (11, 0),
    "side hip abductor": (11, 0), "side lying clam": (10, 44),
    # === CORE ===
    "plank": (19, 43), "side plank": (19, 66), "reverse plank": (19, 43),
    "mountain climber": (19, 34), "superman": (13, 29),
    "back extension": (13, 25), "reverse hyperextension": (13, 0),
    "ab wheel": (5, 18), "russian twist": (5, 46), "cable twist": (5, 46),
    "torso rotation": (5, 46), "side bend": (5, 7),
    "kettlebell turkish get up": (5, 89), "hanging leg raise": (16, 1),
    "toes to bar": (16, 1), "knees to elbows": (16, 1),
    "knee raise": (16, 0), "flat knee raise": (16, 0),
    "flat leg raise": (16, 8), "crunch": (6, 0), "cable crunch": (6, 0),
    "cross body crunch": (6, 0), "bicycle crunch": (6, 0),
    "decline crunch": (6, 0), "oblique crunch": (6, 0),
    "reverse crunch": (6, 0), "side crunch": (6, 0),
    "sit up": (27, 0), "jackknife sit up": (27, 0), "v up": (27, 0),
    # === OLYMPIC LIFTS ===
    "clean": (18, 0), "clean and jerk": (18, 0), "power clean": (18, 0),
    "hang clean": (18, 0), "snatch": (18, 0), "power snatch": (18, 0),
    "hang snatch": (18, 0), "split jerk": (18, 0),
    # === CARDIO / PLYO ===
    "burpee": (29, 0), "box jump": (20, 0), "lateral box jump": (20, 0),
    "high knee skips": (2, 0), "jump rope": (2, 0), "jumping jack": (2, 0),
    "cycling": (33, 0), "elliptical machine": (39, 0),
    "ball slams": (29, 0), "battle ropes": (38, 0),
}

EXERCISE_MAP = MANUAL_OVERRIDES  # backward compatibility


# ---------------------------------------------------------------------------
# Garmin category name -> ID
# ---------------------------------------------------------------------------
GARMIN_CATEGORIES: dict[str, int] = {
    "bench_press": 0, "calf_raise": 1, "cardio": 2, "carry": 3,
    "chop": 4, "core": 5, "crunch": 6, "curl": 7, "deadlift": 8,
    "flye": 9, "hip_raise": 10, "hip_stability": 11, "hip_swing": 12,
    "hyperextension": 13, "lateral_raise": 14, "leg_curl": 15,
    "leg_raise": 16, "lunge": 17, "olympic_lift": 18, "plank": 19,
    "plyo": 20, "pull_up": 21, "push_up": 22, "row": 23,
    "shoulder_press": 24, "shoulder_stability": 25, "shrug": 26,
    "sit_up": 27, "squat": 28, "total_body": 29,
    "triceps_extension": 30, "warm_up": 31,
}

# ---------------------------------------------------------------------------
# Per-category exercises for fuzzy matching (subset from Profile.xlsx)
# ---------------------------------------------------------------------------
GARMIN_EXERCISES: dict[str, dict[str, int]] = {
    "bench_press": {
        "barbell bench press": 1, "close grip barbell bench press": 4,
        "decline dumbbell bench press": 5, "dumbbell bench press": 6,
        "dumbbell floor press": 7, "incline barbell bench press": 8,
        "incline dumbbell bench press": 9, "smith machine bench press": 22,
        "wide grip barbell bench press": 25, "single arm dumbbell bench press": 21,
    },
    "curl": {
        "barbell biceps curl": 3, "cable biceps curl": 8, "dumbbell biceps curl": 46,
        "dumbbell hammer curl": 16, "ez bar preacher curl": 19,
        "incline dumbbell biceps curl": 22, "one arm concentration curl": 44,
        "reverse ez bar curl": 29, "barbell wrist curl": 5,
        "barbell reverse wrist curl": 4, "dumbbell wrist curl": 18,
    },
    "deadlift": {
        "barbell deadlift": 0, "barbell straight leg deadlift": 1,
        "dumbbell deadlift": 2, "rack pull": 7,
        "single leg romanian deadlift with dumbbell": 14,
        "sumo deadlift": 15, "sumo deadlift high pull": 16,
        "trap bar deadlift": 17, "romanian deadlift": 23,
        "straight leg deadlift": 25,
    },
    "hyperextension": {
        "spine extension": 25, "superman from floor": 29,
        "swiss ball hyperextension": 33, "cobra": 38, "kneeling superman": 12,
    },
    "lateral_raise": {
        "front raise": 10, "one arm cable lateral raise": 14,
        "seated lateral raise": 24, "seated rear lateral raise": 25,
        "dumbbell lateral raise": 34, "arm circles": 32, "muscle up": 13,
    },
    "leg_curl": {"leg curl": 0, "good morning": 2, "sliding leg curl": 6},
    "leg_raise": {
        "hanging knee raise": 0, "hanging leg raise": 1,
        "lying straight leg raise": 8, "reverse leg raise": 13,
    },
    "lunge": {
        "barbell bulgarian split squat": 7, "barbell lunge": 10,
        "barbell reverse lunge": 11, "dumbbell bulgarian split squat": 18,
        "dumbbell lunge": 21, "lunge": 32, "walking lunge": 78,
        "barbell split squat": 13, "curtsy lunge": 86,
    },
    "row": {
        "cable row standing": 1, "dumbbell row": 2, "face pull": 5,
        "one arm bent over row": 13, "seated cable row": 18,
        "single arm cable row": 20, "t bar row": 28,
        "v grip cable row": 32, "wide grip seated cable row": 33,
        "barbell row": 45, "bent over row with barbell": 46,
        "chest supported dumbbell row": 40,
        "single arm neutral grip dumbbell row": 24,
    },
    "shoulder_press": {
        "arnold press": 1, "barbell push press": 3, "barbell shoulder press": 4,
        "overhead barbell press": 14, "overhead dumbbell press": 15,
        "seated barbell shoulder press": 16, "seated dumbbell shoulder press": 17,
        "dumbbell shoulder press": 24, "military press": 25, "strict press": 27,
    },
    "shrug": {"barbell shrug": 1, "dumbbell shrug": 5, "upright row": 24},
    "squat": {
        "leg press": 0, "barbell back squat": 6, "barbell box squat": 7,
        "barbell front squat": 8, "barbell hack squat": 9,
        "goblet squat": 37, "overhead squat": 44, "pistol squat": 47,
        "squat": 61, "step up": 66, "thrusters": 79,
        "zercher squat": 86, "air squat": 100, "sissy squat": 61,
    },
    "triceps_extension": {
        "bench dip": 0, "body weight dip": 2, "cable kickback": 3,
        "lying ez bar triceps extension": 13,
        "overhead dumbbell triceps extension": 15,
        "rope pressdown": 19, "triceps pressdown": 39, "weighted dip": 40,
    },
    "flye": {
        "cable crossover": 0, "dumbbell flye": 2, "incline dumbbell flye": 3,
    },
    "hip_raise": {
        "barbell hip thrust on floor": 0, "barbell hip thrust with bench": 1,
        "clam bridge": 6, "hip raise": 11, "kettlebell swing": 23,
        "marching hip raise": 24, "single leg hip raise": 30,
        "single leg hip raise with foot on bench": 32, "clams": 44,
    },
    "plank": {"mountain climber": 34, "plank": 43, "side plank": 66},
    "core": {
        "kneeling ab wheel": 18, "russian twist": 46, "cable side bend": 7,
        "turkish get up": 89,
    },
    "pull_up": {
        "lat pulldown": 13, "reverse grip pulldown": 18,
        "kneeling lat pulldown": 11, "wide grip pull up": 26,
        "kipping pull up": 32, "pull up": 38, "chin up": 39,
        "ez bar pullover": 8,
    },
    "calf_raise": {
        "seated calf raise": 6, "single leg standing calf raise": 15,
        "standing calf raise": 18, "standing dumbbell calf raise": 20,
    },
    "push_up": {"push up": 77, "handstand push up": 25},
}

# ---------------------------------------------------------------------------
# Tier 3: Target muscle -> Garmin category
# ---------------------------------------------------------------------------
MUSCLE_TO_CATEGORY: dict[str, str] = {
    "pectoralis major sternal head": "bench_press",
    "pectoralis major clavicular head": "bench_press",
    "deltoid anterior": "shoulder_press", "deltoid lateral": "lateral_raise",
    "deltoid posterior": "row", "latissimus dorsi": "pull_up",
    "trapezius middle fibers": "row", "trapezius lower fibers": "row",
    "trapezius upper fibers": "shrug", "teres major": "pull_up",
    "biceps brachii": "curl", "triceps brachii": "triceps_extension",
    "brachialis": "curl", "brachioradialis": "curl",
    "quadriceps": "squat", "gluteus maximus": "hip_raise",
    "hamstrings": "deadlift", "gastrocnemius": "calf_raise",
    "soleus": "calf_raise", "adductor magnus": "squat",
    "gluteus medius": "hip_stability",
    "rectus abdominis": "crunch", "obliques": "core",
    "erector spinae": "hyperextension", "iliopsoas": "core",
    "serratus anterior": "shoulder_press",
    "infraspinatus": "shoulder_stability", "teres minor": "shoulder_stability",
}


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    n = name.lower().strip()
    for suffix in (", barbell", ", dumbbell", ", cable", ", machine",
                   ", band", ", kettlebell", ", bodyweight", ", ez-bar"):
        n = n.replace(suffix, "")
    return n


def _fuzzy_match_in_category(name: str, category_name: str) -> tuple[int | None, float]:
    exercises = GARMIN_EXERCISES.get(category_name)
    if not exercises:
        return None, 0.0
    norm = _normalize_name(name)
    if norm in exercises:
        return exercises[norm], 1.0
    keys = list(exercises.keys())
    matches = get_close_matches(norm, keys, n=1, cutoff=0.45)
    if matches:
        score = SequenceMatcher(None, norm, matches[0]).ratio()
        return exercises[matches[0]], score
    return None, 0.0


def _get_category_from_muscles(target_muscles: str) -> str | None:
    if not target_muscles:
        return None
    muscles = [m.strip().lower() for m in target_muscles.split(",")]
    for muscle in muscles:
        if muscle in MUSCLE_TO_CATEGORY:
            return MUSCLE_TO_CATEGORY[muscle]
    return None


def lookup_exercise(name: str, target_muscles: str | None = None) -> tuple[int, int]:
    """Map exercise name to (category_id, exercise_name_id).

    Three-tier lookup:
    1. Manual overrides (covers all 182 built-in Liftosaur exercises)
    2. Fuzzy matching within muscle-determined category
    3. Muscle-based category fallback

    Falls back to (65534, 0) for truly unknown exercises.
    """
    key = name.strip().lower()

    # Tier 1: exact override
    if key in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[key]

    # Tier 1b: partial match
    for ok, ov in MANUAL_OVERRIDES.items():
        if ok in key or key in ok:
            return ov

    # Tier 2: fuzzy within muscle-determined category
    if target_muscles:
        cat_name = _get_category_from_muscles(target_muscles)
        if cat_name:
            cat_id = GARMIN_CATEGORIES.get(cat_name)
            if cat_id is not None:
                ex_id, score = _fuzzy_match_in_category(name, cat_name)
                if ex_id is not None and score >= 0.5:
                    return (cat_id, ex_id)
                return (cat_id, 0)

    # Tier 2b: global fuzzy
    best_match: tuple[int, int] | None = None
    best_score = 0.0
    for cat_name in GARMIN_EXERCISES:
        ex_id, score = _fuzzy_match_in_category(name, cat_name)
        if ex_id is not None and score > best_score:
            best_score = score
            cat_id = GARMIN_CATEGORIES.get(cat_name, 65534)
            best_match = (cat_id, ex_id)

    if best_match and best_score >= 0.6:
        return best_match

    return (65534, 0)