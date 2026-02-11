"""CLI entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
import tempfile

from .csv_parser import group_workouts, parse_csv
from .fit.utils import parse_iso, resolve_timezone
from .history import get_new_workouts, load_history, mark_uploaded
from .uploader import garmin_setup, upload_to_garmin
from .workout_builder import build_fit_for_workout
from .validation import validate_fit_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liftosaur-garmin",
        description="Convert Liftosaur CSV workouts to Garmin FIT",
    )
    parser.add_argument("csv", nargs="?", help="Path to Liftosaur CSV export")
    parser.add_argument("--setup", action="store_true", help="Authenticate Garmin Connect")
    parser.add_argument("--status", action="store_true", help="Show upload history")
    parser.add_argument("--list", action="store_true", help="List workouts with status")
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
        print(f"✗ FIT file not found: {fit_path}")
        return 1

    status, result = validate_fit_file(fit_path, keep_csv=args.keep_csv)
    if status is None:
        print("✗ FitCSVTool.jar not found.")
        print(
            "Please download the Garmin FIT SDK and copy tools/FitCSVTool.jar into this project."
        )
        return 2

    if status:
        print("✓ FIT file is valid")
        return 0

    # validation failed
    print("✗ FIT file validation failed")
    if result and result.stdout:
        print("--- stdout ---")
        print(result.stdout.strip())
    if result and result.stderr:
        print("--- stderr ---")
        print(result.stderr.strip())
    return 1


def format_workout_summary(workout_datetime: str, sets: list[dict], uploaded: bool) -> str:
    """Format a single workout for display."""
    dt = parse_iso(workout_datetime)
    day = sets[0].get("Day Name", "")
    working = [
        row for row in sets if (row.get("Is Warmup Set?") or "0").strip() != "1"
    ]
    warmups = len(sets) - len(working)
    exercises = list(OrderedDict.fromkeys(row.get("Exercise", "") for row in working))
    icon = "✅" if uploaded else "🆕"
    lines = [
        f"  {icon} {dt.strftime('%Y-%m-%d %H:%M')} – {day}",
        f"     {len(working)} working sets, {warmups} warmup sets",
        f"     {', '.join(exercises)}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    if args_list and args_list[0] == "validate":
        return run_validate_command(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)

    if args.status:
        history = load_history()
        if not history:
            print("No workouts uploaded yet.")
            return 0
        print(f"📋 Upload history ({len(history)} workouts):\n")
        for workout_datetime, info in sorted(history.items(), reverse=True):
            dt = parse_iso(workout_datetime)
            print(f"  ✅ {dt.strftime('%Y-%m-%d %H:%M')} – {info.get('day', '')}")
            print(
                f"     {info.get('working_sets', '?')} sets | "
                f"Uploaded: {info.get('uploaded_at', '?')[:19]}"
            )
            print(f"     {', '.join(info.get('exercises', []))}\n")
        return 0

    if args.setup:
        try:
            garmin_setup()
            return 0
        except RuntimeError as exc:
            print(f"❌ {exc}")
            return 1

    if not args.csv:
        parser.print_help()
        return 1

    try:
        # Load all rows from the CSV; filtering is handled downstream
        rows = parse_csv(Path(args.csv))
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return 1

    print(f"📂 Reading {args.csv}...")
    workouts = group_workouts(rows)
    print(f"   {len(workouts)} workout(s), {len(rows)} total rows")

    new_workouts = get_new_workouts(workouts, force=args.force)
    skipped = len(workouts) - len(new_workouts)
    if skipped > 0 and not args.force:
        print(f"   ⭐️  {skipped} already uploaded")
    print(f"   🆕 {len(new_workouts)} new\n")

    if args.list:
        history = load_history()
        for workout_datetime, sets in workouts.items():
            print(format_workout_summary(workout_datetime, sets, workout_datetime in history))
            print()
        return 0

    target = new_workouts if not args.force else workouts
    if not target:
        print("Nothing new to upload. Use --force to re-upload.")
        return 0

    if args.date:
        selected = [(key, value) for key, value in target.items() if args.date in key]
        if not selected:
            print(f"❌ No workout found matching: {args.date}")
            print("   Use --list to see available dates.")
            return 1
    elif args.all:
        selected = list(target.items())
    else:
        key = list(target.keys())[0]
        selected = [(key, target[key])]

    if args.dry_run:
        print("🔍 Dry run – would upload:\n")
        for workout_datetime, sets in selected:
            print(format_workout_summary(workout_datetime, sets, False))
            working = [
                row
                for row in sets
                if (row.get("Is Warmup Set?") or "0").strip() != "1"
            ]
            print(f"     Would generate FIT: ~{len(working)} active sets")
            print()
        print("Run without --dry-run to proceed.")
        return 0

    try:
        local_tz = resolve_timezone(args.timezone)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1

    failures: list[tuple[str, str]] = []

    for workout_datetime, sets in selected:
        dt = parse_iso(workout_datetime)
        day = sets[0].get("Day Name", "Workout")
        working = [
            row
            for row in sets
            if (row.get("Is Warmup Set?") or "0").strip() != "1"
        ]
        exercises = list(OrderedDict.fromkeys(row.get("Exercise", "") for row in working))

        print(f"🏋️  {dt.strftime('%Y-%m-%d %H:%M')} – {day}")
        print(f"   {', '.join(exercises)}")
        print(
            f"   {len(working)} working sets ({len(sets) - len(working)} warmups skipped)"
        )

        try:
            fit_bytes = build_fit_for_workout(sets, tzinfo=local_tz)
        except Exception as exc:
            reason = f"build error: {exc}"
            print(f"   ❌ {reason}")
            failures.append((workout_datetime, reason))
            print()
            continue
        print(f"   FIT: {len(fit_bytes)} bytes")
        output_path = Path(args.output) if args.output else None
        wrote_temp_fit = False
        temp_fit_path: Path | None = None

        if output_path or args.no_upload:
            output_path = output_path or Path(f"liftosaur_{dt.strftime('%Y%m%d_%H%M')}.fit")
            output_path.write_bytes(fit_bytes)
            print(f"   💾 Saved: {output_path}")
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
            print("   ⚠️  Skipping FIT validation (user requested)")
            validation_ok = True
            validation_result = None
            validation_tool_missing = False
        else:
            print("   🔍 Validating FIT file...")
            status, result = validate_fit_file(file_for_validation)
            validation_result = result
            if status is None:
                validation_ok = True
                validation_tool_missing = True
                print("   ⚠️ FitCSVTool.jar not found, skipping validation")
            elif status:
                validation_ok = True
                validation_tool_missing = False
                print("   ✅ FIT file passed SDK validation")
            else:
                validation_ok = False
                validation_tool_missing = False
                print("   ❌ FIT file failed validation:")
                if result and result.stdout:
                    print("--- stdout ---")
                    print(result.stdout.strip())
                if result and result.stderr:
                    print("--- stderr ---")
                    print(result.stderr.strip())

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
            print(f"   ❌ {reason}")
            failures.append((workout_datetime, reason))
            print()
            continue

        # If --no-upload was provided, we stop here after validation (or skipping it).
        if args.no_upload:
            if wrote_temp_fit and temp_fit_path is not None:
                try:
                    temp_fit_path.unlink(missing_ok=True)
                except Exception:
                    pass
            print("   ⚠️  --no-upload specified; not uploading")
        else:
            print("   ☁️  Uploading...")
            try:
                upload_to_garmin(fit_bytes)
                mark_uploaded(workout_datetime, sets)
            except RuntimeError as exc:
                reason = str(exc)
                print(f"   ❌ {reason}")
                if wrote_temp_fit and temp_fit_path is not None:
                    try:
                        temp_fit_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                failures.append((workout_datetime, reason))
                print()
                continue

            if wrote_temp_fit and temp_fit_path is not None:
                try:
                    temp_fit_path.unlink(missing_ok=True)
                except Exception:
                    pass

        print()

    if failures:
        print("Upload summary — failures:")
        for dt, reason in failures:
            print(f"  {dt} : {reason}")
        return 1

    print("Done! 🎉")
    return 0
