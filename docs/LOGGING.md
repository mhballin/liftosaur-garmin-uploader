# Logging Architecture

## Overview

This project implements **industry-standard structured logging** with automatic rotation, per-module verbosity control, and separation between user-facing console output and machine-readable file logs.

## Configuration

### Setup

Logging is configured via `liftosaur_garmin/logging_config.py`:

```python
from liftosaur_garmin.logging_config import setup_logging

setup_logging(verbose=False)  # Use True for DEBUG level console output
```

The CLI automatically calls this during startup (see `cli.py`).

### Handlers

Two handlers process logs:

#### Console Handler
- **Level**: `INFO` (or `DEBUG` if `--verbose` flag is used)
- **Format**: `%(message)s` (clean, user-facing)
- **Purpose**: Real-time feedback, emoji indicators (✅, ❌, 💾)

#### File Handler (Rotating)
- **Location**: `~/.liftosaur_garmin/logs/liftosaur_garmin.log`
- **Level**: `DEBUG`
- **Format**: ISO 8601 timestamp + structured fields
- **Rotation**: 5MB per file, 5 backups (~25MB total)
- **Purpose**: Debugging, audit trail, machine-readable

### Per-Module Log Levels

To prevent log files from growing unbounded, high-verbosity modules are restricted:

| Module | Level | Reason |
|--------|-------|--------|
| `liftosaur_garmin.exercise.mapping` | `WARNING` | 30+ debug statements per exercise lookup |
| `liftosaur_garmin.fit.encoder` | `WARNING` | Verbose binary encoding details |
| All others | `DEBUG` | Standard development logging |

**To change module levels**, edit `_MODULE_LEVELS` in `logging_config.py`.

Example:
```python
_MODULE_LEVELS: dict[str, int] = {
    "liftosaur_garmin.my_module": logging.INFO,  # Less verbose
}
```

## Watcher Logging

The file watcher (`watch_and_process.py`) uses the same structured logging approach:

- **Location**: `profile_dir/watcher.log` (e.g., `~/.liftosaur_garmin/profiles/default/watcher.log`)
- **Rotation**: 5MB per file, 3 backups (15MB max)
- **Format**: ISO 8601 timestamp + level + module name

## Log file Examples

### Console Output (user-facing)
```
🏋️  Parsing 127 sets from liftosaur_2026-02-05.csv...
💾 Generated FIT file: /tmp/activity_2026-02-05T08_30.fit (8.2 KB)
✅ Uploaded to Garmin Connect!
```

### File Log (structured, machine-readable)
```
2026-02-26T10:15:43-0500 [INFO    ] liftosaur_garmin.csv_parser - Parsing 127 sets from liftosaur_2026-02-05.csv...
2026-02-26T10:15:44-0500 [DEBUG   ] liftosaur_garmin.workout_builder - Built 1 activity with 127 sets
2026-02-26T10:15:44-0500 [INFO    ] liftosaur_garmin.fit.encoder - Generated FIT file: 8.2 KB
2026-02-26T10:15:46-0500 [INFO    ] liftosaur_garmin.uploader - ✅ Uploaded to Garmin Connect!
```

## Troubleshooting

### Log files growing too large

1. Check log directory:
   ```bash
   du -sh ~/.liftosaur_garmin/logs/
   ```

2. Rotation should prevent this, but if it's an old installation:
   ```bash
   rm ~/.liftosaur_garmin/logs/liftosaur_garmin.log*
   ```

3. To reduce verbosity further, lower module log levels in `_MODULE_LEVELS`:
   ```python
   _MODULE_LEVELS: dict[str, int] = {
       "liftosaur_garmin.csv_parser": logging.WARNING,  # More conservative
   }
   ```

### Seeing DEBUG logs on console

Use `--verbose` flag:
```bash
python -m liftosaur_garmin <file.csv> --verbose
```

### Watcher logs not appearing

1. Verify watcher was installed with `setup --watcher`
2. Check log location: `~/.liftosaur_garmin/profiles/<profile_name>/watcher.log`
3. Watcher runs every 5 minutes by default; check timestamps in log file

## Best Practices

### When adding logging to new code

1. **Use appropriate level**:
   - `DEBUG`: Development details (variable values, loop iterations)
   - `INFO`: High-level events (file processed, upload started)
   - `WARNING`: Recoverable issues (retry, fallback)
   - `ERROR`: Unrecoverable failures

2. **Avoid logging in hot loops**:
   - Don't log for every set during CSV parsing
   - Use batch logging: "Processed X sets" instead of "Processing set N"

3. **Use structured information**:
   ```python
   # Good
   logger.info(f"Processed {count} sets in {elapsed:.2f}s")

   # Avoid
   logger.debug(f"Set {i}: reps={r}, weight={w}, time={t}...")
   ```

4. **Include context in error messages**:
   ```python
   logger.error(f"Failed to parse {filepath}: {exc}", exc_info=True)
   ```

### Reviewing logs for issues

1. **Console**: Watch for ❌ (errors) or ⚠️ (warnings)
2. **File log**: Query by level:
   ```bash
   grep "\[ERROR" ~/.liftosaur_garmin/logs/liftosaur_garmin.log
   grep "\[WARNING" ~/.liftosaur_garmin/logs/liftosaur_garmin.log
   ```

## Configuration Changes (Feb 2026)

### What Changed
- **Rotating file handler**: Increased from 1MB (3 backups) to 5MB (5 backups)
- **Per-module levels**: Added control to suppress verbose modules (exercise.mapping, fit.encoder)
- **Watcher logging**: Migrated from custom append-only to Python's `RotatingFileHandler`
- **Format**: Added ISO 8601 timestamps and level padding for better readability

### Why
- Previous setup logged 30+ debug statements per exercise lookup → logs filled up quickly
- Watcher template used unlimited append, creating massive log files
- No structured format made it hard to grep/analyze logs

### Benefits
- Logs stay under ~25MB with automatic cleanup
- Reduced verbosity without losing debugging capability (`--verbose` flag)
- Consistent format across CLI and watcher logs
- Machine-readable structure for log aggregation/analysis
