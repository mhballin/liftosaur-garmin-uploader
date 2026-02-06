# Testing Guide

This project uses manual CLI testing only (no automated pytest). Below are the terminal commands to generate a FIT file from a Liftosaur CSV export and validate it.

## Generate a FIT File

Always set an explicit output path under `tests/output` and use versioned names like `test_v1.fit`.

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit
```

## Auto-Increment the Test Version

To create the next available `test_vN.fit`, run this two-step snippet in the terminal. It scans the existing files and increments the highest version by 1.

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v3.fit
```

## Validate the FIT File

Use the FIT SDK validator through the CLI wrapper. Validation will be skipped if `tools/FitCSVTool.jar` is missing.

```bash
python -m liftosaur_garmin validate tests/output/test_v1.fit
```

## Notes

- Real test data in `tests/fixtures/**` is gitignored and for local testing only.
- FIT validation checks structure, required fields, and CRC integrity.
- If validation fails, compare against a reference FIT file:

```bash
python scripts/compare_fits.py tests/output/test_v2.fit tests/fixtures/fit/21783591203_ACTIVITY.fit
```
