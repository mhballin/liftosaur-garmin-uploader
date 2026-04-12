"""Garmin client adapter layer.

Provides a small adapter interface for multiple Garmin client implementations
(currently: Garth and a placeholder GarminConnect adapter).

The adapters encapsulate authentication, session resume, upload, and weight
fetching so calling code can be library-agnostic.
"""
from __future__ import annotations

import json
import logging
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from .config import load_config
from .secrets_store import (
    get_garminconnect_credentials,
    migrate_legacy_garminconnect_file,
    set_garminconnect_credentials,
)

logger = logging.getLogger(__name__)


class BaseGarminClient:
    name = "base"

    def authenticate(self, profile_dir: Path, email: Optional[str], password: Optional[str], non_interactive: bool = False) -> None:
        raise NotImplementedError()

    def resume(self, profile_dir: Path) -> bool:
        raise NotImplementedError()

    def upload(self, fit_bytes: bytes, profile_dir: Path, *, non_interactive: bool = False) -> None:
        raise NotImplementedError()

    def fetch_latest_weight(self, profile_dir: Path) -> Optional[float]:
        raise NotImplementedError()


def _normalize_weight_kg(value: float, unit: str | None = None) -> float | None:
    if unit:
        unit_lower = unit.lower()
        if unit_lower in {"lb", "lbs", "pound", "pounds"}:
            # Lazily import to avoid cycles
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


class GarthAdapter(BaseGarminClient):
    """Adapter that wraps the legacy `garth` library."""

    name = "garth"

    def _garth_dir(self, profile_dir: Path) -> Path:
        return profile_dir / "garth"

    def authenticate(self, profile_dir: Path, email: Optional[str], password: Optional[str], non_interactive: bool = False) -> None:
        try:
            import garth
        except Exception as exc:  # ImportError or similar
            raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

        if not email or not password:
            raise RuntimeError("Email and password are required for garth authentication")

        try:
            garth.login(email, password)
            garth_dir = self._garth_dir(profile_dir)
            garth_dir.mkdir(parents=True, exist_ok=True)
            garth.save(str(garth_dir))
        except Exception as exc:
            raise RuntimeError(f"Authentication failed: {exc}") from exc

    def resume(self, profile_dir: Path) -> bool:
        garth_dir = self._garth_dir(profile_dir)
        if not garth_dir.exists():
            return False
        try:
            import garth

            garth.resume(str(garth_dir))
            return True
        except Exception as exc:
            logger.debug("garth resume failed: %s", exc)
            return False

    def upload(self, fit_bytes: bytes, profile_dir: Path, *, non_interactive: bool = False) -> None:
        try:
            import garth
        except Exception as exc:
            raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

        garth_dir = self._garth_dir(profile_dir)
        if not garth_dir.exists():
            raise RuntimeError("No saved credentials. Run with --setup first.")

        try:
            garth.resume(str(garth_dir))
        except Exception as exc:
            raise RuntimeError(f"Authentication failed: {exc}") from exc

        tmp_path = Path(tempfile.mkstemp(suffix=".fit")[1])
        try:
            tmp_path.write_bytes(fit_bytes)
            with tmp_path.open("rb") as handle:
                garth.client.upload(handle)
        finally:
            tmp_path.unlink(missing_ok=True)

    def fetch_latest_weight(self, profile_dir: Path) -> Optional[float]:
        try:
            import garth
        except Exception as exc:
            raise RuntimeError("'garth' is not installed. Run: pip install garth") from exc

        garth_dir = self._garth_dir(profile_dir)
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


