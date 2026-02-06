"""Build FIT from workout data."""

from __future__ import annotations

from datetime import datetime, timedelta

from .exercise.duration import estimate_set_duration, lbs_to_kg
from .exercise.mapping import lookup_exercise
from .fit.constants import (
    EVENT_TYPE_START,
    EVENT_TYPE_STOP_ALL,
    SET_TYPE_ACTIVE,
    SET_TYPE_REST,
    SPLIT_TYPE_ACTIVE,
    SPLIT_TYPE_REST,
)
from .fit.encoder import FitEncoder
from .fit.utils import parse_iso


def build_fit_for_workout(sets: list[dict]) -> bytes:
    """Build a FIT strength training activity from Liftosaur set rows.
    
    Fix 1.5: Message ordering now follows the Garmin spec:
    file_id → file_creator → device_info → event(start) → sport → 
    workout → workout_step → exercise_title → set+split (interleaved) →
    split_summary → lap → session → event(stop) → activity
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
            category_id, exercise_id = lookup_exercise(name)
            unique_exercises.append((name, category_id, exercise_id))

    total_reps = sum(
        int(float(row.get("Completed Reps", 0) or 0)) for row in working_sets
    )

    # ===== MESSAGE ORDERING PER GARMIN SPEC =====
    
    # 1. file_id
    encoder.write_file_id(workout_start)
    
    # 2. file_creator
    encoder.write_file_creator()
    
    # 3. device_info (creator device)
    encoder.write_device_info(workout_start, device_index=0)
    
    # 4. event(start)
    encoder.write_event(workout_start, event_type=EVENT_TYPE_START)
    
    # 5. sport
    encoder.write_sport("Strength")
    
    # 6. workout
    workout_name = sets[0].get("Day Name") or "Workout"
    encoder.write_workout(workout_name, len(unique_exercises) * 2)
    
    # 7. workout_step (all steps before any sets)
    step_index = 0
    exercise_step_index: dict[str, int] = {}
    for name, category_id, exercise_id in unique_exercises:
        exercise_step_index[name] = step_index
        encoder.write_workout_step(step_index, category_id, exercise_id, 10)
        step_index += 1
        encoder.write_workout_step(step_index, 0, 0, 0, is_rest=True)
        step_index += 1
    
    # 8. exercise_title (all titles before any sets)
    for index, (name, category_id, exercise_id) in enumerate(unique_exercises):
        encoder.write_exercise_title(index, name, category_id, exercise_id)
    
    # 9. set + split (interleaved)
    prev_end_time: datetime | None = None
    prev_category_id = 65534
    prev_exercise_id = 0
    prev_exercise_name: str | None = None
    set_count = 0
    message_index = 0
    splits: list[tuple[float, int]] = []

    for row in working_sets:
        exercise_name = (row.get("Exercise") or "Unknown").strip()
        reps = int(float(row.get("Completed Reps", 0) or 0))
        weight_value = float(row.get("Completed Weight Value", 0) or 0)
        weight_unit = (row.get("Completed Weight Unit") or "lb").strip()
        weight_kg = lbs_to_kg(weight_value) if weight_unit == "lb" else weight_value

        category_id, exercise_id = lookup_exercise(exercise_name)
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

        # Insert rest period if there's a gap
        base_step_index = exercise_step_index.get(exercise_name, 0)
        rest_step_index = base_step_index
        if prev_exercise_name:
            rest_step_index = exercise_step_index.get(prev_exercise_name, base_step_index)

        if prev_end_time and set_start > prev_end_time:
            rest_duration = (set_start - prev_end_time).total_seconds()
            if rest_duration > 5:
                encoder.write_set(
                    ts=set_start,
                    duration_s=rest_duration,
                    set_type=SET_TYPE_REST,
                    category=prev_category_id,
                    exercise_name=prev_exercise_id,
                    reps=0,
                    weight_kg=0,
                    start_time=prev_end_time,
                    message_index=message_index,
                    wkt_step_index=rest_step_index + 1,
                )
                encoder.write_split(
                    ts=set_start,
                    start_time=prev_end_time,
                    end_time=set_start,
                    elapsed_s=rest_duration,
                    timer_s=rest_duration,
                    split_type=SPLIT_TYPE_REST,
                    message_index=message_index,
                    total_ascent=0,
                )
                splits.append((rest_duration, SET_TYPE_REST))
                message_index += 1

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
            wkt_step_index=base_step_index,
        )
        encoder.write_split(
            ts=set_end,
            start_time=set_start,
            end_time=set_end,
            elapsed_s=set_duration,
            timer_s=set_duration,
            split_type=SPLIT_TYPE_ACTIVE,
            message_index=message_index,
            total_ascent=1,
        )
        splits.append((set_duration, SET_TYPE_ACTIVE))
        message_index += 1

        prev_end_time = set_end
        prev_category_id = category_id
        prev_exercise_id = exercise_id
        prev_exercise_name = exercise_name
        set_count += 1

    # 10. split_summary (Fix 1.4: Use keyword arguments for clarity)
    active_splits = [split for split in splits if split[1] == SET_TYPE_ACTIVE]
    rest_splits = [split for split in splits if split[1] == SET_TYPE_REST]
    
    if active_splits:
        total_active_time = sum(split[0] for split in active_splits)
        encoder.write_split_summary(
            ts=workout_end,
            total_timer_s=total_active_time,
            num_splits=len(active_splits),
            split_type=SPLIT_TYPE_ACTIVE,
            avg_hr=64,
            max_hr=74,
            message_index=0  # Fix 1.4: Explicit keyword argument
        )
    
    if rest_splits:
        total_rest_time = sum(split[0] for split in rest_splits)
        encoder.write_split_summary(
            ts=workout_end,
            total_timer_s=total_rest_time,
            num_splits=len(rest_splits),
            split_type=SPLIT_TYPE_REST,
            avg_hr=64,
            max_hr=74,
            message_index=1  # Fix 1.4: Explicit keyword argument
        )
    
    # 11. lap (Fix 1.6: Added required lap message)
    encoder.write_lap(
        ts=workout_end,
        start_time=workout_start,
        elapsed_s=total_elapsed,
        timer_s=total_elapsed,
        total_reps=total_reps
    )
    
    # 12. session
    encoder.write_session(
        ts=workout_end,
        start=workout_start,
        elapsed_s=total_elapsed,
        timer_s=total_elapsed,
        total_reps=total_reps
    )
    
    # 13. event(stop)
    encoder.write_event(workout_end, event_type=EVENT_TYPE_STOP_ALL)
    
    # 14. device_info (end)
    encoder.write_device_info(workout_end, device_index=0)
    
    # 15. activity
    encoder.write_activity(workout_end, total_elapsed)

    return encoder.build()


def build_fit(sets: list[dict]) -> bytes:
    """Compatibility wrapper for building a FIT payload."""
    return build_fit_for_workout(sets)
