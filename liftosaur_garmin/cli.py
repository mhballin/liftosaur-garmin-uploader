"""CLI entry point."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

from .csv_parser import group_workouts, read_csv
from .fit.utils import parse_iso
from .history import get_new_workouts, load_history, mark_uploaded
from .uploader import garmin_setup, upload_to_garmin
from .workout_builder import build_fit_for_workout


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
    return parser


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
    parser = build_parser()
    args = parser.parse_args(argv)

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
        rows = read_csv(Path(args.csv))
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

        fit_bytes = build_fit_for_workout(sets)
        print(f"   FIT: {len(fit_bytes)} bytes")

        output_path = Path(args.output) if args.output else None
        if output_path or args.no_upload:
            output_path = output_path or Path(f"liftosaur_{dt.strftime('%Y%m%d_%H%M')}.fit")
            output_path.write_bytes(fit_bytes)
            print(f"   💾 Saved: {output_path}")

        if not args.no_upload:
            print("   ☁️  Uploading...")
            try:
                upload_to_garmin(fit_bytes)
                mark_uploaded(workout_datetime, sets)
            except RuntimeError as exc:
                print(f"   ❌ {exc}")
                return 1

        print()

    print("Done! 🎉")
    return 0