class GarminConnectAdapter(BaseGarminClient):
    """Adapter for the `garminconnect` (python-garminconnect) library.

    This implementation is intentionally lightweight: it will attempt to use
    the third-party library if available and persist a minimal credential
    file under `profile_dir/garminconnect/credentials.json` so uploads can be
    performed non-interactively later. Storing plaintext credentials is a
    security tradeoff; the adapter uses restrictive file permissions when
    possible.
    """

    name = "garminconnect"

    def _load_client(self, profile_dir: Path):
        try:
            from garminconnect import Garmin
        except Exception as exc:
            raise RuntimeError("'garminconnect' is not installed. Run: pip install garminconnect") from exc

        # One-time migration path from legacy plaintext credentials file.
        migrate_legacy_garminconnect_file(profile_dir)

        email, password = get_garminconnect_credentials(profile_dir)
        if not email or not password:
            raise RuntimeError("No saved credentials for garminconnect. Run with --setup first.")

        client = Garmin(email, password)
        try:
            client.login()
        except Exception as exc:
            raise RuntimeError(f"Authentication failed: {exc}") from exc
        return client

    def authenticate(self, profile_dir: Path, email: Optional[str], password: Optional[str], non_interactive: bool = False) -> None:
        try:
            from garminconnect import Garmin
        except Exception as exc:
            raise RuntimeError("'garminconnect' is not installed. Run: pip install garminconnect") from exc

        if not email or not password:
            raise RuntimeError("Email and password are required for garminconnect authentication")

        client = Garmin(email, password)
        try:
            client.login()
        except Exception as exc:
            raise RuntimeError(f"Authentication failed: {exc}") from exc

        set_garminconnect_credentials(profile_dir, email, password)

    def resume(self, profile_dir: Path) -> bool:
        migrate_legacy_garminconnect_file(profile_dir)
        email, password = get_garminconnect_credentials(profile_dir)
        return bool(email and password)

    def upload(self, fit_bytes: bytes, profile_dir: Path, *, non_interactive: bool = False) -> None:
        client = self._load_client(profile_dir)

        tmp_path = Path(tempfile.mkstemp(suffix=".fit")[1])
        try:
            tmp_path.write_bytes(fit_bytes)

            # Attempt common method names used by community clients.
            # The python-garminconnect API may vary between versions; try a
            # best-effort approach and raise a clear error if upload fails.
            for method in ("upload_activity", "upload", "upload_file", "upload_activity_file"):
                fn = getattr(client, method, None)
                if not fn:
                    continue
                try:
                    # Try passing file path first
                    fn(str(tmp_path))
                    return
                except TypeError:
                    # Try passing an open file handle
                    with tmp_path.open("rb") as fh:
                        fn(fh)
                        return
                except Exception as exc:
                    # Keep trying other methods
                    logger.debug("Attempt to call %s() failed: %s", method, exc)

            # If we reach here, no adapter method succeeded
            raise RuntimeError("Upload method not implemented for installed garminconnect library; adapter needs updating")
        finally:
            tmp_path.unlink(missing_ok=True)

    def fetch_latest_weight(self, profile_dir: Path) -> Optional[float]:
        try:
            client = self._load_client(profile_dir)
        except Exception as exc:
            logger.debug("garminconnect unavailable for weight fetch: %s", exc)
            return None

        # Community clients may expose a method to fetch weight samples; try
        # common names and fall back to None.
        for method in ("get_weight", "get_weight_data", "get_user_weight", "get_weights"):
            fn = getattr(client, method, None)
            if not fn:
                continue
            try:
                payload = fn()
            except Exception as exc:
                logger.debug("Weight fetch via %s() failed: %s", method, exc)
                continue

            samples = _extract_weight_samples(payload)
            if not samples:
                continue
            latest = max(samples, key=_sample_timestamp)
            value = latest.get("weight") or latest.get("value") or latest.get("weightKg")
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            unit = latest.get("unit") or latest.get("weightUnit")
            return _normalize_weight_kg(numeric, unit)

        return None


def get_garmin_client(profile_dir: Path, preference: Optional[str] = None) -> BaseGarminClient:
    """Return an appropriate Garmin client adapter.

    preference can be None (auto), 'garth', or 'garminconnect'. Auto will prefer
    an existing `garth` session if present and resumable, otherwise fall back
    to `GarminConnectAdapter`.
    """
    config_pref = load_config(profile_dir).get("garmin_client")
    pref = (preference or config_pref or "auto").lower()
    if pref == "garth":
        return GarthAdapter()
    if pref == "garminconnect":
        return GarminConnectAdapter()

    # Auto-detect policy:
    # 1) Existing profiles with a legacy garth token dir keep using garth.
    # 2) New profiles (no garth dir) default to garminconnect.
    garth_dir = profile_dir / "garth"
    if garth_dir.exists():
        return GarthAdapter()

    # New profile path
    return GarminConnectAdapter()
