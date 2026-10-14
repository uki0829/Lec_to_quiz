#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("cl100k_base")'
echo "Installed. Configure OPENAI_API_KEY in .env, then run bash scripts/start.sh."
