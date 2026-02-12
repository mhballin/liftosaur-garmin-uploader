"""Logging configuration for liftosaur_garmin package."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for liftosaur_garmin.
    
    Sets up:
    - Console handler (stdout) at INFO level (or DEBUG if verbose=True)
      Format: %(message)s (clean CLI output)
    - File handler at DEBUG level to ~/.liftosaur_garmin/logs/liftosaur_garmin.log
      Format: %(asctime)s [%(levelname)s] %(name)s - %(message)s
    - Rotating file handler (maxBytes=1MB, backupCount=3)
    
    Args:
        verbose: If True, set console level to DEBUG instead of INFO
    """
    logger = logging.getLogger("liftosaur_garmin")
    logger.setLevel(logging.DEBUG)  # Logger captures all; handlers filter
    
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # ── Console (stdout) handler ────────────────────────────────────────
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ── File (rotating) handler ────────────────────────────────────────
    log_dir = Path.home() / ".liftosaur_garmin" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "liftosaur_garmin.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
