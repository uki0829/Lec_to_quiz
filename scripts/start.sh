#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo "Run bash scripts/setup.sh first."
  exit 1
fi
echo "Lecture Lab: http://127.0.0.1:${PORT:-8765}"
exec .venv/bin/python app.py
