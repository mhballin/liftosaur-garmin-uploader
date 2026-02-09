"""Build FIT from workout data."""

from __future__ import annotations

from datetime import datetime, timedelta

from .exercise.duration import estimate_set_duration, lbs_to_kg
from .exercise.mapping import lookup_exercise
from .fit.constants import EVENT_TYPE_START, EVENT_TYPE_STOP_ALL, SET_TYPE_ACTIVE
from .fit.encoder import FitEncoder
from .fit.utils import parse_iso


def build_fit_for_workout(sets: list[dict]) -> bytes:
    """Build a FIT strength training activity from Liftosaur set rows.
    
    Fix 1.5: Message ordering now follows the Garmin spec:
    file_id → device_settings → user_profile → zones_target → file_creator →
    device_info → event(start) → sport → set → session → event(stop) → activity
    """
    if not sets:
        raise ValueError("Workout has no sets to encode.")

    encoder = FitEncoder()
    workout_start = parse_iso(sets[0]["Workout DateTime"])

    # Calculate workout end time
    last_time = workout_start
    for row in sets:
        completed = (row.get("Completed Reps Time") or "").strip()
        if completed:
            parsed = parse_iso(completed)
            if parsed > last_time:
                last_time = parsed

    workout_end = last_time + timedelta(seconds=30)
    total_elapsed = (workout_end - workout_start).total_seconds()

    # Filter out warmup sets
    working_sets = [
        row for row in sets if (row.get("Is Warmup Set?") or "0").strip() != "1"
    ]

    # Get unique exercises
    unique_exercises: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for row in working_sets:
        name = (row.get("Exercise") or "").strip()
        if name and name not in seen:
            seen.add(name)
            category_id, exercise_id = lookup_exercise(
                name, target_muscles=row.get("Target Muscles")
            )
            unique_exercises.append((name, category_id, exercise_id))

    total_reps = sum(
        int(float(row.get("Completed Reps", 0) or 0)) for row in working_sets
    )

    # ===== MESSAGE ORDERING PER GARMIN SPEC =====
    
    # 1. file_id
    encoder.write_file_id(workout_start)
    
    # 2. device_settings
    encoder.write_device_settings(workout_start)

    # 3. user_profile
    encoder.write_user_profile()

    # 4. zones_target
    encoder.write_zones_target()

    # 5. file_creator
    encoder.write_file_creator()
    
    # 6. device_info (creator device)
    encoder.write_device_info(workout_start, device_index=0)
    
    # 7. event(start)
    encoder.write_event(workout_start, event_type=EVENT_TYPE_START)
    
    # 8. sport
    encoder.write_sport("Strength")
    
    # 9. set
    prev_end_time: datetime | None = None
    prev_category_id = 65534
    prev_exercise_id = 0
    set_count = 0
    message_index = 0

    for row in working_sets:
        exercise_name = (row.get("Exercise") or "Unknown").strip()
        reps = int(float(row.get("Completed Reps", 0) or 0))
        weight_value = float(row.get("Completed Weight Value", 0) or 0)
        weight_unit = (row.get("Completed Weight Unit") or "lb").strip()
        weight_kg = lbs_to_kg(weight_value) if weight_unit == "lb" else weight_value

        category_id, exercise_id = lookup_exercise(
            exercise_name, target_muscles=row.get("Target Muscles")
        )
        completed = (row.get("Completed Reps Time") or "").strip()
        if completed:
            set_end = parse_iso(completed)
        else:
            set_end = workout_start + timedelta(minutes=set_count * 2)

        set_duration = estimate_set_duration(reps, category_id)
        set_start_estimated = set_end - timedelta(seconds=set_duration)

        if prev_end_time:
            set_start = max(set_start_estimated, prev_end_time)
            set_duration = (set_end - set_start).total_seconds()
        else:
            set_start = set_start_estimated

        # Write the active set
        encoder.write_set(
            ts=set_end,
            duration_s=set_duration,
            set_type=SET_TYPE_ACTIVE,
            category=category_id,
            exercise_name=exercise_id,
            reps=reps,
            weight_kg=weight_kg,
            start_time=set_start,
            message_index=message_index,
            wkt_step_index=0,
        )
        message_index += 1

        prev_end_time = set_end
        prev_category_id = category_id
        prev_exercise_id = exercise_id
        set_count += 1

    # 10. session
    encoder.write_session(
        ts=workout_end,
        start=workout_start,
        elapsed_s=total_elapsed,
        timer_s=total_elapsed,
        total_reps=total_reps
    )

    # Additional device_info messages during the workout.
    device_info_interval_s = 30
    for offset_s in range(device_info_interval_s, int(total_elapsed), device_info_interval_s):
        encoder.write_device_info(
            workout_start + timedelta(seconds=offset_s),
            device_index=0,
        )

    # Record messages at 1-second intervals for the entire workout duration.
    for offset_s in range(int(total_elapsed) + 1):
        encoder.write_record(
            workout_start + timedelta(seconds=offset_s),
            heart_rate=64,
        )
    
    # 11. event(stop)
    encoder.write_event(workout_end, event_type=EVENT_TYPE_STOP_ALL)
    
    # 12. device_info (end)
    encoder.write_device_info(workout_end, device_index=0)
    
    # 13. activity
    encoder.write_activity(workout_end, total_elapsed)

    return encoder.build()


def build_fit(sets: list[dict]) -> bytes:
    """Compatibility wrapper for building a FIT payload."""
    return build_fit_for_workout(sets)
