"""Garmin Connect upload logic."""

from __future__ import annotations

import tempfile
from pathlib import Path

GARTH_DIR = Path.home() / ".garth"


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
        garth.resume(str(GARTH_DIR))
    else:
        raise RuntimeError("No saved credentials. Run with --setup first.")

    tmp_path = Path(tempfile.mkstemp(suffix=".fit")[1])
    try:
        tmp_path.write_bytes(fit_bytes)
        with tmp_path.open("rb") as handle:
            garth.client.upload(handle)
        print("   ✅ Uploaded to Garmin Connect!")
    except Exception as exc:
        message = str(exc)
        if "409" in message or "conflict" in message.lower():
            print("   ⚠️  Activity already exists (duplicate timestamp).")
        else:
            raise RuntimeError(f"Upload failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
