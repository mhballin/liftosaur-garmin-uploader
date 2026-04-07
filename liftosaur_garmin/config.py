"""Config helpers for Liftosaur Garmin uploader."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict = {
    "calories_enabled": False,
    "fallback_weight_kg": None,
    "poll_interval": 300,
    "temp_dir_retention_hours": 24,
    "liftosaur_api_enabled": False,
    "liftosaur_api_key": None,
    "liftosaur_api_poll_enabled": False,
    "liftosaur_api_last_synced_datetime": None,
}


def load_config(profile_dir: Path) -> dict:
    """Load config from disk, returning defaults when missing."""
    config_path = profile_dir / "config.json"
    if not config_path.exists():
        logger.debug("No config found at %s, using defaults", config_path)
        return DEFAULT_CONFIG.copy()

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read config; using defaults: {exc}")
        return DEFAULT_CONFIG.copy()

    merged = DEFAULT_CONFIG.copy()
    if isinstance(config, dict):
        merged.update(config)
    return merged


def save_config(config: dict, profile_dir: Path) -> None:
    """Persist config to disk."""
    config_path = profile_dir / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    logger.debug("Saved config to %s", config_path)


def get_temp_dir(profile_dir: Path) -> Path:
    """Get or create the temp directory for a profile."""
    temp_dir = profile_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def cleanup_old_temp_files(temp_dir: Path, retention_hours: int = 24) -> None:
    """Remove temp files older than retention_hours.

    Runs opportunistically to prevent unbounded growth of temp directory.
    Logs removed files at debug level.
    """
    if not temp_dir.exists():
        return

    now = time.time()
    deadline = now - (retention_hours * 3600)
    removed = 0

    try:
        for file in temp_dir.glob("*.csv"):
            try:
                mtime = file.stat().st_mtime
                if mtime < deadline:
                    file.unlink()
                    logger.debug(f"Cleaned up old temp file: {file.name}")
                    removed += 1
            except OSError as exc:
                logger.debug(f"Failed to clean up {file.name}: {exc}")
    except OSError as exc:
        logger.debug(f"Failed to scan temp directory: {exc}")

    if removed > 0:
        logger.debug(f"Cleaned up {removed} old temp file(s)")
