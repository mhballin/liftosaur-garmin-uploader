# Testing Guide

This project uses manual CLI testing only (no automated pytest). Below are the terminal commands to generate a FIT file from a Liftosaur CSV export and validate it.

## Generate a FIT File

Always set an explicit output path under `tests/output` and use versioned names like `test_v1.fit`.

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit
```

## Validate the FIT File

Use the FIT SDK validator through the CLI wrapper. `tools/FitCSVTool.jar` is bundled in the repo; if it's missing (e.g., a minimal clone), validation will be skipped.

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

## Future Improvement (Manual Note)

Add a small helper script to auto-increment `tests/output/test_vN.fit` by scanning existing files and choosing the next version number.



ok i think i need a little bit better organizing for the tests and everthing. so i can future proof this right now when i run this 



python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v1.fit

it works but it just dumps the file in the output folder and i have to keep track of the versions manually. I want to be able to just run the command and have it automatically increment the version number for me. So maybe I can do something like this in the terminal:

```bash
python -m liftosaur_garmin tests/fixtures/csv/liftosaur_2026-02-05.csv --no-upload --output tests/output/test_v3.fit
```

This are notes for me in the future when I want to implement this auto-incrementing feature. I can write a small script that checks the `tests/output` directory for existing `test_vN.fit` files, finds the highest N, and then generates the next version number automatically. This way, I can just run the command without worrying about version numbers.

