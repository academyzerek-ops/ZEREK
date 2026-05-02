#!/bin/bash
# ZEREK pipeline launcher
# Activates the Python 3.12 venv and runs batch_extract_v3.py with passed args.
#
# Usage:
#   ./zerek_run.sh --dry-run          # check pending queue, no API calls
#   ./zerek_run.sh                    # run actual extraction
#
# Requires: .venv/ created via `python3.12 -m venv .venv`
#           and dependencies installed (see scripts/README_v3.md).

set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found. Set up the environment first:"
  echo "  python3.12 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install \"notebooklm-py[browser]\" pyyaml python-frontmatter python-dotenv requests"
  echo "  python -m playwright install chromium"
  exit 1
fi

source .venv/bin/activate
python scripts/batch_extract_v3.py "$@"
