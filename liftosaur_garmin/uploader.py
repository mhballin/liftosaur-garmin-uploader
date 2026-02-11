"""Garmin Connect upload logic."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

GARTH_DIR = Path.home() / ".garth"
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


def garmin_setup() -> None:
    """Authenticate with Garmin Connect and store tokens locally."""
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    print("\n🔐 Garmin Connect Authentication")
    print("=" * 40)
    email = input("Email: ").strip()
    password = input("Password: ").strip()

    try:
        garth.login(email, password)
        garth.save(str(GARTH_DIR))
        print(f"\n✅ Authenticated! Tokens saved to {GARTH_DIR}")
    except Exception as exc:
        raise RuntimeError(f"Authentication failed: {exc}") from exc


def upload_to_garmin(fit_bytes: bytes) -> None:
    """Upload a FIT payload to Garmin Connect."""
    try:
        import garth
    except ImportError as exc:
        raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

    if GARTH_DIR.exists():
        try:
            garth.resume(str(GARTH_DIR))
        except Exception as exc:
            message = str(exc)
            if _is_auth_error(message):
                print("   ⚠️  Garmin token expired; re-auth required.")
                garmin_setup()
                garth.resume(str(GARTH_DIR))
            else:
                raise RuntimeError(f"Authentication failed: {exc}") from exc
    else:
        raise RuntimeError("No saved credentials. Run with --setup first.")

    tmp_path = Path(tempfile.mkstemp(suffix=".fit")[1])
    try:
        tmp_path.write_bytes(fit_bytes)
        reauthed = False
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                with tmp_path.open("rb") as handle:
                    garth.client.upload(handle)
                print("   ✅ Uploaded to Garmin Connect!")
                return
            except Exception as exc:
                message = str(exc)
                if "409" in message or "conflict" in message.lower():
                    print("   ⚠️  Activity already exists (duplicate timestamp).")
                    return
                if _is_auth_error(message) and not reauthed:
                    print("   ⚠️  Upload auth expired; re-auth required.")
                    garmin_setup()
                    garth.resume(str(GARTH_DIR))
                    reauthed = True
                    continue
                if _is_rate_limited(message) and attempt < max_attempts:
                    delay = 2 ** (attempt - 1)
                    print(f"   ⏳ Garmin rate-limited, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Upload failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
