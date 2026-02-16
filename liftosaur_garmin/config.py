"""Config helpers for Liftosaur Garmin uploader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict = {
    "calories_enabled": False,
    "fallback_weight_kg": None,
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
