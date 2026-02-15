"""Config helpers for Liftosaur Garmin uploader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".liftosaur_garmin" / "config.json"

DEFAULT_CONFIG: dict = {
    "calories_enabled": False,
    "fallback_weight_kg": None,
}


def load_config() -> dict:
    """Load config from disk, returning defaults when missing."""
    if not CONFIG_PATH.exists():
        logger.debug("No config found, using defaults")
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read config; using defaults: {exc}")
        return DEFAULT_CONFIG.copy()

    merged = DEFAULT_CONFIG.copy()
    if isinstance(config, dict):
        merged.update(config)
    return merged


def save_config(config: dict) -> None:
    """Persist config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    logger.debug("Saved config")
