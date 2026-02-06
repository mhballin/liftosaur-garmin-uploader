"""Garmin Connect upload logic."""

from __future__ import annotations


class GarminUploader:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def upload_fit(self, fit_payload: bytes) -> str:
        """Upload a FIT payload. Returns an activity ID."""
        raise NotImplementedError("Upload not implemented yet")
