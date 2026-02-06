\# Copilot Instructions — liftosaur-garmin-uploader

## Project Overview

This is a Python CLI tool that converts **Liftosaur** workout CSV exports into Garmin-compatible **.FIT files** and uploads them to **Garmin Connect**. Activities are spoofed as coming from a **Garmin Fenix 7** so Garmin Connect treats them as native device data (Training Effect, badges, challenges, etc.).

## Architecture

```
liftosaur-garmin-uploader/
├── README.md
├── requirements.txt
├── setup.py
├── liftosaur-garmin-uploader.code-workspace
├── tree.txt
│
├── liftosaur_garmin/
│   ├── __init__.py
│   ├── __main__.py              # Entry point (python -m liftosaur_garmin)
│   ├── cli.py                   # argparse CLI interface
│   ├── csv_parser.py            # Validates & groups Liftosaur CSV by workout date
│   ├── workout_builder.py       # Orchestrates FIT file creation from parsed sets
│   ├── uploader.py              # Garmin Connect auth & upload via garth
│   ├── history.py               # JSON-based upload history tracking (~/.liftosaur_garmin/)
│   │
│   ├── fit/
│   │   ├── __init__.py
│   │   ├── constants.py         # FIT protocol constants, device IDs, sport types
│   │   ├── encoder.py           # Custom binary FIT encoder (hand-rolled, NOT fit-tool)
│   │   └── utils.py             # Timestamp helpers (ISO parse, FIT epoch conversion)
│   │
│   └── exercise/
│       ├── __init__.py
│       ├── mapping.py           # Exercise name → Garmin (category_id, exercise_name_id)
│       └── duration.py          # Per-rep duration estimates, lb→kg conversion
│
└── tests/
    ├── test_csv_parser.py
    ├── test_encoder.py
    └── fixtures/
        ├── csv/
        │   ├── sample.csv                          # Committed — sanitized test data
        │   └── liftosaur_2026-02-05.csv            # Gitignored — real data for local testing
        └── fit/
            └── strength_workout_garmin_reference.fit  # Real Garmin FIT for comparison

Note: __pycache__/ directories are gitignored and not shown above.
```

## Key Technical Details

### FIT File Encoding
- We use a **custom binary FIT encoder** — do NOT introduce `fit-tool`, `fitparse`, or similar libraries for *writing* FIT files. The encoder is hand-rolled because third-party libs don't support strength training set messages properly.
- FIT files use a **little-endian binary format** with CRC-16 checksums.
- The FIT epoch is **1989-12-31T00:00:00Z** — all timestamps in FIT are seconds since this date.
- Activities must include these message types in order: file_id, file_creator, device_info, event (start), sport, workout, workout_step, exercise_title, set (active + rest interleaved), split, split_summary, lap, session, event (stop), activity.

### Garmin Device Spoofing
- Manufacturer: Garmin (ID: 1)
- Product: Fenix 7 (ID: 3906)
- Sport: Training (10), Sub-sport: Strength Training (20)
- Device serial is a placeholder — Garmin Connect doesn't validate it.

### Garmin Connect Integration
- Auth and upload use the **`garth`** library (OAuth via Garmin SSO).
- Auth tokens are saved to `~/.garth/` for reuse.
- Upload endpoint accepts raw `.fit` bytes.

### CSV Format (Liftosaur Export)
Required columns: `Workout DateTime`, `Exercise`, `Is Warmup Set?`, `Completed Reps`, `Completed Weight Value`, `Completed Weight Unit`, `Completed Reps Time`, `Day Name`
- Workouts are grouped by `Workout DateTime`
- Warmup sets (`Is Warmup Set? == '1'`) are currently skipped in FIT output
- Timestamps per set (`Completed Reps Time`) drive real timing and rest period calculation
- Weights are in lbs in the CSV; converted to kg for FIT (protocol requirement)

### Exercise Mapping
- `exercise/mapping.py` maps lowercase exercise names → `(category_id, exercise_name_id)` tuples per the Garmin FIT SDK
- Fuzzy matching: if exact key not found, checks substring containment
- Unknown exercises fall back to `(65534, 0)`
- When adding new exercises, look up the correct category_id from the FIT SDK Profile

