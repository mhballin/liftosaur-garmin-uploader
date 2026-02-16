# Liftosaur Garmin Uploader — TODO

## Phase 1: Data Accuracy ✅ (Done)

- [x] FIT file generates and uploads to Garmin Connect
- [x] Exercise mapping — 3-tier system (manual overrides → fuzzy match → muscle fallback)
- [x] Timestamps — using real `Completed Reps Time` from CSV instead of estimates
- [x] Rest periods calculated from actual set timestamps
- [x] Work Time showing correctly in Garmin (`timer_s` = active time only)
- [x] Removed split messages that caused Run/Walk chart bug (methods still in encoder but never called)
- [x] Weight conversion lbs → kg
- [x] Exercise mapping verified for GZCLP exercises
- [x] Bodyweight exercise handling — exercises like Superman show actual name, not just "Bodyweight"
- [x] Set counts match between CSV and Garmin Connect display

### Remaining cleanup

- [x] **AMRAP sets** — parsed from CSV `Is AMRAP?` column, labeled in debug logging; FIT set data already captures actual completed reps
- [x] **Superset-style overlapping timestamps** — verified working; superset transitions logged when gap < 10s between different exercises; short set durations from rapid succession flagged
- [x] **Include warmup sets** — warmup sets now included as normal active sets in FIT output; CLI shows warmup/AMRAP counts
- [x] **Merge `--status` into `--list`** — both flags show overlapping workout/upload info. Consolidated into `--list` and removed `--status`
- [x] **Remove dead encoder methods** — `write_split`, `write_split_summary`, `write_lap`, `write_workout`, `write_workout_step` removed from `fit/encoder.py`
- [x] **Fix `__main__.py` exit code** — already had `sys.exit(main())`, verified correct
- [x] **Fake HR records** — removed; Garmin Connect accepts FIT files without record messages. Removed 1-second `record` messages and fake HR from session. File size reduced ~95% (e.g. 31KB → 1.4KB)


---

## Phase 2: Multi-Workout Processing ✅ (Done)

- [x] Remove hardcoded datetime filter in `cli.py`
- [x] Batch error handling — continues past failures, reports summary at end
- [x] Tested with CSV containing 33 workouts — all 33 generate valid FIT files
- [x] Defensive timestamp handling — workouts with missing `Completed Reps Time` no longer crash encoder
- [x] Verified `history.json` dedup works across runs
- [x] Tested CLI flags: `--date`, `--all`, `--force`, `--list`, `--dry-run`, `--no-upload`, `--skip-validation`
- [x] Timezone handling — `local_timestamp` on activity message, auto-detects system timezone, `--timezone` override flag available
- [x] Confirmed Garmin Connect shows correct local time after upload

---

## Phase 3: Upload & Automation ✅ (Done)

- [x] `garth`-based upload works reliably for single files
- [x] Batch upload (multiple workouts in one run with `--all`)
- [x] `garth` token expiration handled gracefully (re-auth prompt)
- [x] Garmin Connect handles rapid sequential uploads
- [x] iOS Shortcut copies Liftosaur CSV export to iCloud Drive
- [x] Shortcut automation triggers on leaving gym
- [x] `launchd`/`fswatch` watches iCloud Drive folder for new `.csv` files
- [x] On new file: runs `python -m liftosaur_garmin <file> --all` automatically

---

## Phase 4: Calorie Estimation 🔧 (Next Up)

Estimate calories burned per workout using a research-backed formula, so Garmin Connect shows a real number instead of zero.

### Background

The StrengthLog formula is derived from a study of 52 adults doing resistance training (2–3 sets × 8–12 reps at 60–70% 1RM across 7 exercises). The key finding is that calorie burn during strength training is dominated by body weight and duration — exercise selection, rep ranges, and rest periods roughly cancel out. The formula is:

- **Men:** `minutes × weight_kg × 0.0713`
- **Women:** `minutes × weight_kg × 0.0637`

We use the male coefficient (0.0713) as a single default. The ~10% difference between male/female coefficients is small relative to the inherent imprecision of any non-HR-based estimate. This is documented in the README so users understand the tradeoff.

