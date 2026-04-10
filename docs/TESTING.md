# Testing Guide

This project currently relies on manual CLI testing.

## Generate a FIT File

Use an explicit output path under `tests/output/` and give each run a distinct filename.

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit
```

## Validate the FIT File

Download Garmin's FIT SDK and place `FitCSVTool.jar` in `tools/` if you want local validation enabled.

```bash
python -m liftosaur_garmin validate tests/output/test_v1.fit
```

## Compare Against a Reference FIT

If validation fails, compare the generated file against a known-good FIT file.

```bash
python scripts/compare_fits.py tests/output/test_v1.fit tests/fixtures/fit/21783591203_ACTIVITY.fit
```

## Notes

- Real test data in `tests/fixtures/**` is gitignored and intended for local testing only.
- FIT validation checks structure, required fields, and CRC integrity.
- Validation is optional for normal use when `FitCSVTool.jar` is not present locally.
- The dedicated `validate` command requires `FitCSVTool.jar`.
