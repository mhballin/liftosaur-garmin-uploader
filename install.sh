#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "🏋️ Liftosaur → Garmin Uploader — Installer"

echo "Checking Python version..."
PYTHON_CMD="python3"
PYTHON_VERSION=""

if command -v "$PYTHON_CMD" >/dev/null 2>&1; then
  PYTHON_VERSION="$($PYTHON_CMD --version 2>&1 | awk '{print $2}')"
fi

if [[ -z "$PYTHON_VERSION" ]]; then
  echo "❌ Python 3.10+ is required. Python was not found. Install from https://python.org"
  exit 1
fi

PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 || ( "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ) ]]; then
  echo "❌ Python 3.10+ is required. You have ${PYTHON_MAJOR}.${PYTHON_MINOR}. Install from https://python.org"
  exit 1
fi

if [[ -d ".venv" ]]; then
  read -r -p "Virtual environment already exists. Reinstall? (y/N) " REINSTALL
  if [[ ! "$REINSTALL" =~ ^[Yy]$ ]]; then
    echo "Skipping venv creation."
  else
    rm -rf .venv
  fi
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

. .venv/bin/activate

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .

echo "✅ Dependencies installed"

read -r -p "Run setup wizard now? (Y/n) " RUN_SETUP
if [[ -z "$RUN_SETUP" || "$RUN_SETUP" =~ ^[Yy]$ ]]; then
  .venv/bin/python -m liftosaur_garmin --setup
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "To use the tool, either:"
echo "  source .venv/bin/activate"
echo "  liftosaur-garmin --help"
echo ""
echo "Or run directly:"
echo "  .venv/bin/liftosaur-garmin --help"
