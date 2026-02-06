"""Analyze CSV exercise mapping against FIT set messages."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from liftosaur_garmin.csv_parser import read_csv
from liftosaur_garmin.exercise.duration import lbs_to_kg
from liftosaur_garmin.exercise.mapping import EXERCISE_MAP, lookup_exercise


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Compare Liftosaur CSV sets to FIT set messages."
    )
    parser.add_argument("csv_path", type=Path, help="Path to Liftosaur CSV export")
    parser.add_argument("fit_path", type=Path, help="Path to generated FIT file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/output/mapping_analysis.txt"),
        help="Output report path",
    )
    parser.add_argument(
        "--include-warmups",
        action="store_true",
        help="Include warmup sets from the CSV",
    )
    parser.add_argument(
        "--weight-tolerance-kg",
        type=float,
        default=0.05,
        help="Allowed weight delta in kg when comparing",
    )
    return parser.parse_args()


def parse_csv_sets(csv_path: Path, include_warmups: bool) -> list[dict[str, Any]]:
    """Parse CSV into a list of set summaries."""
    rows = read_csv(csv_path)
    sets: list[dict[str, Any]] = []
    for row in rows:
        if not include_warmups:
            is_warmup = (row.get("Is Warmup Set?") or "0").strip() == "1"
            if is_warmup:
                continue

        name = (row.get("Exercise") or "").strip()
        reps = int(float(row.get("Completed Reps", 0) or 0))
        weight_value = float(row.get("Completed Weight Value", 0) or 0)
        weight_unit = (row.get("Completed Weight Unit") or "lb").strip()
        weight_kg = lbs_to_kg(weight_value) if weight_unit == "lb" else weight_value
        category_id, exercise_id = lookup_exercise(name or "Unknown")

        sets.append(
            {
                "exercise": name or "Unknown",
                "reps": reps,
                "weight_kg": weight_kg,
                "expected_category": category_id,
                "expected_exercise": exercise_id,
            }
        )

    return sets


def parse_fit_sets(fit_path: Path) -> list[dict[str, Any]]:
    """Parse FIT set messages using fitparse."""
    try:
        from fitparse import FitFile
    except ImportError as exc:  # pragma: no cover - manual script
        raise SystemExit(
            "fitparse is required. Install with: pip install fitparse"
        ) from exc

    fitfile = FitFile(str(fit_path))
    sets: list[dict[str, Any]] = []
    for message in fitfile.get_messages("set"):
        fields = {field.name: field.value for field in message}
        set_type = fields.get("set_type")
        if set_type is not None:
            if isinstance(set_type, str):
                if set_type.lower() != "active":
                    continue
            elif int(set_type) != 1:
                continue

        reps = fields.get("repetitions")
        if reps is None:
            reps = fields.get("reps")

        sets.append(
            {
                "category": _to_int(fields.get("category")),
                "exercise": _to_int(fields.get("exercise_name")),
                "reps": _to_int(reps),
                "weight_kg": _to_float(fields.get("weight")),
            }
        )

    return sets


def build_reverse_map() -> dict[tuple[int, int], list[str]]:
    """Build reverse lookup of exercise ids to names."""
    reverse: dict[tuple[int, int], list[str]] = {}
    for name, ids in EXERCISE_MAP.items():
        reverse.setdefault(ids, []).append(name)
    for names in reverse.values():
        names.sort()
    return reverse


def compare_sets(
    csv_sets: list[dict[str, Any]],
    fit_sets: list[dict[str, Any]],
    tolerance_kg: float,
) -> tuple[list[dict[str, str]], list[str]]:
    """Create comparison rows and a list of mismatch notes."""
    reverse_map = build_reverse_map()
    rows: list[dict[str, str]] = []
    mismatches: list[str] = []

    max_len = max(len(csv_sets), len(fit_sets))
    for idx in range(max_len):
        csv_set = csv_sets[idx] if idx < len(csv_sets) else None
        fit_set = fit_sets[idx] if idx < len(fit_sets) else None
        mismatch_reasons: list[str] = []

        if csv_set is None:
            mismatch_reasons.append("missing csv set")
        if fit_set is None:
            mismatch_reasons.append("missing fit set")

        if csv_set and fit_set:
            if (
                csv_set["expected_category"],
                csv_set["expected_exercise"],
            ) != (fit_set["category"], fit_set["exercise"]):
                mismatch_reasons.append("category/exercise mismatch")
            if csv_set["reps"] != fit_set["reps"]:
                mismatch_reasons.append("reps mismatch")
            if fit_set["weight_kg"] is not None:
                if abs(csv_set["weight_kg"] - fit_set["weight_kg"]) > tolerance_kg:
                    mismatch_reasons.append("weight mismatch")

        garmin_display = ""
        if fit_set:
            garmin_display = ", ".join(
                reverse_map.get((fit_set["category"], fit_set["exercise"]), [])
            )

        row = {
            "idx": str(idx + 1),
            "csv_exercise": csv_set["exercise"] if csv_set else "",
            "csv_reps": _fmt_int(csv_set["reps"]) if csv_set else "",
            "csv_wt_kg": _fmt_float(csv_set["weight_kg"]) if csv_set else "",
            "csv_expected": _fmt_pair(
                csv_set["expected_category"], csv_set["expected_exercise"]
            )
            if csv_set
            else "",
            "fit_cat_ex": _fmt_pair(
                fit_set["category"], fit_set["exercise"]
            )
            if fit_set
            else "",
            "fit_reps": _fmt_int(fit_set["reps"]) if fit_set else "",
            "fit_wt_kg": _fmt_float(fit_set["weight_kg"]) if fit_set else "",
            "garmin_display": garmin_display or "unknown",
            "mismatch": "; ".join(mismatch_reasons),
        }
        rows.append(row)

        if mismatch_reasons:
            mismatches.append(
                f"Set {idx + 1}: " + "; ".join(mismatch_reasons)
            )

    return rows, mismatches


def render_table(rows: list[dict[str, str]]) -> str:
    """Render rows as a fixed-width table."""
    columns = [
        ("idx", "#"),
        ("csv_exercise", "CSV Exercise"),
        ("csv_reps", "CSV Reps"),
        ("csv_wt_kg", "CSV Wt kg"),
        ("csv_expected", "CSV Cat/Ex"),
        ("fit_cat_ex", "FIT Cat/Ex"),
        ("fit_reps", "FIT Reps"),
        ("fit_wt_kg", "FIT Wt kg"),
        ("garmin_display", "Garmin Display"),
        ("mismatch", "Mismatch"),
    ]

    widths: dict[str, int] = {}
    for key, title in columns:
        widths[key] = len(title)
    for row in rows:
        for key, _ in columns:
            widths[key] = max(widths[key], len(row.get(key, "")))

    lines: list[str] = []
    header = " | ".join(
        title.ljust(widths[key]) for key, title in columns
    )
    separator = "-+-".join("-" * widths[key] for key, _ in columns)
    lines.append(header)
    lines.append(separator)
    for row in rows:
        lines.append(
            " | ".join(row.get(key, "").ljust(widths[key]) for key, _ in columns)
        )

    return "\n".join(lines)


def write_report(
    output_path: Path,
    csv_path: Path,
    fit_path: Path,
    rows: list[dict[str, str]],
    mismatches: list[str],
) -> None:
    """Write report to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "Workout Mapping Analysis",
        f"CSV: {csv_path}",
        f"FIT: {fit_path}",
        "",
        "Garmin Display uses reverse lookup from exercise/mapping.py.",
        "",
        render_table(rows),
        "",
        f"Total sets: {len(rows)}",
        f"Mismatches: {len(mismatches)}",
    ]

    if mismatches:
        report_lines.append("")
        report_lines.append("Mismatch Details:")
        report_lines.extend(mismatches)

    output_path.write_text("\n".join(report_lines), encoding="utf-8")


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_pair(category: int | None, exercise: int | None) -> str:
    if category is None or exercise is None:
        return ""
    return f"{category}/{exercise}"


def _fmt_int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _fmt_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def main() -> None:
    """Run comparison and write output."""
    args = parse_args()

    csv_sets = parse_csv_sets(args.csv_path, args.include_warmups)
    fit_sets = parse_fit_sets(args.fit_path)
    rows, mismatches = compare_sets(
        csv_sets, fit_sets, args.weight_tolerance_kg
    )

    write_report(args.output, args.csv_path, args.fit_path, rows, mismatches)
    print(f"Wrote report to {args.output}")


if __name__ == "__main__":
    main()
