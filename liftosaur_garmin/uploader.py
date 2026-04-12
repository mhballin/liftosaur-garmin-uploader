"""Garmin Connect upload logic."""

from __future__ import annotations

import getpass
import logging
import sys
import time
from pathlib import Path

from .garmin_client import get_garmin_client

logger = logging.getLogger(__name__)

AUTH_ERROR_HINTS = (
    "401",
    "unauthorized",
    "forbidden",
    "login",
    "expired",
    "token",
    "authenticate",
    "authorization",
)
RATE_LIMIT_HINTS = ("429", "rate limit", "too many requests", "throttle")


def _matches_any(message: str, hints: tuple[str, ...]) -> bool:
    lowered = message.lower()
    return any(hint in lowered for hint in hints)


def _is_auth_error(message: str) -> bool:
    return _matches_any(message, AUTH_ERROR_HINTS)


def _is_rate_limited(message: str) -> bool:
    return _matches_any(message, RATE_LIMIT_HINTS)


def _require_interactive(non_interactive: bool, context: str) -> None:
    if non_interactive:
        reason = "stdin is not interactive" if not sys.stdin.isatty() else "--non-interactive was set"
        raise RuntimeError(
            f"{context}: Garmin authentication cannot prompt in background mode "
            f"({reason}). Run `python -m liftosaur_garmin --setup --profile <name>` first."
        )


def garmin_setup(profile_dir: Path, *, non_interactive: bool = False) -> None:
    """Authenticate with Garmin Connect and store tokens locally via adapter."""
    _require_interactive(non_interactive, "Authentication required")
    logger.info("🔐 Garmin Connect Authentication")
    logger.info("=" * 40)
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ").strip()

    client = get_garmin_client(profile_dir)
    try:
        client.authenticate(profile_dir, email=email, password=password, non_interactive=non_interactive)
        logger.info("✅ Authenticated! Tokens saved to %s", profile_dir)
    except Exception as exc:
        raise RuntimeError(f"Authentication failed: {exc}") from exc


def upload_to_garmin(
    fit_bytes: bytes,
    profile_dir: Path,
    *,
    non_interactive: bool = False,
) -> None:
    """Upload a FIT payload to Garmin Connect."""
    client = get_garmin_client(profile_dir)
    reauthed = False
    max_attempts = 3
    rate_limit_delays = (5, 15)
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Uploading FIT ({len(fit_bytes)} bytes) to Garmin Connect...")
            client.upload(fit_bytes, profile_dir, non_interactive=non_interactive)
            logger.info("✅ Uploaded to Garmin Connect!")
            return
        except Exception as exc:
            message = str(exc)
            if "409" in message or "conflict" in message.lower():
                logger.warning("Activity already exists (duplicate timestamp).")
                return
            if _is_auth_error(message) and not reauthed:
                logger.warning("Upload auth expired; re-authenticating...")
                garmin_setup(profile_dir, non_interactive=non_interactive)
                reauthed = True
                continue
            if _is_rate_limited(message) and attempt < max_attempts:
                delay = rate_limit_delays[min(attempt - 1, len(rate_limit_delays) - 1)]
                logger.debug(f"Garmin rate-limited, retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise RuntimeError(f"Upload failed: {exc}") from exc


def fetch_latest_weight_kg(profile_dir: Path) -> float | None:
    """Fetch the most recent body weight using the configured adapter."""
    client = get_garmin_client(profile_dir)
    try:
        return client.fetch_latest_weight(profile_dir)
    except Exception as exc:
        logger.debug(f"Garmin weight fetch failed: {exc}")
        return None
