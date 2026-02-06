"""Build FIT from workout data."""

from __future__ import annotations

from datetime import datetime, timedelta

from .exercise.duration import estimate_set_duration, lbs_to_kg
from .exercise.mapping import lookup_exercise
from .fit.constants import EVENT_TYPE_STOP_ALL, SET_TYPE_ACTIVE, SET_TYPE_REST
from .fit.encoder import FitEncoder
from .fit.utils import parse_iso


def build_fit_for_workout(sets: list[dict]) -> bytes:
    """Build a FIT strength training activity from Liftosaur set rows."""
    if not sets:
        raise ValueError("Workout has no sets to encode.")

    encoder = FitEncoder()
    workout_start = parse_iso(sets[0]["Workout DateTime"])

    last_time = workout_start
    for row in sets:
        completed = (row.get("Completed Reps Time") or "").strip()
        if completed:
            parsed = parse_iso(completed)
            if parsed > last_time:
                last_time = parsed

    workout_end = last_time + timedelta(seconds=30)
    total_elapsed = (workout_end - workout_start).total_seconds()

    working_sets = [
        row for row in sets if (row.get("Is Warmup Set?") or "0").strip() != "1"
    ]

    unique_exercises: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for row in working_sets:
        name = (row.get("Exercise") or "").strip()
        if name and name not in seen:
            seen.add(name)
            category_id, exercise_id = lookup_exercise(name)
            unique_exercises.append((name, category_id, exercise_id))

    encoder.write_file_id(workout_start)
    encoder.write_file_creator()
    encoder.write_activity(workout_end, total_elapsed)

    total_reps = sum(
        int(float(row.get("Completed Reps", 0) or 0)) for row in working_sets
    )
    encoder.write_session(
        workout_end, workout_start, total_elapsed, total_elapsed, total_reps
    )

    prev_end_time: datetime | None = None
    prev_category_id = 65534
    prev_exercise_id = 0
    set_count = 0
    message_index = 0
    wkt_step_index = 0
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
        set_start = set_end - timedelta(seconds=set_duration)

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
                    wkt_step_index=wkt_step_index + 1,
                    set_counter=set_count,
                )
                encoder.write_split(
                    ts=set_start,
                    start_time=prev_end_time,
                    end_time=set_start,
                    elapsed_s=rest_duration,
                    timer_s=rest_duration,
                    split_type=SET_TYPE_REST,
                    message_index=message_index,
                )
                splits.append((rest_duration, SET_TYPE_REST))
                message_index += 1

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
            wkt_step_index=wkt_step_index,
            set_counter=set_count,
        )
        encoder.write_split(
            ts=set_end,
            start_time=set_start,
            end_time=set_end,
            elapsed_s=set_duration,
            timer_s=set_duration,
            split_type=SET_TYPE_ACTIVE,
            message_index=message_index,
        )
        splits.append((set_duration, SET_TYPE_ACTIVE))
        message_index += 1

        prev_end_time = set_end
        prev_category_id = category_id
        prev_exercise_id = exercise_id
        set_count += 1

    active_splits = [split for split in splits if split[1] == SET_TYPE_ACTIVE]
    rest_splits = [split for split in splits if split[1] == SET_TYPE_REST]
    if active_splits:
        total_active_time = sum(split[0] for split in active_splits)
        encoder.write_split_summary(
            workout_end, total_active_time, len(active_splits), SET_TYPE_ACTIVE, 0
        )
    if rest_splits:
        total_rest_time = sum(split[0] for split in rest_splits)
        encoder.write_split_summary(
            workout_end, total_rest_time, len(rest_splits), SET_TYPE_REST, 1
        )

    encoder.write_event(workout_start)
    encoder.write_event(workout_end, event_type=EVENT_TYPE_STOP_ALL)

    encoder.write_device_info(workout_start, device_index=0)
    encoder.write_device_info(workout_end, device_index=0)
    encoder.write_sport("Strength")

    workout_name = sets[0].get("Day Name") or "Workout"
    encoder.write_workout(workout_name, len(unique_exercises) * 2)

    step_index = 0
    for _, category_id, exercise_id in unique_exercises:
        encoder.write_workout_step(step_index, category_id, exercise_id, 10)
        step_index += 1
        encoder.write_workout_step(step_index, 0, 0, 0, is_rest=True)
        step_index += 1

    current_time = workout_start
    while current_time <= workout_end:
        encoder.write_record(current_time, heart_rate=64)
        current_time += timedelta(seconds=2)

    for index, (name, category_id, exercise_id) in enumerate(unique_exercises):
        encoder.write_exercise_title(index, name, category_id, exercise_id)

    return encoder.build()


def build_fit(sets: list[dict]) -> bytes:
    """Compatibility wrapper for building a FIT payload."""
    return build_fit_for_workout(sets)
