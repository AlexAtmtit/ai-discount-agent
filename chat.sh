#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "Virtual environment not found. Running setup..."
  ./setup.sh
fi

source .venv/bin/activate
export PYTHONPATH=.

python3 scripts/chat.py "$@"

