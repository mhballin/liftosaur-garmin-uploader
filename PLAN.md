# Liftosaur Garmin Uploader Plan

This plan tracks remaining work after Phase 1 (FIT encoder fixes) is complete.

## Phase 1 (Completed)
- Fixed FIT encoder definition caching for variable-length fields.
- Fixed workout step rest/non-rest definition mismatch.
- Fixed exercise title variable-length definition mismatch.
- Fixed split summary argument ordering.
- Corrected message ordering to match required spec.
- Added lap message support.
- Manual validation via Garmin Connect upload.

See: PHASE1_FIXES_SUMMARY.md

## Phase 2 - Code Quality Cleanup
Goal: Make the codebase clean, consistent, and easy to review.

1) Consolidate warmup filtering
- Add a helper like `is_working_set(row: dict) -> bool`.
- Replace the repeated inline checks across CLI, builder, and history.

2) Exit code propagation
- In `__main__.py`, call `sys.exit(main())`.

3) Fix temporary file handling
- Use `tempfile.NamedTemporaryFile` or close fd from `mkstemp()`.

4) Remove dead code
- Remove unused `parse_csv_rows` and `build_fit` wrapper.

5) Import hygiene and typing
- Replace wildcard import in encoder with explicit imports.
- Add missing instance type hints for `_messages` and `_local_count`.

6) Test correctness cleanup
- Fix `test_csv_parser` expected workout count (sample.csv has two workouts).

Definition of done:
- `pytest tests/` passes.
- No obvious dead code or duplicated warmup logic.
- Code review reads cleanly.

## Phase 3 - iCloud URL Input
Goal: Support CSV input from a shareable iCloud Drive URL.

1) CLI surface
- Add `--url` argument for shareable iCloud Drive links.
- Keep existing local CSV path support.

2) iCloud download module
- Add `liftosaur_garmin/icloud.py` that:
  - Follows redirects to resolve the actual download URL.
  - Downloads the CSV bytes via stdlib `urllib.request`.
  - Returns file-like data or writes to a temp file.

3) CSV reader refactor
- Allow `read_csv` to accept a Path or file-like object.
- Keep validation and grouping behavior unchanged.

Definition of done:
- `python -m liftosaur_garmin --url <icloud-link> --no-upload -o test.fit` works.

## Phase 4 - Garmin Connect Auto Upload
Goal: Enable end-to-end automation once iCloud input works.

1) Use existing upload path
- Remove `--no-upload` in actual runs.
- Keep `--setup` for auth/token caching.

2) Validate complete flow
- `--url <icloud-link> --all` uploads without manual steps.
- Upload history prevents duplicates unless `--force` is used.

Definition of done:
- CSV from iCloud URL -> FIT -> Garmin Connect upload -> history updated.

## Optional Future Enhancements (Not in Scope Yet)
- Merge real heart rate data from Garmin Connect into FIT files.
- iOS Shortcut + server automation for fully hands-off uploads.


