"""Profile management helpers."""

from __future__ import annotations

from pathlib import Path
import shutil
import logging


logger = logging.getLogger(__name__)


def get_profiles_dir() -> Path:
    """Return the root profiles directory."""
    profiles_dir = Path("~/.liftosaur_garmin/profiles").expanduser()
    logger.debug("Resolved profiles root: %s", profiles_dir)
    return profiles_dir


def get_profile_dir(name: str) -> Path:
    """Return the directory path for a specific profile."""
    profile_dir = get_profiles_dir() / name
    logger.debug("Resolved profile dir for '%s': %s", name, profile_dir)
    return profile_dir


def profile_exists(name: str) -> bool:
    """Return True if the profile directory exists."""
    exists = get_profile_dir(name).is_dir()
    logger.debug("Profile '%s' exists: %s", name, exists)
    return exists


def list_profiles() -> list[str]:
    """List all profile directory names."""
    profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        logger.debug("Profiles directory does not exist: %s", profiles_dir)
        return []

    names = sorted(
        entry.name for entry in profiles_dir.iterdir() if entry.is_dir()
    )
    logger.debug("Found profiles: %s", names)
    return names


def _get_default_profile_path() -> Path:
    """Return the path to the default profile file."""
    default_path = Path("~/.liftosaur_garmin/default_profile.txt").expanduser()
    logger.debug("Resolved default profile path: %s", default_path)
    return default_path


def get_default_profile() -> str | None:
    """Return the default profile name if set, otherwise None."""
    default_path = _get_default_profile_path()
    if not default_path.exists():
        logger.debug("Default profile file missing: %s", default_path)
        return None

    name = default_path.read_text(encoding="utf-8").strip()
    if not name:
        logger.debug("Default profile file empty: %s", default_path)
        return None

    logger.debug("Default profile resolved to: %s", name)
    return name


def set_default_profile(name: str) -> None:
    """Persist the default profile name."""
    default_path = _get_default_profile_path()
    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_text(f"{name}\n", encoding="utf-8")
    logger.debug("Default profile set to '%s' at %s", name, default_path)


def resolve_profile(cli_arg: str | None) -> str:
    """Resolve the profile name from CLI arg or default settings."""
    if cli_arg:
        logger.debug("Using CLI profile: %s", cli_arg)
        return cli_arg

    default_name = get_default_profile()
    if default_name:
        logger.debug("Using default profile: %s", default_name)
        return default_name

    message = (
        "No profile specified and no current profile is selected. "
        "Run with --setup to create one or --manage-profiles to choose one."
    )
    logger.debug("Profile resolution failed: %s", message)
    raise RuntimeError(message)


def migrate_legacy_config() -> str | None:
    """Migrate legacy config/history files into a default profile if needed."""
    base_dir = Path("~/.liftosaur_garmin").expanduser()
    profiles_dir = base_dir / "profiles"
    if profiles_dir.exists():
        return None

    config_path = base_dir / "config.json"
    history_path = base_dir / "history.json"
    if not config_path.exists() or not history_path.exists():
        return None

    profile_name = "default"
    profile_dir = profiles_dir / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    for path in (config_path, history_path, base_dir / "processed_files.txt"):
        if path.exists():
            path.replace(profile_dir / path.name)

    garth_source = Path("~/.garth").expanduser()
    if garth_source.exists() and garth_source.is_dir():
        shutil.copytree(garth_source, profile_dir / "garth", dirs_exist_ok=True)

    set_default_profile(profile_name)
    print("📦 Migrated existing config to profile: default")
    return profile_name
