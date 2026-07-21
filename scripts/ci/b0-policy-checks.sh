#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$script_dir/_common.sh"

uv lock --check
uv run --locked --all-packages --group dev python scripts/policy/validate_phase0_interface_freeze.py
uv run --locked --all-packages --group dev python scripts/policy/validate_repository_governance.py
uv run --locked --all-packages --group dev python scripts/policy/validate_import_boundaries.py
uv run --locked --all-packages --group dev python scripts/policy/validate_backend_capabilities.py
uv run --locked --all-packages --group dev python scripts/policy/validate_workspace_dependencies.py
uv run --locked --all-packages --group dev pytest -q tests/policy tests/ci \
    -m "not b0_policy_script_selftest and not all_check_scripts"
