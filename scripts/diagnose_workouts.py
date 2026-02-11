"""Diagnostic: filter CSV for specific workout datetimes and print selected columns.

Usage:
    python scripts/diagnose_workouts.py path/to.csv dt1 dt2 dt3

Example datetimes (from failing runs):
    2026-01-27T23:10:41.184Z 2024-12-03T20:56:28.612Z 2024-10-30T15:16:21.075Z
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: python scripts/diagnose_workouts.py <csv_path> <workout_datetime> [<workout_datetime> ...]")
    sys.exit(1)

csv_path = Path(sys.argv[1])
targets = set(sys.argv[2:])

if not csv_path.exists():
    print(f"CSV not found: {csv_path}")
    sys.exit(2)

with csv_path.open(encoding="utf-8-sig", newline="") as fh:
    reader = csv.DictReader(fh)
    rows = [r for r in reader if r.get("Workout DateTime") in targets]

if not rows:
    print("No matching rows found for targets:")
    for t in targets:
        print("  ", t)
    sys.exit(0)

# Print header and focused columns
cols = ["Workout DateTime", "Completed Reps Time", "Exercise", "Completed Reps", "Completed Weight Value", "Completed Weight Unit"]
print(",".join(cols))
for r in rows:
    print(",".join((r.get(c, "") for c in cols)))

# For easier inspection, also print rows grouped by workout
from collections import defaultdict
groups = defaultdict(list)
for r in rows:
    groups[r["Workout DateTime"]].append(r)

for dt, group in groups.items():
    print(f"\n=== Workout: {dt} ({len(group)} rows) ===")
    for i, r in enumerate(group):
        print(f"{i:03d}: Completed Reps Time={r.get('Completed Reps Time')!r}, Exercise={r.get('Exercise')!r}, Reps={r.get('Completed Reps')!r}, Weight={r.get('Completed Weight Value')!r} {r.get('Completed Weight Unit')!r}")
