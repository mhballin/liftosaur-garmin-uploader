"""CLI entry point."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liftosaur-garmin",
        description="Convert Liftosaur CSV workouts to Garmin FIT",
    )
    parser.add_argument("csv", help="Path to Liftosaur CSV export")
    parser.add_argument("--out", help="Output FIT path")
    parser.add_argument("--dry-run", action="store_true", help="Skip upload")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.dry_run:
        print(f"Dry run for CSV: {args.csv}")
        return 0
    print(f"CSV path: {args.csv}")
    if args.out:
        print(f"FIT output: {args.out}")
    return 0
