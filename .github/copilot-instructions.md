# Copilot Instructions — liftosaur-garmin-uploader

## Project Overview

This is a Python CLI tool that converts **Liftosaur** workout CSV exports into Garmin-compatible **.FIT files** and uploads them to **Garmin Connect**. Activities are spoofed as coming from a **Garmin Fenix 7** so Garmin Connect treats them as native device data (Training Effect, badges, challenges, etc.).

## Project Structure

See `tree.txt` in the project root for the current directory structure.

Key files:
- `liftosaur_garmin/__main__.py` - Entry point (`python -m liftosaur_garmin`)
- `liftosaur_garmin/cli.py` - argparse CLI interface
- `liftosaur_garmin/csv_parser.py` - Validates & groups Liftosaur CSV by workout date
- `liftosaur_garmin/workout_builder.py` - Orchestrates FIT file creation from parsed sets
- `liftosaur_garmin/uploader.py` - Garmin Connect auth & upload via garth
- `liftosaur_garmin/history.py` - JSON-based upload history tracking (~/.liftosaur_garmin/)
- `liftosaur_garmin/fit/encoder.py` - Custom binary FIT encoder (hand-rolled, NOT fit-tool)
- `liftosaur_garmin/fit/constants.py` - FIT protocol constants, device IDs, sport types
- `liftosaur_garmin/fit/utils.py` - Timestamp helpers (ISO parse, FIT epoch conversion)
- `liftosaur_garmin/exercise/mapping.py` - Exercise name → Garmin (category_id, exercise_name_id)
- `liftosaur_garmin/exercise/duration.py` - Per-rep duration estimates, lb→kg conversion
- `inspect_fit.py` - Utility for inspecting FIT file contents
- `tests/fixtures/` - Sample CSV and FIT files for testing

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
- Warmup sets (`Is Warmup Set? == '1'`) are currently skipped in FIT output (intentional design decision)
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

Get the core pipeline working reliably: CSV → FIT → Garmin upload. Don't over-engineer I/O abstractions yet — the input source (local file vs URL vs HTTP POST) and output destination (local file vs Garmin API) will change later.

## Non-Goals (Do NOT Build These)

- **Don't refactor the custom FIT encoder** to use `fit-tool`, `fitparse`, or any third-party FIT writing library. The hand-rolled encoder is intentional.
- **Don't add heart rate data merging** - this is not part of the project scope
- **Don't build automated CSV fetching yet** - eventually the CSV will be fetched from a URL instead of a local file, but we'll tackle input abstraction after the core pipeline works
- **Don't over-engineer I/O abstractions** before the core works - keep it simple
- **Don't write automated tests (pytest)** - manual CLI testing is sufficient for now

## Future Features (Planned for Later)

- **Automated CSV fetching**: Eventually the CSV will be fetched from a URL instead of requiring a local file. This will enable automation workflows. Don't build this yet - we'll cross that bridge when we get there.

## Testing

### Strategy
Test manually by running the CLI with sample data. The goal is to verify the core pipeline works end-to-end: CSV → FIT → Garmin upload.

### Test Data
- `tests/fixtures/csv/liftosaur_2026-02-05.csv` — **gitignored**, real user data for manual/local testing only
- `tests/fixtures/fit/**` — **gitignored**, real Garmin-recorded FIT files for byte-level comparison

### Manual Testing
```bash
# Test with real data (local only, file is gitignored)
# Always set an explicit output path under tests/output to avoid default naming/location.
# Use versioned names like test_v1.fit, test_v2.fit, etc.
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit

```

## Common Pitfalls

- FIT message field order matters — fields must be written in the order defined by the message definition record
- CRC is calculated over the full file including the 14-byte header
- Garmin Connect silently rejects malformed FIT files with no error message — always validate with `fitparse` or Garmin's FIT SDK validator during development
- `garth` tokens expire — the uploader should handle re-auth gracefully
- Liftosaur CSV encoding can vary — always open with `utf-8-sig` to handle BOM

## Troubleshooting

- **CSV parsing fails**: Check for missing required columns, ensure UTF-8 encoding with BOM handling
- **Garmin upload rejected**: Validate FIT file structure, check message ordering, verify CRC-16 checksum
- **Exercise not mapped**: Add to `exercise/mapping.py` with correct Garmin category_id from FIT SDK Profile
- **Auth issues**: Delete `~/.garth/` and re-run with `--setup` flag to re-authenticate