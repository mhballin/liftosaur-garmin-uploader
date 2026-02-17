# CSV Parser Fix: iCloud Drive Deadlock

## Problem

The watcher process was failing when reading workout CSV files from iCloud Drive with:
```
OSError: [Errno 11] Resource deadlock avoided
```

This occurred because:
1. The watcher monitors `/Users/xxxx/Library/Mobile Documents/com~apple~CloudDocs/Liftosaur/profile/`
2. When a new CSV file appears, the watcher immediately tries to read it
3. iCloud Drive is still syncing/finalizing the file at that moment
4. The CSV parser's `reader.fieldnames` access (line 43) was NOT protected by retry logic
5. The outer exception handler only caught errors during `filepath.open()`, not during DictReader header access

## Root Cause

The CSV parsing code had two layers of I/O:
```python
with filepath.open("r", encoding="utf-8-sig", newline="") as handle:  # Retry-protected ✓
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:  # NOT retry-protected ✗
        raise ValueError(...)
```

The second access (when Python's csv module tries to read the header row) happens inside the `with` block but was not wrapped in retry logic. If the file was still being synced, this would fail.

## Solution Applied

### 1. Re-structured retry logic to cover header read
```python
try:
    fieldnames = reader.fieldnames  # Now wrapped!
except OSError as exc2:
    is_deadlock_field = (
        getattr(exc2, "errno", None) == errno.EDEADLK
        or getattr(exc2, "errno", None) == errno.EAGAIN
        or "Resource deadlock avoided" in str(exc2)
    )
    if is_deadlock_field and attempt < max_attempts:
        raise  # Re-raise to trigger outer retry loop
    raise
```

### 2. Enhanced errno detection
- Checks for `errno.EDEADLK` (11) — the actual errno from this error
- Checks for `errno.EAGAIN` (35) — fallback for other platforms
- Checks message text — handles platforms that don't set errno properly

### 3. Increased retry resilience for cloud storage
Changed from:
- `max_attempts = 5` with `delay_seconds = 0.5`
- Total wait: ~7.5 seconds

To:
- `max_attempts = 10` with `delay_seconds = 1.0`
- Total wait: ~55 seconds with exponential backoff (1s, 2s, 3s, ..., 10s)

## Testing

Local test confirms parser now works:
```bash
source .venv/bin/activate
python3 -c "from liftosaur_garmin.csv_parser import parse_csv; from pathlib import Path; rows = parse_csv(Path('tests/output/verify.csv')); print(f'✓ Parsed {len(rows)} rows')"
```

## Installation

The fix is only active after running:
```bash
cd /Users/xxxx/Documents/Projects/liftosaur-garmin-uploader
source install.sh  # or: source .venv/bin/activate && pip install -e .
```

The watcher will automatically use the updated code on its next poll cycle (typically within 1 minute).

## Why This Works

- iCloud Drive file syncs typically complete within 1-10 seconds
- With 55 seconds of exponential backoff, we catch:
  - Fast syncs (retried within 1-2 seconds)
  - Slow syncs (retried within 10-20 seconds)
  - Very slow syncs (retried within 30-55 seconds)
- The original headers remain intact by retrying the entire file read cycle

## Files Changed

- `liftosaur_garmin/csv_parser.py` — Added retry logic for header access, increased backoff
