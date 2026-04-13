# Advanced Documentation

This folder contains optional technical reference material.

You do not need these docs to install or use the uploader. Start with the main `README.md` first.

- `FIT_VALIDATION.md` explains how FIT validation works and how to debug validator failures.
- `LOGGING.md` documents the logging setup used by the CLI and background watcher.
- `MAPPING_RESEARCH.md` records the Garmin FIT exercise-mapping research behind the current strength exercise mappings.
- `TESTING.md` describes the current manual testing workflow.

Recent behavior updates covered by the main `README.md` include:
- Garmin client support for both legacy `garth` users and `python-garminconnect` for newer profiles.
- Secure secret storage through OS keychain backends (`keyring`) instead of plaintext API keys and credentials.
- First-sync backfill choices for both Liftosaur API and CSV workflows.
- More tolerant Liftosaur API history parsing for common real-world text variations.
- Profile names that allow uppercase letters and spaces.

The main install and usage guide stays in the repository `README.md`.
