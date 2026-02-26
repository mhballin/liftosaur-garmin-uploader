# Changelog

All notable changes to this project will be documented in this file.

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

### Added
- Change summary

## [1.1.1] - Earlier

- Previous releases
