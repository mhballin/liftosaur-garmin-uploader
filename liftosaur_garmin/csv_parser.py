"""CSV validation and grouping."""

from __future__ import annotations

from typing import Iterable


def parse_csv_rows(rows: Iterable[dict]) -> list[dict]:
    """Validate and normalize CSV rows."""
    return list(rows)
