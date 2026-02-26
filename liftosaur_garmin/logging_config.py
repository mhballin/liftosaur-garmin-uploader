"""Logging configuration for liftosaur_garmin package.

This module implements industry-standard logging with:
- Structured, machine-readable format
- Automatic log rotation and cleanup
- Per-module log level control
- Reduced verbosity (DEBUG reserved for development)
- Consistent formatting across console and files
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────
# Module Log Levels
# ────────────────────────────────────────────────────────────────────────────
# Control verbosity for specific modules. Most modules log at INFO/WARNING
# level, but high-chatter modules (e.g., exercise.mapping) are limited to
# WARNING to reduce file size and noise in logs.
_MODULE_LEVELS: dict[str, int] = {
    # High-verbosity modules: limited to WARNING in production
    "liftosaur_garmin.exercise.mapping": logging.WARNING,
    "liftosaur_garmin.fit.encoder": logging.WARNING,
    
    # Standard modules: INFO/DEBUG as configured
    "liftosaur_garmin.csv_parser": logging.DEBUG,
    "liftosaur_garmin.uploader": logging.DEBUG,
    "liftosaur_garmin.validation": logging.DEBUG,
    "liftosaur_garmin.watcher": logging.DEBUG,
}


def _apply_module_levels() -> None:
    """Set per-module log levels to control verbosity."""
    for module_name, level in _MODULE_LEVELS.items():
        logging.getLogger(module_name).setLevel(level)


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging for liftosaur_garmin.
    
    Sets up:
    - Console handler: INFO or DEBUG (if verbose). Format: %(message)s
    - File handler: DEBUG level. Format: ISO 8601 timestamp + structured fields
    - Automatic rotation: 5MB per file, 5 backups (~25MB total)
    - Per-module log levels: Reduce verbosity for high-chatter modules
    
    Args:
        verbose: If True, set console level to DEBUG instead of INFO
    """
    logger = logging.getLogger("liftosaur_garmin")
    logger.setLevel(logging.DEBUG)  # Root logger captures all; handlers filter
    
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # ────────────────────────────────────────────────────────────────────────
    # Console Handler (stdout)
    # ────────────────────────────────────────────────────────────────────────
    # Purpose: User-facing output. Keeps emoji and formatted messages for CLI.
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ────────────────────────────────────────────────────────────────────────
    # File Handler (rotating, structured)
    # ────────────────────────────────────────────────────────────────────────
    # Purpose: Structured logs for debugging and analysis.
    # Rotation: 5MB per file × 5 backups = ~25MB max. Prevents disk bloat.
    log_dir = Path.home() / ".liftosaur_garmin" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "liftosaur_garmin.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB per file
        backupCount=5               # Keep 5 backups (25MB total)
    )
    file_handler.setLevel(logging.DEBUG)
    
    # ISO 8601 timestamps + structured fields for machine readability
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # ────────────────────────────────────────────────────────────────────────
    # Apply per-module log levels
    # ────────────────────────────────────────────────────────────────────────
    _apply_module_levels()
