# Liftosaur Garmin Uploader

Tools to convert Liftosaur CSV workouts to Garmin FIT and upload.

## Quick start

python -m liftosaur_garmin --help

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

## Testing

- Put sample CSV files in tests/fixtures/csv/
- Run a manual test:
	python -m liftosaur_garmin tests/fixtures/csv/your_file.csv --no-upload
- Generated FIT outputs should go in tests/output/ (git-ignored)

