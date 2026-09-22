#!/usr/bin/env bash
# Build Squad AI for the current platform (macOS Apple Silicon / Linux).
# Run from the project root:  bash packaging/build.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Creating build venv"
python3 -m venv .build-venv
# shellcheck disable=SC1091
source .build-venv/bin/activate

echo "==> Installing dependencies (+ PyInstaller)"
pip install --upgrade pip
pip install -r requirements.txt || echo "WARN: some optional deps failed; app will run with fewer features"
pip install pyinstaller

echo "==> Running tests before packaging"
python -m unittest discover -s tests

echo "==> Building with PyInstaller"
pyinstaller --noconfirm packaging/squad_ai.spec

echo "==> Done. Output in ./dist/"
ls -la dist/
if [ "$(uname)" = "Darwin" ]; then
  echo "macOS app bundle: dist/Squad AI.app"
  echo "Note: on first capture, grant Screen Recording permission in"
  echo "System Settings > Privacy & Security > Screen Recording."
fi
