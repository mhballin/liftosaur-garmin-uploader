# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Background watchers now invoke the installed `liftosaur-garmin` CLI entry point instead of `python -m liftosaur_garmin`, which is more reliable for launchd/systemd environments.
- Profile manager wording now uses "current profile" language to better match how the selected profile is used in day-to-day commands.
- Reinstalling a watcher now re-suggests the profile's previously configured watch folder before falling back to the default detected folder.
- Garmin integration now supports both legacy `garth` and `python-garminconnect` via an adapter layer.
- Liftosaur API mode now uploads all new workouts by default (`--api --all` remains supported).
- Liftosaur API parser is now more tolerant of common real-world record text variations (comment lines and some annotated/alternate set specs).
- Profile names now allow uppercase letters and spaces.
- Watcher service identifiers now sanitize profile names for launchd/systemd compatibility.

### Added
- `--manage-profiles` as a clearer alias for the interactive profile manager (`--profiles` still works).
- A short "Most Common Commands" section near the top of the README for onboarding.
- A `Help` option inside the interactive profile manager.
- Secure secret storage via OS keychain backends (`keyring`) for Liftosaur API keys and garminconnect credentials.
- First-sync backfill choices in setup for both Liftosaur API and CSV workflows.
- CSV baseline mode for users who choose not to backfill historical CSV workouts on first sync.

### Notes
- Existing watchers should be reinstalled once after upgrading so the regenerated watcher script picks up the new CLI-based invocation path.
- Legacy plaintext secrets are migrated to keychain-backed storage when possible.

## [1.3.1] - 2026-02-26

### Added
- macOS coordinated iCloud copy using NSFileCoordinator via PyObjC

### Changed
- iCloud temp copy now uses coordinated reads before falling back to direct copy
- macOS installs PyObjC automatically (conditional dependency)

### Fixed
- Copy deadlock when iCloud coordination locks are still active

## [1.3.0] - 2026-02-26

### Added
- **iCloud Drive file handling**: Automatically copy iCloud files to temp directory before parsing to avoid file coordination deadlock errors (`OSError: [Errno 11] Resource deadlock avoided`)
- Temp file management in `config.py`: `get_temp_dir()` and `cleanup_old_temp_files()` functions
- Automatic cleanup of temp files older than 24 hours (configurable via `temp_dir_retention_hours` in profile config)

### Changed
- `parse_csv()` now accepts optional `profile_dir` parameter for iCloud file support
- CSV files in iCloud Drive are automatically copied to `~/.liftosaur_garmin/profiles/{profile}/temp/` before parsing
- Temp directory created under each profile for isolated file management

### Fixed
- Resolves infinite retry loop when watcher encounters iCloud sync locks
- Files that previously failed with deadlock errors now parse successfully
- Backward compatible: existing code without `profile_dir` parameter continues to work

## [1.2.0] - 2026-02-23

### Notes
- Internal changes not documented.

## [1.1.1] - Earlier

- Internal pre-1.2.0 releases.
