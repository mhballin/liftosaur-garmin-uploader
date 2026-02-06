"""Upload tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def record_upload(history_path: Path, metadata: dict[str, Any]) -> None:
    """Persist upload metadata for later reference."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(str(metadata) + "\n")