### Upload History
- Stored as JSON in `~/.liftosaur_garmin/history.json`
- Keyed by workout datetime string
- Prevents duplicate uploads unless `--force` is used

## Coding Conventions

- **Python 3.10+** — use modern type hints (`str | None`, `tuple[int, int]`)
- **No unnecessary dependencies** — stdlib is preferred. Current deps are only `garth` (for Garmin auth) and stdlib.
- Functions should have **docstrings** explaining what they do
- Use `pathlib.Path` over `os.path`
- Binary/struct operations use `struct.pack` with explicit format strings and little-endian (`<`) byte order
- CLI uses `argparse` — keep flags consistent with existing ones: `--setup`, `--list`, `--dry-run`, `--no-upload`, `--force`, `--date`, `--all`, `--output`
- Errors should be human-readable with emoji indicators (🏋️, 💾, ☁️, 🎉, ❌) in CLI output

## Current Focus

Get the core pipeline working reliably: CSV → FIT → Garmin upload. Don't over-engineer I/O abstractions yet — the input source (local file vs iCloud vs HTTP POST) and output destination (local file vs Garmin API) will change later.

## Future Features (Planned, not yet — don't build these)

- **Heart rate merging**: Pull HR data from Garmin Connect for the workout time window and embed it in the FIT file alongside set data. The user wears a Fenix 7 passively during lifting.
- **iOS Shortcut + server automation**: Expose an HTTP endpoint so an iOS Shortcut can POST the CSV after Liftosaur export, triggering automatic conversion and upload (likely via Tailscale to a home server / iCloud → server file watcher).


## Testing

### Strategy
The goal is to get the core pipeline working end-to-end first (CSV → FIT → Garmin upload), then abstract I/O later (eventually CSV comes from iCloud, FIT uploads automatically).

### Test Data
- `tests/fixtures/csv/sample.csv` — **committed**, sanitized fake data with same structure as real Liftosaur exports. Contains 2 workout days (Day 1 & Day 2) covering all edge cases: warmup sets, AMRAP final sets, bodyweight exercises (0 lb), completed vs required weight mismatches, superset-style overlapping timestamps, comma-containing exercise names.
- `tests/fixtures/csv/liftosaur_2026-02-05.csv` — **gitignored**, real user data for manual/local testing only
- `tests/fixtures/fit/strength_workout_garmin_reference.fit` — **committed**, a real Garmin-recorded strength training FIT file for byte-level comparison against encoder output
- `tests/fixtures/README.md` — documents what each fixture is and how to use it

### Test Layers (in priority order)
1. **CSV parser** — correct grouping by `Workout DateTime`, warmup detection, column validation, handling of quoted comma-containing exercise names like `"Romanian Deadlift, Barbell"`
2. **Exercise mapping** — all exercises in sample.csv resolve to correct Garmin category IDs, fuzzy match works, unknown exercises fall back to (65534, 0)
3. **FIT encoder** — valid 14-byte header, CRC-16 correctness, correct message ordering, parseable by `fitparse` (dev dependency only)
4. **End-to-end** — sample.csv in → FIT bytes out → validate with `fitparse` that it contains expected number of set messages, correct sport type, sane timestamps

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with real data (local only)
LIFTOSAUR_CSV=tests/fixtures/csv/liftosaur_2026-02-05.csv pytest tests/

# Generate a FIT file for manual inspection
python -m liftosaur_garmin tests/fixtures/csv/sample.csv --no-upload --output test_output.fit
```

## Common Pitfalls

- FIT message field order matters — fields must be written in the order defined by the message definition record
- CRC is calculated over the full file including the 14-byte header
- Garmin Connect silently rejects malformed FIT files with no error message — always validate with `fitparse` or Garmin's FIT SDK validator during development
- `garth` tokens expire — the uploader should handle re-auth gracefully
- Liftosaur CSV encoding can vary — always open with `utf-8-sig` to handle BOM