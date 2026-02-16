# Liftosaur → Garmin Uploader

Convert Liftosaur CSV workout exports into Garmin-compatible FIT files and
upload them to Garmin Connect. The tool spoofs a Garmin Fenix device so
activities behave like native Garmin uploads (training effect, badges, etc.).

**Quick links**
- **Install script:** [install.sh](install.sh)
- **CLI entry:** `python -m liftosaur_garmin` (console script: `liftosaur-garmin`)
- **Config & profiles:** `~/.liftosaur_garmin/profiles`

**Highlights**
- Converts Strength / Lifting CSVs to FIT with set timing and weights.
- Uploads to Garmin Connect using `garth` OAuth tokens.
- Per-profile config, history, and tokens so multiple users/environments are supported.
- Built-in validation tooling and comparison helpers.

**Supported platforms**: macOS and Linux (Windows supported via `install.bat` for venv setup).

**Table of contents**
- **Overview** — what the project does
- **Requirements** — system prerequisites
- **Install** — one-line installer and manual steps
- **Setup & Usage** — walkthrough and examples
- **Profiles** — how profiles work
- **Validation** — using Garmin FIT SDK tools
- **Development & Testing** — how to run locally
- **Troubleshooting** — common issues and fixes

## Requirements

- Python 3.10+
- Java (optional: for FIT validation using Garmin's FitCSVTool.jar)
- On macOS/Linux: `bash` for `install.sh` (or run `install.bat` on Windows)

## Install (recommended)

Run the included installer — it creates a local virtualenv, installs deps,
and offers to run the setup wizard.

To auto-activate the virtual environment when the script finishes, source it:

```bash
source install.sh
```

To run normally (you'll need to activate the venv manually afterwards):

```bash
bash install.sh
```

After a normal run, activate with:

```bash
source .venv/bin/activate
```

## Setup

The installer offers to run the interactive setup wizard. You can also run it
any time to configure Garmin auth and local preferences:

```bash
liftosaur-garmin --setup
```

Setup will ask about:
- Garmin authentication (stores tokens under the active profile)
- Default weight for calorie estimation
- Optional file-watcher setup (launchd/systemd)

## Usage

Convert a single CSV to a FIT file (no upload):

```bash
python -m liftosaur_garmin tests/fixtures/csv/example.csv --no-upload --output out.fit
```

Upload a CSV (after confirming setup/auth):

```bash
liftosaur-garmin path/to/your.csv
```

Common flags:
- `--no-upload` : write FIT file locally but do not upload to Garmin Connect
- `--output <path>` : specify output FIT file path
- `--profiles` : interactive profile manager
- `--force` : force re-upload even if history shows it was uploaded

## Profiles

Profiles are stored in `~/.liftosaur_garmin/profiles/<name>` and isolate config,
history, and Garmin tokens. Use the interactive menu to manage profiles:

```bash
liftosaur-garmin --profiles
```

You can set a default profile programmatically (or the setup/migration will
create one). Legacy config migration will create a `default` profile when
previous single-user files are detected.

## FIT Validation

Before upload, validate your generated FIT files with Garmin's official tools.

1. Download the FIT SDK from https://developer.garmin.com/fit/download/
2. Copy `FitCSVTool.jar` into the project's `tools/` directory.
3. Validate a FIT file:

```bash
python -m liftosaur_garmin validate path/to/file.fit
```

If validation fails, compare your file to a reference with:

```bash
python scripts/compare_fits.py generated.fit reference.fit
```

Notes:
- Tests that require validation will be skipped if the SDK jar is missing.

## Development & Testing

Create and activate a virtualenv (if not using the installer):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run a manual test using fixture CSVs:

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit
```

Unit tests (where present) can be run via `pytest` after installing dev deps.

## Troubleshooting

- Garmin upload rejected: validate with the FitCSVTool and compare with known-good FITs.
- Auth problems: remove `~/.garth/` under the active profile and rerun `--setup`.
- CSV parsing errors: ensure your Liftosaur export columns are present and the file is UTF-8 (use `utf-8-sig` if needed).

## Contributing

Contributions welcome. Keep changes small and focused: the FIT encoder is
hand-rolled and sensitive — avoid replacing it with third-party FIT writers.

Steps to contribute:

1. Fork the repo and create a feature branch
2. Add tests for any behavior changes
3. Open a PR with a clear description and example files

## Where to look in the codebase

- Core CLI & install: [liftosaur_garmin/cli.py](liftosaur_garmin/cli.py)
- CSV parsing: [liftosaur_garmin/csv_parser.py](liftosaur_garmin/csv_parser.py)
- FIT encoding: [liftosaur_garmin/fit/encoder.py](liftosaur_garmin/fit/encoder.py)
- Garmin upload: [liftosaur_garmin/uploader.py](liftosaur_garmin/uploader.py)
- Profile helpers: [liftosaur_garmin/profile.py](liftosaur_garmin/profile.py)

## License

See `PKG-INFO` and the project metadata for licensing details.

---

If you'd like, I can also:

- Add a short Quick Start video GIF to the repo
- Create a checklist in `docs/` for pre-upload validation
- Update `install.bat` to show similar activation instructions for Windows