Reference: [StrengthLog Calories Calculator](https://www.strengthlog.com/calories-burned-lifting-weights/)

### Onboarding (during `--setup`)

- [x] Ask: "Do you want to estimate calories for your workouts?" → yes/no
- [x] If yes: ask for body weight and unit preference (kg or lbs)
- [x] Convert to kg internally, store in config
- [x] Save to `~/.liftosaur_garmin/config.json`:
  ```json
  {
    "calories_enabled": true,
    "fallback_weight_kg": 84.0
  }
  ```

### Weight source priority

1. **Garmin Connect** — fetch most recent weigh-in via `garth`
2. **Fallback** — use `fallback_weight_kg` from config (entered during onboarding)
3. **Neither** — if `calories_enabled` is false or no weight available, `total_calories = 0` (current behavior)

### Implementation

- [x] Add `liftosaur_garmin/config.py` — load/save `~/.liftosaur_garmin/config.json`
- [x] Add calorie questions to `--setup` onboarding flow in `cli.py`
- [x] Create helper to fetch most recent weight from Garmin Connect via `garth`
- [x] Calculate: `total_calories = int(duration_minutes * weight_kg * 0.0713)`
- [x] Pass `total_calories` into session message in `workout_builder.py` (session message field 11 already exists as placeholder 0)
- [x] Duration comes from existing CSV timestamps (first set start → last set end)

### Documentation

- [x] README section explaining the formula, its source, and limitations
- [x] Note that a single coefficient is used (male, 0.0713) and why
- [x] Note that weight is pulled automatically from Garmin Connect with manual fallback
- [x] Clarify this is a duration × bodyweight estimate, not HR-based

### Not doing (and why)

- **Per-exercise MET values** — research shows the variables cancel out; no strength training app does this
- **HR-based calories** — requires watch sync timing, only 15s sampling, added complexity for marginal accuracy gain
- **Asking for sex** — coefficient difference is ~10%, within the margin of error for any non-HR estimate

---

## Phase 5: Security Audit 🔒

**Do this BEFORE the repo goes public.**

### 5a: Scan repo for sensitive data

- [x] **Audit full git history** — every file ever added, even if later deleted, is still in history
  ```bash
  git log --all --diff-filter=A --name-only --pretty=format: | sort -u
  ```
- [x] **Sanitize `sample.csv`** — current file contains real personal data (`Mikes GZCLP 3.0`, real timestamps, real weights). Replace with fake/generic data before committing
- [x] **Update `.gitignore`** — current pattern `tests/fixtures/**/*.csv` blocks ALL CSVs including `sample.csv`. Change to `tests/fixtures/csv/liftosaur_*.csv` and add `!tests/fixtures/csv/sample.csv`
- [x] **Check committed FIT files** — removed FIT fixtures from repo; only empty fixture folders remain
  ```bash
  java -jar tools/FitCSVTool.jar -b tests/fixtures/fit/21779306834_ACTIVITY.fit
  # Look for: serial_number, timestamp, position_lat, position_long
  ```
  Decide per file: keep (if safe), sanitize, or delete
- [x] **Grep for credentials and personal info**
  ```bash
  grep -rn "@" --include="*.py" --include="*.json" --include="*.md" .
  grep -rn "/Users/" --include="*.py" .
  grep -rni "password\|secret\|token\|api_key\|credential" --include="*.py" .
  ```
- [x] **Verify garth tokens never committed** — confirm `~/.garth/` is gitignored and no `oauth1_token.json` or `oauth2_token.json` was ever tracked
- [x] **Check device serial in `constants.py`** — set to `0` to avoid using a real serial

### 5b: Harden `.gitignore`

Current `.gitignore` issues found during audit:
- `tests/fixtures/**/*.csv` is too broad — blocks `sample.csv` from being tracked
- `*.fit` globally blocks all FIT files including test fixtures
- Missing patterns for `.garth/`, `*.code-workspace`, `.DS_Store`

Target `.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
venv/
.env
.env.*
.pytest_cache/
.mypy_cache/

# Real user data — NEVER commit
tests/fixtures/csv/*.csv
tests/fixtures/fit/*.fit
tests/output/

# Garmin auth tokens
.garth/
**/garth/oauth*.json

# User config directory
.liftosaur_garmin/

# FIT SDK (large, Garmin-licensed — users download separately)
tools/
FitSDKRelease_*/

# Generated output
*.fit

# OS / IDE
.DS_Store
.vscode/
*.code-workspace

# Local snapshots
tree.txt
```

- [x] Update `.gitignore` to match the above
- [x] Verify fixture data is not tracked

### 5c: Scrub git history (if needed)

If 5a finds anything sensitive that was ever committed:

- [x] Install `git filter-repo` (`pip install git-filter-repo`)
- [x] Remove sensitive files from all commits:
  ```bash
  git filter-repo --path <sensitive_file> --invert-paths
  ```
- [x] Force push to rewrite remote history
- [x] Rotate any exposed credentials (change Garmin password, recreate garth tokens)

**Note:** This rewrites all commit hashes. Do it once, before anyone else has cloned the repo.

---

## Phase 6: Package & Publish to PyPI 📦

Make it installable with `pip install liftosaur-garmin-uploader`.

### Packaging

- [ ] Replace `setup.py` with `pyproject.toml` (modern Python standard)
- [ ] Add metadata: description, author, license, Python version, keywords
- [ ] Define CLI entry point: `liftosaur-garmin` command
  ```toml
  [project.scripts]
  liftosaur-garmin = "liftosaur_garmin.cli:main"
  ```
- [ ] Add `LICENSE` file (MIT recommended)
- [ ] Verify all dependencies declared (`garth` is the only runtime dep)

### First-run experience for new users

- [ ] `liftosaur-garmin --setup` — prompts for Garmin credentials, saves tokens, done
- [ ] `liftosaur-garmin workout.csv --all` — main usage
- [ ] Clear error messages when config doesn't exist yet
- [ ] FitCSVTool.jar is optional (validation skipped with warning if missing — already implemented)

### README for strangers

- [ ] One-sentence description
- [ ] `pip install` command
- [ ] 3-line quickstart (install → setup → upload)
- [ ] Screenshot of how it looks in Garmin Connect
- [ ] Supported workout types / programs
- [ ] How to contribute
- [ ] Link to Liftosaur app

### Publish

- [ ] Create PyPI account
- [ ] Build: `python -m build`
- [ ] Upload: `twine upload dist/*`
- [ ] Verify clean install: `pip install liftosaur-garmin-uploader && liftosaur-garmin --help`

---

## Phase 7: Tests & CI 🧪

### Unit tests (no external dependencies needed)

- [ ] `csv_parser.py` — parsing, column validation, workout grouping
- [ ] `exercise/mapping.py` — name resolution, fallback behavior, manual overrides
- [ ] `exercise/duration.py` — timing estimates, `lbs_to_kg` conversion
- [ ] `fit/utils.py` — timestamp conversion, FIT epoch math, timezone resolution
- [ ] `config.py` — config loading/saving (after Phase 4)

### Integration tests (require FitCSVTool.jar + Java)

- [ ] FIT file structural validation (existing `test_validation.py`)
- [ ] Round-trip: CSV → FIT → FitCSVTool parse → verify fields

### CI setup

- [ ] Add `[project.optional-dependencies]` with pytest in `pyproject.toml`
- [ ] `.github/workflows/ci.yml` — runs unit tests on every push
- [ ] Skip FitCSVTool tests when Java not available
- [ ] `conftest.py` with shared fixtures

---

## Future Enhancements (Don't Build Yet)

- [ ] **Cloud automation** — migrate file watcher to a cloud function (AWS Lambda / Google Cloud Function) to remove Mac dependency; iOS Shortcut would POST directly to cloud endpoint
- [ ] **Automatic Liftosaur export** — may not be possible without Liftosaur app support; manual export + shortcut trigger is fine for now
- [ ] **Heart rate merging** — pull HR from Garmin Connect for workout time window, embed in FIT file (requires watch sync, only 15s sampling — poor complexity vs accuracy tradeoff)
- [ ] **Custom Liftosaur exercises** — user-created exercises that won't match any Garmin ID
- [ ] **Equipment variants** — "Bench Press, Dumbbell" vs "Bench Press, Cable" normalization

---

## Known Issues

- **Garmin exercise names** — FIT files show Garmin's exercise names, not the original Liftosaur names. This is expected FIT behavior.
- **Garmin Connect strictness** — Garmin Connect validation is stricter than FIT SDK. Always test by uploading after encoder changes.
- **Missing timestamps** — some older workouts lack `Completed Reps Time`. Defensive handling with warnings is in place.

---

## Dev Notes

- Always validate with FitCSVTool.jar before uploading: `python -m liftosaur_garmin validate <file.fit>`
- Compare against real Fenix 7 FIT files in `tests/fixtures/fit/`
- Real test data is gitignored; `sample.csv` should be sanitized before committing
- `garth` stores OAuth tokens, not raw passwords — one-time auth then token refresh
- `scripts/diagnose_workouts.py` available for inspecting specific workout CSV rows
- `scripts/compare_fits.py` for diffing generated vs reference FIT files