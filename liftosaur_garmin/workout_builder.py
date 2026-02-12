"""Build FIT from workout data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, tzinfo

from .exercise.duration import (
    compute_set_timing,
    lbs_to_kg,
)
from .exercise.mapping import lookup_exercise
from .fit.constants import (
    EVENT_TYPE_START,
    EVENT_TYPE_STOP_ALL,
    SET_TYPE_ACTIVE,
    SET_TYPE_REST,
)
from .fit.encoder import FitEncoder
from .fit.utils import fit_local_timestamp, parse_iso, resolve_timezone

logger = logging.getLogger(__name__)


def build_fit_for_workout(sets: list[dict], tzinfo: tzinfo | None = None) -> bytes:
    """Build a FIT strength training activity from Liftosaur set rows.

    Message ordering follows the Garmin spec:
    file_id -> device_settings -> user_profile -> zones_target -> file_creator ->
    device_info -> event(start) -> sport -> exercise_titles ->
    records/device_info (interleaved) -> sets (active + rest) ->
    session -> event(stop) -> device_info(end) -> activity

    NOTE: Split and split_summary messages are NOT included because
    real Fenix 7 strength training FIT files do not contain them.
    """
    if not sets:
        raise ValueError("Workout has no sets to encode.")

    # Diagnostic state for improved error messages. Updated inside the per-set loop.
    current_set_info: dict | None = None

    try:
        encoder = FitEncoder()
        local_tz = tzinfo or resolve_timezone(None)
        workout_start = parse_iso(sets[0]["Workout DateTime"])

        # ── Calculate workout end time ──────────────────────────────────
        last_time = workout_start
        for row in sets:
            completed = (row.get("Completed Reps Time") or "").strip()
            if completed:
                parsed = parse_iso(completed)
                if parsed > last_time:
                    last_time = parsed

        workout_end = last_time + timedelta(seconds=30)
        total_elapsed = (workout_end - workout_start).total_seconds()

        # ── Get unique exercises (preserving order) ─────────────────────
        unique_exercises: list[tuple[str, int, int]] = []
        seen: set[str] = set()
        for row in sets:
            name = (row.get("Exercise") or "").strip()
            if name and name not in seen:
                seen.add(name)
                category_id, exercise_id = lookup_exercise(
                    name, target_muscles=row.get("Target Muscles")
                )
                unique_exercises.append((name, category_id, exercise_id))

        total_reps = sum(
            int(float(row.get("Completed Reps", 0) or 0)) for row in sets
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

        # 9. exercise_title messages for each unique exercise
        for idx, (name, cat_id, ex_id) in enumerate(unique_exercises):
            encoder.write_exercise_title(
                message_index=idx,
                name=name,
                exercise_category=cat_id,
                exercise_name=ex_id,
            )

        # 10. Record and device_info messages interleaved during the workout
        #     Records at 1-second intervals, device_info every 30 seconds
        for offset_s in range(int(total_elapsed) + 1):
            ts = workout_start + timedelta(seconds=offset_s)
            encoder.write_record(ts, heart_rate=64)
            if offset_s > 0 and offset_s % 30 == 0:
                encoder.write_device_info(ts, device_index=0)

        # 11. Sets (active + rest, NO splits) ────────────────────────────
        prev_end_time: datetime | None = None
        prev_category_id: int = 65534
        prev_exercise_id: int = 0
        prev_exercise_name: str = ""
        set_count: int = 0
        message_index: int = 0
        active_timer_s: float = 0.0

        for idx, row in enumerate(sets):
            # Update diagnostic context before processing this set
            current_set_info = {
                "index": idx,
                "exercise": (row.get("Exercise") or "").strip(),
                "completed_reps_time": (row.get("Completed Reps Time") or "").strip(),
                "workout_datetime": sets[0].get("Workout DateTime"),
            }

            # Keep current_set_info local for exception handlers
            cur_info = current_set_info

            exercise_name = (row.get("Exercise") or "Unknown").strip()
            is_amrap = (row.get("Is AMRAP?") or "0").strip() == "1"
            is_warmup = (row.get("Is Warmup Set?") or "0").strip() == "1"
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

            prev_for_timing = prev_end_time if prev_end_time is not None else workout_start
            timing = compute_set_timing(set_end, prev_for_timing, reps, category_id)
            set_start = timing["set_start"]
            set_duration = timing["set_duration"]
            rest_duration = timing["rest_duration"]

            set_label = "AMRAP" if is_amrap else ("Warmup" if is_warmup else "Set")

            # Detect superset pattern (different exercise with short gap)
            if (prev_end_time is not None
                    and exercise_name != prev_exercise_name
                    and rest_duration < 10):
                logger.debug(
                    f"Superset transition: {prev_exercise_name} → {exercise_name} "
                    f"(gap={rest_duration:.1f}s)"
                )

            logger.debug(
                f"{set_label} {idx}: {exercise_name} - {reps} reps @ {weight_kg:.1f}kg "
                f"duration={set_duration:.1f}s rest={rest_duration:.1f}s"
            )

            # ── Write rest set (if there's a gap > 5s) ─────────────────
            if prev_end_time is not None and rest_duration > 5:
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
                    wkt_step_index=0,
                )
                message_index += 1

            # ── Write active set ───────────────────────────────────────
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
            active_timer_s += set_duration

            prev_end_time = set_end
            prev_category_id = category_id
            prev_exercise_id = exercise_id
            prev_exercise_name = exercise_name
            set_count += 1

        # 12. session
        # NOTE: timer_s = total_elapsed so the header shows full workout duration.
        # Garmin calculates Work Time / Rest Time from individual set messages.
        encoder.write_session(
            ts=workout_end,
            start=workout_start,
            elapsed_s=total_elapsed,
            timer_s=total_elapsed,
            total_reps=total_reps,
        )

        # 13. event(stop)
        encoder.write_event(workout_end, event_type=EVENT_TYPE_STOP_ALL)

        # 14. device_info (end)
        encoder.write_device_info(workout_end, device_index=0)

        # 15. activity
        encoder.write_activity(
            workout_end,
            total_elapsed,
            local_timestamp=fit_local_timestamp(workout_end, local_tz),
        )

        fit_data = encoder.build()
        logger.info(
            f"Generated FIT for {len(unique_exercises)} exercises, "
            f"{len(sets)} sets, {total_reps} total reps ({len(fit_data)} bytes)"
        )
        return fit_data

    except Exception as exc:  # pragma: no cover - diagnostic wrapper
        logger.error("Error building FIT for workout:")
        try:
            workout_dt = sets[0].get("Workout DateTime")
        except Exception:
            workout_dt = None
        logger.error(f"  Workout DateTime: {workout_dt}")
        if current_set_info is not None:
            logger.error("  Current set when error occurred:")
            for k, v in current_set_info.items():
                logger.error(f"    {k}: {v}")
        logger.exception("  Exception:")
        raise


def build_fit(sets: list[dict], tzinfo: tzinfo | None = None) -> bytes:
    """Compatibility wrapper for building a FIT payload."""
    return build_fit_for_workout(sets, tzinfo=tzinfo)