# 🏋️ Liftosaur → Garmin Uploader

Bridge the gap between [Liftosaur](https://www.liftosaur.com/) and [Garmin Connect](https://connect.garmin.com/). This tool automatically converts your Liftosaur strength training CSV exports into Garmin-compatible FIT files and uploads them to Garmin Connect — no manual entry, no third-party sync services.

Uploaded workouts appear as native Garmin activities with full support for Training Effect, Training Status, badges, and workout history.

---

## How It Works

```
📱 Liftosaur (iPhone)
 ↓  Export CSV 
 ↓  Automatically move files to iCloud Drive (via iOS Shortcut + automation)
☁️  iCloud Drive / watched folder
 ↓  Auto-detected by background file watcher
💻 liftosaur-garmin (this tool)
 ↓  Converts to FIT + uploads automatically
⌚ Garmin Connect
```

Once installed, the tool runs in the background. Export a CSV from Liftosaur, and within minutes it's parsed, converted to a FIT file, validated, and uploaded to Garmin Connect. No commands to run, nothing to remember — it just works.

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | ✅ Fully tested | Primary development platform. File watcher via `launchd`. Tested with iCloud Drive for CSV delivery from iPhone. |
| **Linux** | 🟡 Should work | File watcher via `systemd` is implemented but not yet tested. Core CSV → FIT → upload functionality uses cross-platform Python and should work. Feedback welcome. |
| **Windows** | 🔴 Partial | `install.bat` and venv setup are available. Automatic file watching is not yet implemented. Manual CLI usage should work. |

The tool has been developed and tested on macOS using iCloud Drive to transfer CSVs from iPhone. Other file delivery methods (Google Drive, Dropbox, AirDrop, etc.) should work with any folder the watcher can read — these will be tested in future releases.

---

## Install

**Requirements:** Python 3.10+ and a Garmin Connect account.

1. Download the [latest release](https://github.com/mhballin/liftosaur-garmin-uploader/releases/latest) and unzip it
2. Open a terminal in the unzipped folder
3. Run:

```bash
source install.sh
```

The installer creates a virtual environment, installs all dependencies, and launches the setup wizard. The wizard walks you through connecting your Garmin account, configuring preferences, and setting up the automatic file watcher. Everything is handled in one go — when the installer finishes, the tool is fully configured and running.

If you'd rather activate the environment yourself afterward:

```bash
bash install.sh
source .venv/bin/activate
```

### macOS: iCloud Drive Permission

If your watched folder is in iCloud Drive, macOS requires Full Disk Access for the background watcher. The setup wizard will guide you through this — it's a one-time step in System Settings → Privacy & Security → Full Disk Access, scoped to your project's Python binary only (not a system-wide change).

---

## Automatic Uploading

This is the core of the project. The background file watcher monitors a folder for new Liftosaur CSV exports. When a new file appears, it's automatically processed and uploaded.

On macOS the watcher runs via `launchd` and checks for new files on a configurable interval (default: every 5 minutes). Linux support via `systemd` is also available.

Let me know if you have made it work on Linux or Windows!

### iOS Shortcut (Recommended Workflow)

For a seamless phone-to-Garmin experience:

1. Finish your workout in Liftosaur
2. Export your data as CSV (Me → Export History to CSV file → Press Ok)
3. Use this iOS Shortcut to save the CSV to your a folder in icloud dirve (this shortcut will create the folder needed)
		https://www.icloud.com/shortcuts/1dad4917516b4a7b833f66d62dd07cb6
4. The file watcher picks it up and uploads automatically
5. Add a simple automation to run the shortcut if you leave the gym (or whatever you want)

### Managing the Watcher

Check status, view logs, or reinstall the watcher anytime:

```bash
liftosaur-garmin --profiles
# → Manage file watcher
```

---

## Multi-User Profiles

Multiple people can use the tool on the same machine. Each profile has its own Garmin credentials, upload history, calorie settings, and file watcher:

```bash
liftosaur-garmin --profiles
```

This opens an interactive menu to add, rename, switch, or delete profiles and manage each profile's watcher.

---

## Manual Usage

While the tool is designed to run automatically, you can also use it directly from the command line.

```bash
# Upload the newest unprocessed workout from a CSV
liftosaur-garmin workout.csv

# Upload all new workouts from a CSV
liftosaur-garmin workout.csv --all

# Upload a specific date
liftosaur-garmin workout.csv --date 2026-02-15

# Preview what would be uploaded
liftosaur-garmin workout.csv --dry-run

# Generate a FIT file without uploading
liftosaur-garmin workout.csv --no-upload --output my_workout.fit

# See what's in a CSV and what's already uploaded
liftosaur-garmin workout.csv --list

# View upload history (no CSV needed)
liftosaur-garmin --list
```

### All Flags

| Flag | Description |
|------|-------------|
| `--setup` | Re-run the setup wizard (Garmin auth, calories, watcher) |
| `--profiles` | Interactive profile management menu |
| `--profile NAME` | Use a specific profile for this command |
| `--all` | Upload all new workouts from the CSV |
| `--date YYYY-MM-DD` | Upload only the matching workout |
| `--dry-run` | Preview uploads without making changes |
| `--no-upload` | Generate FIT files locally, skip upload |
| `--output PATH` | Save the FIT file to a specific path |
| `--force` | Ignore upload history (allows re-uploads) |
| `--list` | List workouts in CSV or upload history |
| `--skip-validation` | Skip FIT SDK validation before upload |
| `--timezone ZONE` | Override timezone (e.g. `America/New_York`) |
| `--verbose` | Show detailed debug output |

---

## Features

### Calorie Estimation

Optionally estimate calories burned using research-backed formulas. The tool can pull your latest body weight from Garmin Connect or use a fallback you provide during setup.

### Duplicate Prevention

Every uploaded workout is tracked. Re-running the tool on the same CSV won't create duplicates. Use `--force` to override this if needed.

### FIT Validation

Generated FIT files are automatically validated using Garmin's FIT SDK before uploading. This catches issues before Garmin Connect silently rejects them. The SDK tool (`FitCSVTool.jar`) is included in the repo — no separate download needed.

To manually validate a file:

```bash
liftosaur-garmin validate path/to/file.fit
```

---

## Project Structure

```
liftosaur-garmin-uploader/
├── liftosaur_garmin/          # Main package
│   ├── cli.py                 # CLI entry point and setup wizard
│   ├── csv_parser.py          # Liftosaur CSV parsing
│   ├── workout_builder.py     # FIT message construction
│   ├── fit/                   # Binary FIT encoder
│   ├── exercise/              # Exercise mapping and duration logic
│   ├── uploader.py            # Garmin Connect upload via garth
│   ├── profile.py             # Multi-user profile management
│   ├── watcher.py             # File watcher setup (launchd/systemd)
│   ├── history.py             # Upload tracking
│   ├── config.py              # Per-profile configuration
│   └── templates/             # Watcher script and service templates
├── scripts/                   # Development and validation utilities
├── tests/                     # Test fixtures and validation tests
├── tools/                     # FIT SDK tools (FitCSVTool.jar)
├── install.sh                 # macOS/Linux installer
├── install.bat                # Windows installer
└── setup.py                   # Package configuration
```

---

## Troubleshooting

**Garmin rejects the upload silently**
Validate the FIT file: `liftosaur-garmin validate path/to/file.fit`. Compare against a known-good file with `python scripts/compare_fits.py generated.fit reference.fit`.

**Authentication expired**
The tool attempts to re-authenticate automatically. If that fails, re-run the setup wizard: `liftosaur-garmin --setup`.

**Watcher not detecting files**
Check the log: `liftosaur-garmin --profiles` → Manage file watcher → View watcher log. Common causes: wrong watch folder, or missing Full Disk Access on macOS when using iCloud Drive.

**Duplicate uploads**
Upload history is stored per-profile in `~/.liftosaur_garmin/profiles/<name>/history.json`. Use `--force` to re-upload, or edit the history file directly.

---

## Technical Notes

This tool uses a custom binary FIT encoder rather than third-party FIT libraries. Garmin's strength training FIT format has specific structural requirements that generic FIT writers don't handle correctly. The encoder writes little-endian binary with CRC-16 checksums and FIT epoch timestamps (base: 1989-12-31). All weights are converted from pounds to kilograms for FIT compatibility.

FIT validation uses Garmin's official `FitCSVTool.jar` (included in `tools/`), which is part of the free [Garmin FIT SDK](https://developer.garmin.com/fit/download/).

---

## Contributing

Contributions are welcome — especially exercise name mappings, bug fixes, and platform testing. If you get this running on Linux or Windows, please open an issue or PR with your experience.

---

## License

MIT
