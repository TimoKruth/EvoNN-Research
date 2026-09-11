#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
readonly REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${CODEX_MAINTENANCE_VALIDATE_ONLY:-0}" == "1" ]]; then
  command -v codex
  "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/automation/training_guardian.py" validate "$1"
  exit 0
fi
exec "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/automation/training_guardian.py" tick "$1"
