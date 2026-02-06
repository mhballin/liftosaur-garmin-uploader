"""Debug tool for inspecting FIT files with garmin_fit_sdk."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from garmin_fit_sdk import Decoder, Stream


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Inspect a FIT file with garmin_fit_sdk.")
    parser.add_argument("path", type=Path, help="Path to the FIT file")
    return parser.parse_args()


def _sample_messages(messages: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    """Return a small sample of message dicts for display."""
    return messages[:limit]


def main() -> None:
    """Decode a FIT file, summarize messages, and show samples."""
    args = parse_args()
    fit_path = args.path

    if not fit_path.exists():
        raise SystemExit(f"❌ FIT file not found: {fit_path}")

    data = fit_path.read_bytes()
    stream = Stream.from_byte_array(data)
    decoder = Decoder(stream)

    messages, errors = decoder.read()

    if errors:
        print("❌ Errors found while decoding:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("🎉 No decoding errors reported.")

    message_counts: Counter[str] = Counter()
    for message_type, message_list in messages.items():
        message_counts[message_type] += len(message_list)

    print("\nMessage counts:")
    for message_type, count in sorted(message_counts.items()):
        print(f"- {message_type}: {count}")

    print("\nSample messages:")
    for message_type in sorted(messages.keys()):
        sample = _sample_messages(messages[message_type])
        print(f"\n[{message_type}] ({len(sample)} sample(s))")
        for message in sample:
            print(message)


if __name__ == "__main__":
    main()
