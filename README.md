# Liftosaur Garmin Uploader

Tools to convert Liftosaur CSV workouts to Garmin FIT and upload.

## Quick start

python -m liftosaur_garmin --help

## Dev

pip install -r requirements.txt

## Tree snapshot

Generate a clean repo tree snapshot for local tracking:

```bash
tree -a -I ".git|__pycache__|.venv|.pytest_cache|.mypy_cache|.dist|.build|build|dist|*.egg-info" > tree.txt
```

Notes:
- The output is stored at repo root as tree.txt and is ignored by git.
- Adjust the exclude list as needed for local tooling.
