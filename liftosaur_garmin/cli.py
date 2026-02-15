"""CLI entry point."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
import tempfile

from .config import load_config, save_config
from .csv_parser import group_workouts, parse_csv
from .exercise.duration import lbs_to_kg
from .fit.utils import parse_iso, resolve_timezone
from .history import get_new_workouts, load_history, mark_uploaded
from .logging_config import setup_logging
from .uploader import fetch_latest_weight_kg, garmin_setup, upload_to_garmin
from .workout_builder import build_fit_for_workout
from .validation import validate_fit_file

logger = logging.getLogger(__name__)


def _prompt_yes_no(question: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{question} ({suffix}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_weight_kg() -> float:
    while True:
        raw_value = input("Body weight fallback (used if Garmin unavailable) value: ").strip()
        if not raw_value:
            print("Please enter a number.")
            continue
        try:
            value = float(raw_value)
        except ValueError:
            print("Invalid number; try again.")
            continue

        unit = input("Unit (kg/lb): ").strip().lower() or "lb"
        if unit not in {"kg", "lb", "lbs"}:
            print("Invalid unit; use kg or lb.")
            continue
        if unit in {"lb", "lbs"}:
            return lbs_to_kg(value)
        return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liftosaur-garmin",
        description="Convert Liftosaur CSV workouts to Garmin FIT",
    )
    parser.add_argument("csv", nargs="?", help="Path to Liftosaur CSV export")
    parser.add_argument("--setup", action="store_true", help="Authenticate Garmin Connect")
    parser.add_argument("--list", action="store_true", help="List workouts (with CSV) or upload history (without CSV)")
    parser.add_argument("--dry-run", action="store_true", help="Preview uploads only")
    parser.add_argument("--no-upload", action="store_true", help="Skip Garmin upload")
    parser.add_argument("--force", action="store_true", help="Ignore upload history")
    parser.add_argument("--date", help="Workout date filter (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Upload all new workouts")
    parser.add_argument("--output", "-o", help="Output FIT file path")
    parser.add_argument(
        "--timezone",
        help="Override local timezone (e.g. America/New_York)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip FIT validation (FitCSVTool) before upload",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug output to console",
    )
    return parser


def build_validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liftosaur-garmin validate",
        description="Validate a FIT file using Garmin FIT SDK (FitCSVTool.jar)",
    )
    parser.add_argument("fit_file", help="Path to the FIT file to validate")
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        help="Keep the generated CSV output for inspection",
    )
    return parser


def run_validate_command(argv: list[str]) -> int:
    parser = build_validate_parser()
    args = parser.parse_args(argv)
    fit_path = Path(args.fit_file)
    if not fit_path.exists():
        logger.error(f"✗ FIT file not found: {fit_path}")
        return 1

    status, result = validate_fit_file(fit_path, keep_csv=args.keep_csv)
    if status is None:
        logger.error("✗ FitCSVTool.jar not found.")
        logger.error(
            "Please download the Garmin FIT SDK and copy tools/FitCSVTool.jar into this project."
        )
        return 2

    if status:
        logger.info("✓ FIT file is valid")
        return 0

    # validation failed
    logger.error("✗ FIT file validation failed")
    if result and result.stdout:
        logger.error("--- stdout ---")
        logger.error(result.stdout.strip())
    if result and result.stderr:
        logger.error("--- stderr ---")
        logger.error(result.stderr.strip())
    return 1


def format_workout_summary(workout_datetime: str, sets: list[dict], uploaded: bool) -> str:
    """Format a single workout for display."""
    dt = parse_iso(workout_datetime)
    day = sets[0].get("Day Name", "")
    warmup_count = sum(1 for row in sets if (row.get("Is Warmup Set?") or "0").strip() == "1")
    amrap_count = sum(1 for row in sets if (row.get("Is AMRAP?") or "0").strip() == "1")
    exercises = list(OrderedDict.fromkeys(row.get("Exercise", "") for row in sets))
    icon = "✅" if uploaded else "🆕"
    parts = [f"{len(sets)} sets"]
    if warmup_count:
        parts.append(f"{warmup_count} warmup")
    if amrap_count:
        parts.append(f"{amrap_count} AMRAP")
    lines = [
        f"  {icon} {dt.strftime('%Y-%m-%d %H:%M')} – {day}",
        f"     {', '.join(parts)}",
        f"     {', '.join(exercises)}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    
    # Setup logging early -- before any processing
    # Validate command and extract verbose flag
    verbose = "-v" in args_list or "--verbose" in args_list
    setup_logging(verbose=verbose)
    
    if args_list and args_list[0] == "validate":
        return run_validate_command(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)

    if args.list and not args.csv:
        history = load_history()
        if not history:
            logger.info("No workouts uploaded yet.")
            return 0
        logger.info(f"📋 Upload history ({len(history)} workouts):\n")
        for workout_datetime, info in sorted(history.items(), reverse=True):
            dt = parse_iso(workout_datetime)
            logger.info(f"  ✅ {dt.strftime('%Y-%m-%d %H:%M')} – {info.get('day', '')}")
            logger.info(
                f"     {info.get('working_sets', '?')} sets | "
                f"Uploaded: {info.get('uploaded_at', '?')[:19]}"
            )
            logger.info(f"     {', '.join(info.get('exercises', []))}\n")
        return 0

    if args.setup:
        try:
            garmin_setup()
            config = load_config()
            enable_calories = _prompt_yes_no(
                "Estimate calories for workouts?", default=config.get("calories_enabled", False)
            )
            config["calories_enabled"] = enable_calories
            if enable_calories:
                weight_kg = _prompt_weight_kg()
                config["fallback_weight_kg"] = round(weight_kg, 2)
            else:
                config["fallback_weight_kg"] = None
            save_config(config)
            logger.info("✅ Calorie settings saved")
            return 0
        except RuntimeError as exc:
            logger.error(f"❌ {exc}")
            return 1

    if not args.csv:
        parser.print_help()
        return 1

    try:
        # Load all rows from the CSV; filtering is handled downstream
        rows = parse_csv(Path(args.csv))
    except (FileNotFoundError, ValueError) as exc:
        logger.error(f"❌ {exc}")
        return 1

    logger.info(f"📂 Reading {args.csv}...")
    workouts = group_workouts(rows)
    logger.info(f"   {len(workouts)} workout(s), {len(rows)} total rows")

    new_workouts = get_new_workouts(workouts, force=args.force)
    skipped = len(workouts) - len(new_workouts)
    if skipped > 0 and not args.force:
        logger.info(f"   ⭐️  {skipped} already uploaded")
    logger.info(f"   🆕 {len(new_workouts)} new\n")

    if args.list:
        history = load_history()
        for workout_datetime, sets in workouts.items():
            logger.info(format_workout_summary(workout_datetime, sets, workout_datetime in history))
            logger.info("")
        return 0

    target = new_workouts if not args.force else workouts
    if not target:
        logger.info("Nothing new to upload. Use --force to re-upload.")
        return 0

    if args.date:
        selected = [(key, value) for key, value in target.items() if args.date in key]
        if not selected:
            logger.error(f"❌ No workout found matching: {args.date}")
            logger.info("   Use --list to see available dates.")
            return 1
    elif args.all:
        selected = list(target.items())
    else:
        key = list(target.keys())[0]
        selected = [(key, target[key])]

    if args.dry_run:
        logger.info("🔍 Dry run – would upload:\n")
        for workout_datetime, sets in selected:
            logger.info(format_workout_summary(workout_datetime, sets, False))
            logger.info(f"     Would generate FIT: {len(sets)} sets")
            logger.info("")
        logger.info("Run without --dry-run to proceed.")
        return 0

    try:
        local_tz = resolve_timezone(args.timezone)
    except ValueError as exc:
        logger.error(f"❌ {exc}")
        return 1

    config = load_config()
    calories_enabled = bool(config.get("calories_enabled"))
    fallback_weight_kg = config.get("fallback_weight_kg")
    resolved_weight_kg: float | None = None
    if calories_enabled:
        try:
            resolved_weight_kg = fetch_latest_weight_kg()
        except RuntimeError as exc:
            logger.warning(f"⚠️  Garmin weight fetch failed: {exc}")
        if resolved_weight_kg is None and fallback_weight_kg is not None:
            try:
                resolved_weight_kg = float(fallback_weight_kg)
            except (TypeError, ValueError):
                resolved_weight_kg = None
        if resolved_weight_kg is None:
            logger.warning("⚠️  Calories enabled but no weight available; calories set to 0")

    failures: list[tuple[str, str]] = []

    for workout_datetime, sets in selected:
        dt = parse_iso(workout_datetime)
        day = sets[0].get("Day Name", "Workout")
        warmup_count = sum(
            1 for row in sets if (row.get("Is Warmup Set?") or "0").strip() == "1"
        )
        amrap_count = sum(
            1 for row in sets if (row.get("Is AMRAP?") or "0").strip() == "1"
        )
        exercises = list(OrderedDict.fromkeys(row.get("Exercise", "") for row in sets))

        logger.info(f"🏋️  {dt.strftime('%Y-%m-%d %H:%M')} – {day}")
        logger.info(f"   {', '.join(exercises)}")
        parts = [f"{len(sets)} sets"]
        if warmup_count:
            parts.append(f"{warmup_count} warmup")
        if amrap_count:
            parts.append(f"{amrap_count} AMRAP")
        logger.info(f"   {', '.join(parts)}")

        try:
            fit_bytes = build_fit_for_workout(
                sets,
                tzinfo=local_tz,
                calories_enabled=calories_enabled,
                weight_kg=resolved_weight_kg,
            )
        except Exception as exc:
            reason = f"build error: {exc}"
            logger.error(f"   ❌ {reason}")
            failures.append((workout_datetime, reason))
            logger.info("")
            continue
        logger.info(f"   FIT: {len(fit_bytes)} bytes")
        output_path = Path(args.output) if args.output else None
        wrote_temp_fit = False
        temp_fit_path: Path | None = None

        if output_path or args.no_upload:
            output_path = output_path or Path(f"liftosaur_{dt.strftime('%Y%m%d_%H%M')}.fit")
            output_path.write_bytes(fit_bytes)
            logger.info(f"   💾 Saved: {output_path}")
            file_for_validation = output_path
        else:
            # No explicit output requested; write to a temporary file for validation/upload
            tmp = tempfile.NamedTemporaryFile(prefix="liftosaur_", suffix=".fit", delete=False)
            temp_fit_path = Path(tmp.name)
            tmp.close()
            temp_fit_path.write_bytes(fit_bytes)
            wrote_temp_fit = True
            file_for_validation = temp_fit_path

        # Run validation unless explicitly skipped. Validation always runs after encoding,
        # even when --no-upload is provided.
        if args.skip_validation:
            logger.info("   ⚠️  Skipping FIT validation (user requested)")
            validation_ok = True
            validation_result = None
            validation_tool_missing = False
        else:
            logger.info("   🔍 Validating FIT file...")
            status, result = validate_fit_file(file_for_validation)
            validation_result = result
            if status is None:
                validation_ok = True
                validation_tool_missing = True
                logger.warning("   ⚠️ FitCSVTool.jar not found, skipping validation")
            elif status:
                validation_ok = True
                validation_tool_missing = False
                logger.info("   ✅ FIT file passed SDK validation")
            else:
                validation_ok = False
                validation_tool_missing = False
                logger.error("   ❌ FIT file failed validation:")
                if result and result.stdout:
                    logger.error("--- stdout ---")
                    logger.error(result.stdout.strip())
                if result and result.stderr:
                    logger.error("--- stderr ---")
                    logger.error(result.stderr.strip())

        if not validation_ok:
            if wrote_temp_fit and temp_fit_path is not None:
                try:
                    temp_fit_path.unlink(missing_ok=True)
                except Exception:
                    pass
            reason = "validation failed"
            if validation_result and getattr(validation_result, "stdout", None):
                try:
                    reason += f": stdout: {validation_result.stdout.strip()}"
                except Exception:
                    pass
            if validation_result and getattr(validation_result, "stderr", None):
                try:
                    reason += f" stderr: {validation_result.stderr.strip()}"
                except Exception:
                    pass
            logger.error(f"   ❌ {reason}")
            failures.append((workout_datetime, reason))
            logger.info("")
            continue

        # If --no-upload was provided, we stop here after validation (or skipping it).
        if args.no_upload:
            if wrote_temp_fit and temp_fit_path is not None:
                try:
                    temp_fit_path.unlink(missing_ok=True)
                except Exception:
                    pass
            logger.warning("   ⚠️  --no-upload specified; not uploading")
        else:
            logger.info("   ☁️  Uploading...")
            try:
                upload_to_garmin(fit_bytes)
                mark_uploaded(workout_datetime, sets)
            except RuntimeError as exc:
                reason = str(exc)
                logger.error(f"   ❌ {reason}")
                if wrote_temp_fit and temp_fit_path is not None:
                    try:
                        temp_fit_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                failures.append((workout_datetime, reason))
                logger.info("")
                continue

            if wrote_temp_fit and temp_fit_path is not None:
                try:
                    temp_fit_path.unlink(missing_ok=True)
                except Exception:
                    pass

        logger.info("")

    if failures:
        logger.error("Upload summary — failures:")
        for dt, reason in failures:
            logger.error(f"  {dt} : {reason}")
        return 1

    logger.info("Done! 🎉")
    return 0
