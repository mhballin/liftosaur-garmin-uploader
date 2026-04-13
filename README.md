# 🏋️ Liftosaur → Garmin Uploader

Bridge the gap between [Liftosaur](https://www.liftosaur.com/) and [Garmin Connect](https://connect.garmin.com/). This tool converts your Liftosaur strength training CSV exports or Liftosaur API history into Garmin-compatible FIT files and uploads them to Garmin Connect.

Uploaded workouts appear as native Garmin activities with full support for Training Effect, Training Status, badges, and workout history.

I made this because I wanted my Liftosaur workouts to show up in Garmin Connect without re-entering them by hand or relying on third-party sync services. If you run into an issue, please open an issue.

## Quick Start

If you only remember a few commands, make it these:

```bash
# First-time setup
liftosaur-garmin --setup

# Manage profiles and watchers
liftosaur-garmin --manage-profiles

# Upload all new workouts from a CSV (if not automatic via watcher)
liftosaur-garmin workout.csv --all

# Upload all new workouts from the Liftosaur API
liftosaur-garmin --api --all

# Build a FIT file locally without uploading
liftosaur-garmin workout.csv --no-upload --output my_workout.fit
```

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

Once installed, the tool runs in the background. Export a CSV from Liftosaur or enable API polling, and within minutes the workout is parsed, converted to a FIT file, and uploaded to Garmin Connect.

During setup, users can choose whether first sync should backfill historical workouts for both API and CSV sources.

Data like upload history and profile preferences is stored locally in `~/.liftosaur_garmin/`.
Sensitive values are stored via OS keychain backends (through `keyring`) instead of plaintext config files.

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

The background watcher depends on the installed `liftosaur-garmin` CLI inside that virtual environment. If you skip `install.sh` and set the project up manually from a clone, run `pip install -e .` before enabling a watcher for any profile.

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

### Optional: FIT Validation

Normal use does not require Garmin's `FitCSVTool.jar`.

- If `FitCSVTool.jar` is present in `tools/`, the app validates generated FIT files before upload.
- If `FitCSVTool.jar` is missing, the app still generates and uploads workouts, but validation is skipped.
- The standalone `liftosaur-garmin validate ...` command requires `FitCSVTool.jar`.

If you want local validation, download Garmin's FIT SDK and copy `FitCSVTool.jar` into `tools/`.

---

## Automatic Uploading

The background file watcher monitors a folder for new Liftosaur CSV exports. When a new file appears, it is automatically processed and uploaded.

On macOS the watcher runs via `launchd` and checks for new files on a configurable interval. Linux support via `systemd` is also available.

### iOS Shortcut (Recommended Workflow)

For a seamless phone-to-Garmin experience:

1. Finish your workout in Liftosaur
2. Export your data as CSV (Me → Export History to CSV file → Press Ok)
3. Use this [iOS Shortcut](https://www.icloud.com/shortcuts/1dad4917516b4a7b833f66d62dd07cb6) to save the CSV to a folder in iCloud Drive (the shortcut will create the folder if needed)
4. The file watcher picks it up and uploads automatically
5. Optionally, add an iOS automation to run the shortcut automatically

### Managing the Watcher

Check status, view logs, or reinstall the watcher anytime:

```bash
liftosaur-garmin --manage-profiles
# or: liftosaur-garmin --profiles
# → Manage file watcher
```

If terminal commands work from inside the repo but the background watcher fails, the usual cause is that the package was never installed into the virtual environment used by the watcher. Re-run `pip install -e .`, then reinstall the watcher for that profile.

---

## Multi-User Profiles

Multiple people can use the tool on the same machine. Each profile has its own Garmin credentials, upload history, calorie settings, and file watcher:

```bash
liftosaur-garmin --manage-profiles
```

This opens an interactive menu to add, rename, switch, or delete profiles and manage each profile's watcher.

Profile names can include uppercase letters and spaces.

---

## Features

### Liftosaur API Import

If you have Liftosaur Premium, you can connect a Liftosaur API key during setup and import workout history directly without waiting for CSV exports. Manual sync and background polling both reuse the same FIT/upload pipeline as CSV imports, and duplicate workouts are skipped automatically.

API mode now uploads all new workouts by default. For first-time setup, you can choose to backfill historical API workouts or only sync new workouts going forward.

### Calorie Estimation

Optionally estimate calories burned using research-backed formulas. The tool can pull your latest body weight from Garmin Connect or use a fallback you provide during setup.

### Duplicate Prevention

Every uploaded workout is tracked so re-processing the same CSV won't create duplicates. Use `--force` to override this if needed.

### FIT Validation

If `FitCSVTool.jar` is installed locally, generated FIT files can be validated before upload. This is recommended, but optional for normal use.

To manually validate a file:

```bash
liftosaur-garmin validate path/to/file.fit
```

### Exercise Mapping Notes

Liftosaur and Garmin do not use the same exercise taxonomy, so some exercises are exact matches and some are best-fit approximations.

- Common exercises are already mapped.
- Unknown or custom exercises can still upload, but Garmin may show a more generic exercise name.
- If you want more detail on how mappings were chosen, see [docs/MAPPING_RESEARCH.md](docs/MAPPING_RESEARCH.md).

---

## Uninstall

Remove the project directory and optionally delete all user data:

```bash
rm -rf liftosaur-garmin-uploader
rm -rf ~/.liftosaur_garmin/
```

On macOS, the file watcher launchd job will also need to be removed. Use `liftosaur-garmin --manage-profiles` → Manage file watcher → Stop and remove before deleting, or manually:

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

Notes:
- In API mode, `--api` uploads all new workouts by default.
- `--api --all` remains supported for compatibility.
- CSV first-sync behavior is configurable in setup: users can backfill historical CSV workouts or baseline and upload only new CSV workouts going forward.

### Common Flags

| Flag | Description |
|------|-------------|
| `--setup` | Re-run the setup wizard (Garmin auth, calories, watcher) |
| `--manage-profiles` / `--profiles` | Open the interactive profile manager |
| `--all` | Upload all new workouts from the CSV |
| `--date YYYY-MM-DD` | Upload only the matching workout |
| `--dry-run` | Preview uploads without making changes |
| `--no-upload` | Generate FIT files locally, skip upload |
| `--force` | Ignore upload history (allows re-uploads) |
| `--api` | Use Liftosaur API history as the workout source |
| `--skip-validation` | Skip FIT SDK validation before upload |
| `--verbose` | Show detailed debug output |

Run `liftosaur-garmin --help` for the full flag list.

---

## Troubleshooting

**Garmin rejects the upload silently**
If you have `FitCSVTool.jar` installed locally, validate the FIT file with `liftosaur-garmin validate path/to/file.fit`. You can also compare against a known-good FIT file with `python scripts/compare_fits.py generated.fit reference.fit`.

**Authentication expired**
Interactive runs can attempt re-authentication automatically. Background watcher and API polling runs are non-interactive and cannot prompt for credentials. Re-run setup for the affected profile: `liftosaur-garmin --setup --profile <name>`.

**Watcher not detecting files**
Check the log: `liftosaur-garmin --manage-profiles` → Manage file watcher → View watcher log. Common causes: wrong watch folder, or missing Full Disk Access on macOS when using iCloud Drive.

**Some Liftosaur API records are skipped**
The importer now tolerates common variations (comments and some annotated set formats), but still skips structurally invalid records such as missing timestamps or empty exercise blocks.

---

## Advanced Docs

If you want more technical detail, including FIT validation notes, logging details, and mapping research, see [docs/README.md](docs/README.md).

---

## License

MIT
