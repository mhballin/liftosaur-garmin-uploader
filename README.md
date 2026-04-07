# 🏋️ Liftosaur → Garmin Uploader

Bridge the gap between [Liftosaur](https://www.liftosaur.com/) and [Garmin Connect](https://connect.garmin.com/). This tool automatically converts your Liftosaur strength training CSV exports or Liftosaur API history into Garmin-compatible FIT files and uploads them to Garmin Connect — no manual entry, no third-party sync services.

Uploaded workouts appear as native Garmin activities with full support for Training Effect, Training Status, badges, and workout history.

I made this because I wanted to see my workouts in Garmin Connect without manually re-entering them or relying on third-party sync tools. I have fully vibe coded this so it probably has bugs and edge cases I haven't thought of. If you run into any issues, please open an issue or PR!

---

## How It Works

```
📱 Liftosaur (iPhone)
 ↓  Export CSV or sync via API
 ↓  Automatically moved to iCloud Drive (via iOS Shortcut + automation) or fetched from Liftosaur REST API
☁️  iCloud Drive / watched folder or Liftosaur API
 ↓  Auto-detected by background watcher / API polling
💻 liftosaur-garmin (this tool)
 ↓  Converts to FIT + uploads automatically
⌚ Garmin Connect
```

Once installed, the tool runs in the background. Export a CSV from Liftosaur or enable API polling, and within minutes the workout is parsed, converted to a FIT file, validated, and uploaded to Garmin Connect. No commands to run, nothing to remember — it just works.

On first run, the tool will upload every workout in your Liftosaur export. After that, it tracks what's been uploaded so you won't get duplicates. If you don't want to upload everything at once, move files into the watched folder one at a time to upload at your own pace.

All data (upload history, preferences, Garmin tokens) is stored locally in `~/.liftosaur_garmin/` and organized by profile if you have multiple users.

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

On macOS, the installer pulls in PyObjC to enable coordinated iCloud Drive access.

1. Download the [latest release](https://github.com/mhballin/liftosaur-garmin-uploader/releases/latest) and unzip it
2. Open a terminal in the unzipped folder
3. Run the installer:

```bash
source install.sh
```

This is the recommended path. It creates a virtual environment, installs dependencies, launches setup, and leaves your shell in the virtual environment.

If you prefer not to source the script:

```bash
bash install.sh
source .venv/bin/activate
```

After either path, the CLI is ready:

```bash
liftosaur-garmin --help
```

<details>
<summary>Alternative: clone with git</summary>

```bash
git clone https://github.com/mhballin/liftosaur-garmin-uploader.git
cd liftosaur-garmin-uploader
source install.sh
```

</details>

### macOS: iCloud Drive Permission

If your watched folder is in iCloud Drive, macOS requires Full Disk Access for the background watcher. The setup wizard will guide you through this — it's a one-time step in System Settings → Privacy & Security → Full Disk Access, scoped to your project's Python binary only (not a system-wide change).

---

## Automatic Uploading

This is the core of the project. The background file watcher monitors a folder for new Liftosaur CSV exports. When a new file appears, it's automatically processed and uploaded.

On macOS the watcher runs via `launchd` and checks for new files on a configurable interval (default: every 5 minutes). Linux support via `systemd` is also available. Let me know if you've gotten it working on Linux or Windows!

### iOS Shortcut (Recommended Workflow)

For a seamless phone-to-Garmin experience:

1. Finish your workout in Liftosaur
2. Export your data as CSV (Me → Export History to CSV file → Press Ok)
3. Use this [iOS Shortcut](https://www.icloud.com/shortcuts/1dad4917516b4a7b833f66d62dd07cb6) to save the CSV to a folder in iCloud Drive (the shortcut will create the folder if needed)
4. The file watcher picks it up and uploads automatically
5. Optionally, add an iOS automation to run the shortcut when you leave the gym (or any trigger you prefer)

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

## Features

### Liftosaur API Import

If you have Liftosaur Premium, you can connect a Liftosaur API key during setup and import workout history directly without waiting for CSV exports. Manual sync and background polling both reuse the same FIT/upload pipeline as CSV imports, and duplicate workouts are skipped automatically.

### Calorie Estimation

Optionally estimate calories burned using research-backed formulas. The tool can pull your latest body weight from Garmin Connect or use a fallback you provide during setup.

### Duplicate Prevention

Every uploaded workout is tracked so re-processing the same CSV won't create duplicates. Use `--force` to override this if needed.

### FIT Validation

Generated FIT files are automatically validated using Garmin's FIT SDK before uploading. This catches issues before Garmin Connect silently rejects them. The SDK tool (`FitCSVTool.jar`) is included in the repo — no separate download needed.

To manually validate a file:

```bash
liftosaur-garmin validate path/to/file.fit
```

---

## Uninstall

Remove the project directory and optionally delete all user data:

```bash
rm -rf liftosaur-garmin-uploader
rm -rf ~/.liftosaur_garmin/
```

On macOS, the file watcher launchd job will also need to be removed. Use `liftosaur-garmin --profiles` → Manage file watcher → Stop and remove before deleting, or manually:

```bash
launchctl unload ~/Library/LaunchAgents/com.liftosaur.garmin-watcher.*.plist
rm ~/Library/LaunchAgents/com.liftosaur.garmin-watcher.*.plist
```

---

## Manual Usage

While the tool is designed to run automatically, you can also use it directly from the command line.

```bash
# Upload the newest unprocessed workout from a CSV
liftosaur-garmin workout.csv

# Upload the newest unprocessed workout from the Liftosaur API
liftosaur-garmin --api

# Upload all new workouts from a CSV
liftosaur-garmin workout.csv --all

# Upload all new workouts from the Liftosaur API
liftosaur-garmin --api --all

# Upload a specific date
liftosaur-garmin workout.csv --date 2026-02-15

# Preview what would be uploaded
liftosaur-garmin workout.csv --dry-run

# Generate a FIT file without uploading
liftosaur-garmin workout.csv --no-upload --output my_workout.fit

# See what's in a CSV and what's already uploaded
liftosaur-garmin workout.csv --list

# See what the Liftosaur API would import
liftosaur-garmin --api --list

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
| `--non-interactive` | Disable prompts and fail fast for automation/background runs |
| `--api` | Use Liftosaur API history as the workout source |
| `--api-key KEY` | Override the configured Liftosaur API key for one command |
| `--api-start-date DATE` | Filter Liftosaur API history by start date |
| `--api-end-date DATE` | Filter Liftosaur API history by end date |
| `--api-limit N` | Limit how many Liftosaur history records to fetch |
| `--skip-validation` | Skip FIT SDK validation before upload |
| `--timezone ZONE` | Override timezone (e.g. `America/New_York`) |
| `--verbose` | Show detailed debug output |

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
Interactive runs can attempt re-authentication automatically. Background watcher and API polling runs are non-interactive and cannot prompt for credentials. Re-run setup for the affected profile: `liftosaur-garmin --setup --profile <name>`.

**Watcher not detecting files**
Check the log: `liftosaur-garmin --profiles` → Manage file watcher → View watcher log. Common causes: wrong watch folder, or missing Full Disk Access on macOS when using iCloud Drive.

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
