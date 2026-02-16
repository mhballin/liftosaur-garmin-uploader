"""CLI entry point."""

from __future__ import annotations

import argparse
import getpass
import logging
import re
import shutil
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

from .config import load_config, save_config
from .csv_parser import group_workouts, parse_csv
from .exercise.duration import lbs_to_kg
from .fit.utils import parse_iso, resolve_timezone
from .history import get_new_workouts, load_history, mark_uploaded
from .logging_config import setup_logging
from .profile import (
    get_default_profile,
    get_profile_dir,
    list_profiles,
    migrate_legacy_config,
    profile_exists,
    resolve_profile,
    set_default_profile,
)
from .uploader import fetch_latest_weight_kg, upload_to_garmin
from .workout_builder import build_fit_for_workout
from .validation import validate_fit_file
from .watcher import (
    get_default_watch_dir,
    install_watcher,
    uninstall_watcher,
    watcher_status,
)

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


def _prompt_choice(prompt: str, max_val: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print(f"Enter a number between 1 and {max_val}.")
            continue
        if 1 <= value <= max_val:
            return value
        print(f"Enter a number between 1 and {max_val}.")


def _default_profile_name() -> str:
    default_profile = get_default_profile()
    if default_profile:
        return default_profile

    raw_user = getpass.getuser().strip().lower()
    cleaned = re.sub(r"[^a-z0-9_]", "_", raw_user)
    cleaned = cleaned.strip("_")
    return cleaned or "default"


def _prompt_profile_name(default_name: str) -> str:
    while True:
        raw = input(f"Profile name (default: {default_name}): ").strip()
        name = raw or default_name
        name = name.strip()
        if not name:
            print("Profile name is required.")
            continue
        if not re.fullmatch(r"[a-z0-9_]+", name):
            print("Use lowercase letters, numbers, and underscores only.")
            continue
        return name


def _prompt_profile_name_validated(prompt: str = "New name: ") -> str:
    while True:
        name = input(prompt).strip()
        if not name:
            print("Profile name is required.")
            continue
        if not re.fullmatch(r"[a-z0-9_]+", name):
            print("Use lowercase letters, numbers, and underscores only.")
            continue
        return name


def _prompt_watch_dir() -> Path:
    detected_dir = get_default_watch_dir()
    if detected_dir and _prompt_yes_no(
        f"Watch this folder? {detected_dir}",
        default=True,
    ):
        return detected_dir

    while True:
        raw_path = input("Path to Liftosaur CSV folder: ").strip()
        candidate = Path(raw_path).expanduser()
        if candidate.exists():
            return candidate
        print("Folder not found. Please enter a valid path.")


def _prompt_poll_interval(default_seconds: int) -> int:
    default_minutes = max(1, int(default_seconds // 60))
    while True:
        raw = input(
            f"Check for new files every how many minutes? (default: {default_minutes}): "
        ).strip()
        if not raw:
            return default_minutes * 60
        try:
            minutes = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minutes <= 0:
            print("Please enter a positive number.")
            continue
        return minutes * 60


def _install_watcher_flow(profile_name: str, profile_dir: Path, config: dict) -> str:
    watch_dir = _prompt_watch_dir()
    default_interval = config.get("poll_interval", 300)
    try:
        default_seconds = int(default_interval)
    except (TypeError, ValueError):
        default_seconds = 300
    if default_seconds <= 0:
        default_seconds = 300
    poll_interval = _prompt_poll_interval(default_seconds)
    python_path = sys.executable
    installed = install_watcher(
        profile_name,
        profile_dir,
        watch_dir,
        python_path,
        poll_interval=poll_interval,
    )
    if not installed:
        return "disabled"

    config["watch_dir"] = str(watch_dir)
    config["poll_interval"] = poll_interval
    save_config(config, profile_dir)
    home_dir = Path.home()
    if watch_dir.is_relative_to(home_dir):
        display_path = f"~/{watch_dir.relative_to(home_dir)}"
    else:
        display_path = str(watch_dir)
    return f"active ({display_path})"


def _print_profiles_with_details() -> list[str]:
    profiles = list_profiles()
    if not profiles:
        logger.info("No profiles configured. Run --setup to get started.")
        return []

    default_profile = get_default_profile()
    logger.info("🏋️ Profile Manager")
    logger.info("══════════════════════════════")
    logger.info("")
    for name in profiles:
        profile_dir = get_profile_dir(name)
        if name == default_profile:
            logger.info(f"  ⭐ {name} (default)")
        else:
            logger.info(f"     {name}")
        try:
            config = load_config(profile_dir)
            history = load_history(profile_dir)
            workouts_uploaded = len(history)
            calories_enabled = bool(config.get("calories_enabled"))
            fallback_weight = config.get("fallback_weight_kg")
            if calories_enabled:
                if fallback_weight is not None:
                    calories_summary = f"enabled ({float(fallback_weight):.1f} kg)"
                else:
                    calories_summary = "enabled"
            else:
                calories_summary = "disabled"

            uploaded_values = [
                info.get("uploaded_at")
                for info in history.values()
                if info.get("uploaded_at")
            ]
            if uploaded_values:
                latest_upload = max(uploaded_values)
                last_upload = latest_upload.split("T", 1)[0]
            else:
                last_upload = "No uploads yet"

            logger.info(f"     Workouts uploaded: {workouts_uploaded}")
            logger.info(f"     Calories: {calories_summary}")
            logger.info(f"     Last upload: {last_upload}")
        except Exception as exc:
            logger.warning(f"     ⚠️  Failed to read profile data: {exc}")
        logger.info("")
    return profiles


def _confirm_reconfigure(profile_name: str) -> bool:
    raw = input(f"Profile '{profile_name}' already exists. Reconfigure? (y/N) ").strip().lower()
    return raw in {"y", "yes"}


def _authenticate_garmin(email: str, password: str, garth_dir: Path) -> None:
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    try:
        garth.login(email, password)
        garth_dir.mkdir(parents=True, exist_ok=True)
        garth.save(str(garth_dir))
    except Exception as exc:
        raise RuntimeError(f"Authentication failed: {exc}") from exc


def _print_setup_summary(
    profile_name: str,
    email: str,
    calories_summary: str,
    watcher_summary: str,
    default_summary: str,
) -> None:
    lines = [
        f" Profile:   {profile_name}",
        f" Email:     {email}",
        f" Calories:  {calories_summary}",
        f" Watcher:   {watcher_summary}",
        f" Default:   {default_summary}",
    ]
    inner_width = max(30, max(len(line) for line in lines))
    print("✅ Setup complete!")
    print("┌" + "─" * inner_width + "┐")
    for line in lines:
        print("│" + line.ljust(inner_width) + "│")
    print("└" + "─" * inner_width + "┘")


def _run_setup_wizard() -> int:
    print("\n🏋️ Liftosaur → Garmin Setup\n" + "=" * 35)

    profiles = list_profiles()
    if profiles:
        print(f"Existing profiles: {', '.join(profiles)}")

    default_name = _default_profile_name()
    profile_name = _prompt_profile_name(default_name)

    if profile_exists(profile_name) and not _confirm_reconfigure(profile_name):
        print("Setup cancelled.")
        return 0

    profile_dir = get_profile_dir(profile_name)
    garth_dir = profile_dir / "garth"

    while True:
        email = input("Garmin Connect email: ").strip()
        password = getpass.getpass("Garmin Connect password: ")
        try:
            _authenticate_garmin(email, password, garth_dir)
            print("✅ Garmin authenticated!")
            break
        except RuntimeError as exc:
            print(f"❌ {exc}")
            if not _prompt_yes_no("Retry authentication?", default=False):
                return 1

    config = load_config(profile_dir)
    enable_calories = _prompt_yes_no(
        "Estimate calories for workouts?",
        default=bool(config.get("calories_enabled")),
    )
    config["calories_enabled"] = enable_calories
    if enable_calories:
        weight_kg = _prompt_weight_kg()
        config["fallback_weight_kg"] = round(weight_kg, 2)
    else:
        config["fallback_weight_kg"] = None
    save_config(config, profile_dir)

    watcher_summary = "disabled"
    if _prompt_yes_no("Set up automatic file watching?", default=True):
        watcher_summary = _install_watcher_flow(profile_name, profile_dir, config)

    total_profiles = len(set(profiles + [profile_name]))
    default_yes = total_profiles == 1
    set_default = _prompt_yes_no("Set as default profile?", default=default_yes)
    if set_default:
        set_default_profile(profile_name)

    if enable_calories:
        weight_display = config.get("fallback_weight_kg")
        calories_summary = f"enabled ({weight_display:.1f} kg)" if weight_display else "enabled"
    else:
        calories_summary = "disabled"

    default_summary = "yes" if set_default else "no"
    _print_setup_summary(
        profile_name,
        email,
        calories_summary,
        watcher_summary,
        default_summary,
    )
    return 0


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
    parser.add_argument("--profile", "-p", help="User profile name")
    parser.add_argument(
        "--profiles",
        action="store_true",
        help="Manage user profiles",
    )
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

    migrate_legacy_config()
    
    if args_list and args_list[0] == "validate":
        return run_validate_command(args_list[1:])

    parser = build_parser()
    args = parser.parse_args(args_list)

    if args.profiles:
        while True:
            profiles = _print_profiles_with_details()
            if profiles:
                logger.info("──────────────────────────────")
                logger.info("What would you like to do?\n")
                logger.info("  [1] Add new profile")
                logger.info("  [2] Switch default profile")
                logger.info("  [3] Rename a profile")
                logger.info("  [4] Delete a profile")
                logger.info("  [5] Manage file watcher")
                logger.info("  [6] Exit\n")
                choice = _prompt_choice("Choice (1-6): ", 6)
            else:
                logger.info("──────────────────────────────")
                logger.info("What would you like to do?\n")
                logger.info("  [1] Add new profile")
                logger.info("  [5] Exit\n")
                choice = _prompt_choice("Choice (1-5): ", 5)
                if choice not in {1, 5}:
                    print("Enter a number between 1 and 5.")
                    continue

            if choice == 1:
                _run_setup_wizard()
                continue

            if choice == 2:
                if len(profiles) <= 1:
                    logger.info("Only one profile exists.")
                    continue
                logger.info("Select a profile:")
                for idx, name in enumerate(profiles, start=1):
                    logger.info(f"  [{idx}] {name}")
                selection = _prompt_choice("Choice: ", len(profiles))
                selected = profiles[selection - 1]
                set_default_profile(selected)
                logger.info(f"✅ Default profile set to '{selected}'")
                continue

            if choice == 3:
                if not profiles:
                    logger.info("No profiles to rename.")
                    continue
                logger.info("Select a profile to rename:")
                for idx, name in enumerate(profiles, start=1):
                    logger.info(f"  [{idx}] {name}")
                selection = _prompt_choice("Choice: ", len(profiles))
                old_name = profiles[selection - 1]
                new_name = _prompt_profile_name_validated("New name: ")
                if profile_exists(new_name):
                    logger.error(f"❌ Profile already exists: {new_name}")
                    continue
                old_dir = get_profile_dir(old_name)
                new_dir = get_profile_dir(new_name)
                old_dir.rename(new_dir)
                default_profile = get_default_profile()
                if default_profile == old_name:
                    set_default_profile(new_name)
                logger.info(f"✅ Renamed '{old_name}' to '{new_name}'")
                continue

            if choice == 4:
                if not profiles:
                    logger.info("No profiles to delete.")
                    continue
                logger.info("Select a profile to delete:")
                for idx, name in enumerate(profiles, start=1):
                    logger.info(f"  [{idx}] {name}")
                selection = _prompt_choice("Choice: ", len(profiles))
                profile_name = profiles[selection - 1]
                logger.info(
                    "⚠️  This will permanently delete all data for "
                    f"'{profile_name}' (config, history, Garmin tokens)."
                )
                confirmation = input(
                    "Type the profile name to confirm: "
                ).strip()
                if confirmation != profile_name:
                    logger.info("Delete cancelled.")
                    continue
                profile_dir = get_profile_dir(profile_name)
                try:
                    uninstall_watcher(profile_name, profile_dir)
                except Exception as exc:
                    logger.warning(f"⚠️  Failed to uninstall watcher: {exc}")
                shutil.rmtree(profile_dir)
                default_profile = get_default_profile()
                if default_profile == profile_name:
                    default_path = Path("~/.liftosaur_garmin/default_profile.txt").expanduser()
                    default_path.unlink(missing_ok=True)
                    logger.info("ℹ️  No default profile set. Use --profiles to set one.")
                logger.info(f"✅ Profile '{profile_name}' deleted")
                continue

            if choice == 5:
                if not profiles:
                    return 0
                default_profile = get_default_profile()
                if default_profile in profiles:
                    watcher_profile = default_profile
                else:
                    logger.info("Select a profile:")
                    for idx, name in enumerate(profiles, start=1):
                        logger.info(f"  [{idx}] {name}")
                    selection = _prompt_choice("Choice: ", len(profiles))
                    watcher_profile = profiles[selection - 1]

                while True:
                    status = watcher_status(watcher_profile)
                    logger.info(f"File Watcher — {watcher_profile}")
                    logger.info(f"Status: {status}\n")
                    logger.info("  [1] Reinstall watcher")
                    logger.info("  [2] Stop and remove watcher")
                    logger.info("  [3] View watcher log (last 20 lines)")
                    logger.info("  [4] Back to main menu\n")
                    action = _prompt_choice("Choice (1-4): ", 4)

                    if action == 1:
                        watcher_dir = get_profile_dir(watcher_profile)
                        config = load_config(watcher_dir)
                        _install_watcher_flow(watcher_profile, watcher_dir, config)
                        continue

                    if action == 2:
                        if not _prompt_yes_no(
                            f"Stop and remove watcher for '{watcher_profile}'?",
                            default=False,
                        ):
                            continue
                        watcher_dir = get_profile_dir(watcher_profile)
                        uninstall_watcher(watcher_profile, watcher_dir)
                        continue

                    if action == 3:
                        watcher_dir = get_profile_dir(watcher_profile)
                        log_path = watcher_dir / "watcher.log"
                        if not log_path.exists():
                            logger.info("No watcher logs yet.")
                            continue
                        content = log_path.read_text(encoding="utf-8", errors="replace")
                        lines = [line for line in content.splitlines() if line.strip()]
                        if not lines:
                            logger.info("No watcher logs yet.")
                            continue
                        logger.info("Watcher log (last 20 lines):")
                        for line in lines[-20:]:
                            logger.info(line)
                        continue

                    if action == 4:
                        break
                continue

            if choice == 6:
                return 0

    if args.list and not args.csv:
        profile_name: str | None = None
        profile_dir: Path | None = None
        try:
            profile_name = resolve_profile(args.profile)
            profile_dir = get_profile_dir(profile_name)
        except RuntimeError as exc:
            logger.error(f"❌ {exc}")
            return 1
        if profile_dir is None:
            logger.error("❌ Profile resolution failed.")
            return 1
        history = load_history(profile_dir)
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
        return _run_setup_wizard()

    profile_name: str | None = None
    profile_dir: Path | None = None
    try:
        profile_name = resolve_profile(args.profile)
        profile_dir = get_profile_dir(profile_name)
    except RuntimeError as exc:
        logger.error(f"❌ {exc}")
        return 1

    if profile_dir is None:
        logger.error("❌ Profile resolution failed.")
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

    new_workouts = get_new_workouts(workouts, force=args.force, profile_dir=profile_dir)
    skipped = len(workouts) - len(new_workouts)
    if skipped > 0 and not args.force:
        logger.info(f"   ⭐️  {skipped} already uploaded")
    logger.info(f"   🆕 {len(new_workouts)} new\n")

    if args.list:
        history = load_history(profile_dir)
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

    config = load_config(profile_dir)
    calories_enabled = bool(config.get("calories_enabled"))
    fallback_weight_kg = config.get("fallback_weight_kg")
    resolved_weight_kg: float | None = None
    if calories_enabled:
        try:
            resolved_weight_kg = fetch_latest_weight_kg(profile_dir)
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
                upload_to_garmin(fit_bytes, profile_dir)
                mark_uploaded(workout_datetime, sets, profile_dir)
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
