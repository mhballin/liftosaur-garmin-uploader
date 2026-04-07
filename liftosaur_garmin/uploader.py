"""Garmin Connect upload logic."""

from __future__ import annotations

import getpass
import logging
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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
    """Authenticate with Garmin Connect and store tokens locally."""
    _require_interactive(non_interactive, "Authentication required")
    garth_dir = profile_dir / "garth"
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    logger.info("🔐 Garmin Connect Authentication")
    logger.info("=" * 40)
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ").strip()

    try:
        logger.debug("Attempting login for %s...", email)
        garth.login(email, password)
        garth.save(str(garth_dir))
        logger.info("✅ Authenticated! Tokens saved to %s", garth_dir)
    except Exception as exc:
        raise RuntimeError(f"Authentication failed: {exc}") from exc


def upload_to_garmin(
    fit_bytes: bytes,
    profile_dir: Path,
    *,
    non_interactive: bool = False,
) -> None:
    """Upload a FIT payload to Garmin Connect."""
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    garth_dir = profile_dir / "garth"
    if garth_dir.exists():
        try:
            logger.debug("Resuming Garmin session from saved credentials...")
            garth.resume(str(garth_dir))
        except Exception as exc:
            message = str(exc)
            if _is_auth_error(message):
                logger.warning("Garmin token expired; re-authenticating...")
                garmin_setup(profile_dir, non_interactive=non_interactive)
                garth.resume(str(garth_dir))
            else:
                raise RuntimeError(f"Authentication failed: {exc}") from exc
    else:
        raise RuntimeError("No saved credentials. Run with --setup first.")

    tmp_path = Path(tempfile.mkstemp(suffix=".fit")[1])
    try:
        tmp_path.write_bytes(fit_bytes)
        reauthed = False
        max_attempts = 3
        rate_limit_delays = (5, 15)
        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"Uploading FIT ({len(fit_bytes)} bytes) to Garmin Connect...")
                with tmp_path.open("rb") as handle:
                    garth.client.upload(handle)
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
                    garth.resume(str(garth_dir))
                    reauthed = True
                    continue
                if _is_rate_limited(message) and attempt < max_attempts:
                    delay = rate_limit_delays[min(attempt - 1, len(rate_limit_delays) - 1)]
                    logger.debug(f"Garmin rate-limited, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Upload failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _normalize_weight_kg(value: float, unit: str | None = None) -> float | None:
    if unit:
        unit_lower = unit.lower()
        if unit_lower in {"lb", "lbs", "pound", "pounds"}:
            from .exercise.duration import lbs_to_kg

            return lbs_to_kg(value)

    if value > 500:
        return value / 1000.0
    return value


def _extract_weight_samples(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        for key in ("weightSamples", "weights", "weightSample", "entries"):
            samples = payload.get(key)
            if isinstance(samples, list):
                return samples
    if isinstance(payload, list):
        return payload
    return []


def _sample_timestamp(sample: dict) -> int:
    for key in ("date", "timestamp", "startTimeGMT", "calendarDate"):
        value = sample.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def fetch_latest_weight_kg(profile_dir: Path) -> float | None:
    """Fetch the most recent body weight from Garmin Connect via garth."""
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    garth_dir = profile_dir / "garth"
    if not garth_dir.exists():
        logger.debug("No Garmin credentials found for weight lookup")
        return None

    try:
        garth.resume(str(garth_dir))
    except Exception as exc:
        logger.debug(f"Failed to resume Garmin session for weight lookup: {exc}")
        return None

    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    params = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
    }
    path = "/modern/proxy/weight-service/weight/range"

    try:
        response = garth.client.request("GET", path, params=params)
        payload = response.json() if hasattr(response, "json") else response
    except Exception as exc:
        logger.debug(f"Garmin weight fetch failed: {exc}")
        return None

    samples = _extract_weight_samples(payload)
    if not samples:
        logger.debug("No weight samples found in Garmin response")
        return None

    latest = max(samples, key=_sample_timestamp)
    value = latest.get("weight") or latest.get("value") or latest.get("weightKg")
    if value is None:
        logger.debug("Latest Garmin weight sample missing value")
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        logger.debug("Latest Garmin weight sample value is not numeric")
        return None

    unit = latest.get("unit") or latest.get("weightUnit")
    normalized = _normalize_weight_kg(numeric, unit)
    if normalized is None:
        return None

    logger.debug(f"Garmin weight sample: {normalized:.2f} kg")
    return normalized
