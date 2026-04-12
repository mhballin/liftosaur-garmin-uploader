"""Secure secret storage helpers.

Uses the OS keychain via the `keyring` package when available. On profiles
that still contain legacy plaintext secrets, values are migrated into keychain
on first read.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "liftosaur-garmin-uploader"


def _account(profile_dir: Path, key: str) -> str:
    return f"{profile_dir.name}:{key}"


def _require_keyring():
    try:
        import keyring
    except Exception as exc:
        raise RuntimeError(
            "Secure secret storage requires the 'keyring' package. "
            "Run: pip install keyring"
        ) from exc
    return keyring


def set_secret(profile_dir: Path, key: str, value: str | None) -> None:
    """Store a secret value in OS keychain; delete entry when value is None."""
    keyring = _require_keyring()
    account = _account(profile_dir, key)
    if value is None:
        try:
            keyring.delete_password(SERVICE_NAME, account)
        except Exception:
            # Missing secret is fine.
            pass
        return

    keyring.set_password(SERVICE_NAME, account, value)


def get_secret(profile_dir: Path, key: str) -> str | None:
    """Read a secret from OS keychain, returning None when missing."""
    keyring = _require_keyring()
    account = _account(profile_dir, key)
    try:
        value = keyring.get_password(SERVICE_NAME, account)
    except Exception as exc:
        logger.debug("Failed reading secret '%s': %s", key, exc)
        return None
    return value or None


def set_liftosaur_api_key(profile_dir: Path, api_key: str | None) -> None:
    set_secret(profile_dir, "liftosaur_api_key", api_key)


def get_liftosaur_api_key(profile_dir: Path) -> str | None:
    return get_secret(profile_dir, "liftosaur_api_key")


def set_garminconnect_credentials(profile_dir: Path, email: str | None, password: str | None) -> None:
    if not email or not password:
        set_secret(profile_dir, "garminconnect_email", None)
        set_secret(profile_dir, "garminconnect_password", None)
        return
    set_secret(profile_dir, "garminconnect_email", email)
    set_secret(profile_dir, "garminconnect_password", password)


def get_garminconnect_credentials(profile_dir: Path) -> tuple[str | None, str | None]:
    email = get_secret(profile_dir, "garminconnect_email")
    password = get_secret(profile_dir, "garminconnect_password")
    return email, password


def migrate_legacy_garminconnect_file(profile_dir: Path) -> bool:
    """Migrate plaintext garminconnect credentials.json to keychain.

    Returns True when migration happened.
    """
    cred_path = profile_dir / "garminconnect" / "credentials.json"
    if not cred_path.exists():
        return False

    existing_email, existing_password = get_garminconnect_credentials(profile_dir)
    if existing_email and existing_password:
        return False

    try:
        data = json.loads(cred_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("Failed parsing legacy garminconnect creds: %s", exc)
        return False

    email = data.get("email") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not email or not password:
        return False

    set_garminconnect_credentials(profile_dir, email, password)
    try:
        cred_path.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Failed deleting legacy garminconnect creds file: %s", exc)
    return True
