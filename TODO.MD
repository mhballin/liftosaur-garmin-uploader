# Liftosaur Garmin Uploader — TODO


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


---

## Dev Notes

- This was all vibe coded so good luck