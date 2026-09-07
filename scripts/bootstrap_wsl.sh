#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

for command_name in python3 make; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'ERROR: %s is required. Follow docs/wsl-vscode-setup.md.\n' "$command_name" >&2
    exit 1
  fi
done

if ! python3 -m venv --help >/dev/null 2>&1; then
  printf 'ERROR: python3-venv is required. Run: sudo apt install -y python3-venv\n' >&2
  exit 1
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt

PATH="$PROJECT_ROOT/.venv/bin:$PATH" make validate

printf '\nPASS: Phase 1-4 checkpoint validated in WSL.\n'
printf 'Next: cd %s && code .\n' "$PROJECT_ROOT"
