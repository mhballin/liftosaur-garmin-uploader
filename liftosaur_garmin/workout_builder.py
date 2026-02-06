"""Build FIT from workout data."""

from __future__ import annotations

from .fit.encoder import FitEncoder, FitRecord


def build_fit(records: list[FitRecord]) -> bytes:
    """Build a FIT payload from parsed workout records."""
    encoder = FitEncoder()
    return encoder.encode_workout(records)
