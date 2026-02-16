# Liftosaur Garmin Uploader

Tools to convert Liftosaur CSV workouts to Garmin FIT and upload.

## Quick start

macOS/Linux:

Run with 'source' to auto-activate the venv when done:

	source install.sh
Or run normally (you'll need to activate manually after):

	bash install.sh

Windows:

	install.bat

The installer creates a local virtual environment, installs dependencies, and
offers to run the setup wizard.

After install, run:

	liftosaur-garmin --help

Or without activating the venv:

	.venv/bin/liftosaur-garmin --help

## Setup

Run the setup wizard any time:

	liftosaur-garmin --setup

The wizard configures Garmin auth, calories, and optional file watching.

## Profiles

Profiles live under ~/.liftosaur_garmin/profiles/<name>. Each profile stores its
own config, history, and Garmin tokens.

Manage profiles via the interactive menu:

	liftosaur-garmin --profiles

The menu lets you add, rename, delete, and switch the default profile. It also
includes a file watcher manager.

## File watcher

If enabled during setup, a watcher monitors a Liftosaur CSV folder and uploads
new files automatically.

- macOS uses launchd
- Linux uses systemd user services (requires inotify-tools)
- Windows is not supported yet

## Dev

pip install -r requirements.txt

## FIT File Validation

Validation checks whether Garmin Connect will accept a FIT file.

1. Download the FIT SDK from https://developer.garmin.com/fit/download/
2. Extract it and copy FitCSVTool.jar into tools/
3. Validate a file:
	python -m liftosaur_garmin validate <file.fit>
4. Compare two files:
	python scripts/compare_fits.py <file1.fit> <file2.fit>

Notes:
- Tests that rely on validation are skipped if FitCSVTool.jar is not present.
- If validation fails, use the comparison tool to see differences.

## Calorie Estimation

Optional calorie estimation uses a simple duration x bodyweight formula from
StrengthLog: $calories = minutes * weight_kg * 0.0713$. This is not
heart-rate-based and is meant to avoid zero-calorie sessions in Garmin Connect.

Weight source priority:
1. Garmin Connect most recent weigh-in (via garth)
2. Fallback weight saved during `--setup`
3. Disabled or missing weight -> calories set to 0

## Testing

- Put sample CSV files in tests/fixtures/csv/
- Run a manual test:
	python -m liftosaur_garmin tests/fixtures/csv/your_file.csv --no-upload
- Generated FIT outputs should go in tests/output/ (git-ignored)

